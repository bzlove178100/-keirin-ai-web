"""Synthetic inbound startup/expiry/recovery composition, only in fixed QEMU."""
import json
from pathlib import Path
import socket
import time


def admission(current, sealed, actual_lease, sealed_lease, proof, tc, original_tc, now):
    if (not sealed or current != sealed or not sealed_lease or actual_lease != sealed_lease
            or not isinstance(proof, dict) or proof.get('loader_exits') is not True
            or type(proof.get('deadline_ns')) is not int or not original_tc or tc != original_tc
            or not 2 <= proof['deadline_ns'] / 1e9 - now <= 8):
        raise RuntimeError('INBOUND_QUALIFICATION_GUARDS_REQUIRED')


def connect(g, address):
    s = socket.socket(socket.AF_INET6 if ':' in address else socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(.25)
    try:
        s.bind(('2001:db8:1::1' if ':' in address else '192.0.2.1', 0))
        s.connect((address, 443)); return s
    except Exception:
        s.close(); raise


def probes(g, old):
    values = [g.exchange(s) for s in old]
    for address in g.PEERS:
        try:
            with connect(g, address) as s: values.append(g.exchange(s))
        except OSError: values.append(False)
    return dict(qualification=values, probe_finished_monotonic=time.monotonic())


def marker(b):
    path = b.STATE / 'inbound-suspend-marker'
    return int(path.is_file() and path.read_text() == b.boot())


def emit(b, mode, event, **values):
    print('INBOUND_LEASE_RECORD ' + json.dumps(dict(event=event, mode=mode, boot=b.boot(), marker=marker(b),
          **dict(monotonic=time.monotonic(), boottime=time.clock_gettime(time.CLOCK_BOOTTIME)),
          **values)), flush=True)


def main(action, b, i, g):
    h = b.module('inbound', '/inbound_boot.py')
    mode = b.composition()
    if mode not in ('awake', 'suspend') or not h.lease_enabled(): raise RuntimeError('FIXED_INBOUND_LEASE_REQUIRED')
    lease = b.module('lease', '/lease.py')
    if action == 'recover':
        saved = b.read('inbound-lease')
        if saved['boot'] != b.boot(): raise RuntimeError('SAME_EXPIRED_BOOT_REQUIRED')
        h.require_seal(h.shape(i), h.rpc(b, 'expected'))
        if h.identity(i) != saved['restored_identity']: raise RuntimeError('RESTORE_IDENTITY_CHANGED')
        # Release only expired experiment guards AFTER exact maintenance readback.
        # The recovered packet matrix must not be masked by an outer drop gate.
        if g.identity(g.reports(lease)) != saved['lease_identity'] or g.tc_identity(saved['proof']) != saved['tc_identity']:
            raise RuntimeError('EXPIRED_GUARDS_CHANGED')
        for family, table in lease.TABLES: g.run(g.NFT, 'delete', 'table', family, table)
        g.run(g.TC, 'qdisc', 'del', 'dev', 'host0', 'clsact')
        result = h.matrix(b, i, 'closed')
        if probes(g, [])['qualification'] != [False, False]: raise RuntimeError('RESTORED_EGRESS_MUST_STAY_CLOSED')
        h.require_seal(h.shape(i), h.rpc(b, 'expected'))
        if h.identity(i) != saved['restored_identity']: raise RuntimeError('RESTORED_MATRIX_IDENTITY_CHANGED')
        b.write('inbound-recovery', dict(boot=b.boot(), **result))
        emit(b, mode, 'recovered', checked=result, guards_removed=True, policy_unchanged=True)
        return
    if action != 'lease': raise RuntimeError('FIXED_INBOUND_LEASE_ACTION_REQUIRED')
    g.run('/sbin/modprobe', '-C', '/module-config', '-a', 'sch_ingress', 'cls_bpf')
    h.require_seal(h.shape(i), h.rpc(b, 'expected'))
    sealed = b.read('gate')['identity']
    if h.identity(i) != sealed: raise RuntimeError('SAME_STARTUP_SEAL_REQUIRED')
    ssh = b.module('ssh', '/ssh_probe.py'); server = ssh.start_server(systemd=True)
    (b.STATE / 'inbound-suspend-marker').write_text(b.boot())
    opened = []
    try:
        ready = h.rpc(b, 'ssh-start'); emit(b, mode, 'ssh_ready', ssh=ready)
        try: admission(sealed, sealed, None, None, None, None, None, 0)
        except RuntimeError: pass
        else: raise RuntimeError('UNGUARDED_PROMOTION_MUST_FAIL')
        if probes(g, [])['qualification'] != [False, False] or h.identity(i) != sealed:
            raise RuntimeError('REFUSED_PROMOTION_MUST_STAY_CLOSED')
        expected = h.rpc(b, 'qualification')
        live_store = None
        if Path('/inbound_persistence.py').is_file():
            store = b.module('inbound_persistence', '/inbound_persistence.py')
            if store.phase() == 'live-refusal': live_store = store
        started = g.clocks(); deadline = int(started['boottime'] * 1e9) + 8000000000
        g.run(g.NFT, '-f', '-', input=lease.install(socket.if_nametoindex('host0')).encode())
        initial = g.reports(lease); lease_seal = lease.snapshot(initial); original = g.identity(initial)
        proof = json.loads(g.run('/boot-guard', str(deadline)))
        if proof.get('deadline_ns') != deadline: raise RuntimeError('ORIGINAL_IMMUTABLE_DEADLINE_REQUIRED')
        tc = g.tc_identity(proof)
        admission(h.identity(i), sealed, lease.snapshot(g.reports(lease)), lease_seal,
                  proof, g.tc_identity(proof), tc, g.clocks()['boottime'])
        i.t.nft(i.t.r.replacement('qualification')); h.require_seal(h.shape(i), expected)
        active = h.identity(i)
        for address in g.PEERS: opened.append(connect(g, address))
        before = probes(g, opened)
        if before['qualification'] != [True]*4 or time.monotonic() - started['monotonic'] >= 3:
            raise RuntimeError('ORIGINAL_LIVE_WINDOW_REQUIRED')
        if live_store is not None:
            refusal = live_store.refuse_live_save(deadline)
            before = probes(g, opened)
            if (before['qualification'] != [True]*4 or time.monotonic() - started['monotonic'] >= 3
                    or h.identity(i) != active or g.identity(g.reports(lease)) != original
                    or g.tc_identity(proof) != tc):
                raise RuntimeError('LIVE_REFUSAL_CANNOT_CHANGE_POLICY_GUARDS_OR_WINDOW')
            before['save_refusal'] = refusal
        emit(b, mode, 'before', lease_start=started, boottime_guard=proof, **before)
        if mode == 'suspend':
            if 'deep' not in Path('/sys/power/mem_sleep').read_text(): raise RuntimeError('REAL_DEEP_SLEEP_REQUIRED')
            Path('/sys/power/mem_sleep').write_text('deep'); Path('/sys/power/state').write_text('mem')
        else: time.sleep(10)
        # First network actions, before reads, SSH, restoration or guard removal.
        after_clock = g.clocks(); after = probes(g, opened)
        if after['qualification'] != [False]*4: raise RuntimeError('FIRST_EXPIRED_PACKETS_MUST_FAIL')
        if mode == 'suspend' and after['probe_finished_monotonic'] - started['monotonic'] >= 7:
            raise RuntimeError('ORIGINAL_RESUME_WINDOW_REQUIRED')
        if (h.identity(i) != active or g.identity(g.reports(lease)) != original or g.tc_identity(proof) != tc):
            raise RuntimeError('EXPIRY_WITHOUT_POLICY_MUTATION_REQUIRED')
        authenticated = h.rpc(b, 'ssh-check')
        if authenticated != {'established': [True]*2, 'fresh': [True]*2}: raise RuntimeError('EXPIRY_SSH_CONTINUITY_REQUIRED')
        outcome = 'BOOTTIME_AWAKE_EXPIRY_CONFIRMED' if mode == 'awake' else 'BOOTTIME_SUSPEND_EXPIRY_OBSERVED'
        print('INBOUND_LEASE_RECORD ' + json.dumps(dict(event='after', mode=mode, boot=b.boot(), marker=marker(b),
            **after_clock, **after, ssh=authenticated, boottime_guard=proof, rule_identity_unchanged=True,
            tc_identity_unchanged=True, outcome=outcome)), flush=True)
        # Late controller recovery replaces only the owned profile. It never
        # reinstalls or extends either deadline, and existing SSH must survive.
        i.t.nft(i.t.r.replacement('maintenance')); h.require_seal(h.shape(i), h.rpc(b, 'expected'))
        if probes(g, opened)['qualification'] != [False]*4: raise RuntimeError('RECOVERY_CANNOT_REOPEN')
        restored_ssh = h.rpc(b, 'ssh-check')
        if restored_ssh != authenticated: raise RuntimeError('RESTORATION_SSH_CONTINUITY_REQUIRED')
        if g.identity(g.reports(lease)) != original or g.tc_identity(proof) != tc: raise RuntimeError('RECOVERY_CANNOT_RENEW_GUARDS')
        b.write('inbound-lease', dict(boot=b.boot(), restored_identity=h.identity(i),
            lease_identity=original, tc_identity=tc, proof=proof))
        emit(b, mode, 'restored', ssh=restored_ssh, guards_unchanged=True, qualification=[False]*4)
    finally:
        for s in opened: s.close()
        try: h.rpc(b, 'ssh-stop')
        finally: ssh.stop_server(server)


def completion(b, i, g):
    mode = b.composition()
    states = {n: b.properties(g, 'kc-' + n) for n in ('check', 'lease', 'recover')}
    if b.read('inbound-recovery')['boot'] != b.boot(): raise RuntimeError('RECOVERY_COMPLETION_REQUIRED')
    for n in ('lease', 'recover'):
        if states[n]['ActiveState'] != 'active' or states[n]['ExecMainStatus'] != '0':
            raise RuntimeError('INBOUND_LEASE_SERVICE_COMPLETION_REQUIRED')
    emit(b, mode, 'completed', states=states, activation_allowed=False)

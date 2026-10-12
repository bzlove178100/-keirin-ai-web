"""Fixed systemd-managed synthetic SSH/lease experiment; never a host installer."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import time


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def context():
    b = module('boot', '/boot_probe.py'); b.guard()
    mode = b.composition()
    if not mode: raise RuntimeError('SYSTEMD_COMPOSITION_OPT_IN_REQUIRED')
    return b, module('packets', '/probe.py'), mode


def request(command):
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as s:
        s.settimeout(30); s.connect('/run/kc-boot/control')
        s.sendall(command); data = s.recv(16384)
        if not data: raise RuntimeError('PEER_RESPONSE_REQUIRED')
        return json.loads(data)


def marker(path=Path('/run/kc-boot/suspend-marker'), boot_path=Path('/proc/sys/kernel/random/boot_id')):
    return int(path.is_file() and path.read_text() == boot_path.read_text().strip())


def emit(event, mode, **values):
    print('SYSTEMD_LEASE_RECORD ' + json.dumps(dict(event=event, mode=mode,
          boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
          monotonic=time.monotonic(), boottime=time.clock_gettime(time.CLOCK_BOOTTIME), marker=marker(), **values)), flush=True)


def main(action):
    b, g, mode = context()
    if not b.link_up(g) or b.read('gate')['boot'] != b.boot(): raise RuntimeError('SAME_SEALED_BOOT_REQUIRED')
    if action == 'auth':
        module('ssh', '/ssh_probe.py').start_server(systemd=True)
        evidence = request(b'ssh-start')
        b.write('auth', dict(boot=b.boot(), **evidence))
        emit('ssh_ready', mode, **evidence)
        return
    if action != 'lease': raise RuntimeError('FIXED_COMPOSED_ACTION_REQUIRED')
    auth = b.read('auth')
    if auth['boot'] != b.boot() or any(auth.get(k) != [True, True] for k in ('established', 'wrong_keys_rejected', 'wrong_hosts_rejected')):
        raise RuntimeError('AUTHENTICATION_BEFORE_LEASE_REQUIRED')
    lease = module('lease', '/lease.py'); policy = module('policy', '/startup_policy.py')
    sealed = b.read('gate')['seal']
    try: g.release_startup(policy, sealed, lease, None, None, None, 0)
    except RuntimeError as exc:
        if str(exc) != 'STARTUP_RELEASE_GUARDS_REQUIRED': raise
    else: raise RuntimeError('UNGUARDED_RELEASE_MUST_FAIL')
    refused = [g.reaches(a, port) for port in (443, 22) for a in g.PEERS]
    if refused != [False, False, True, True] or policy.seal(json.loads(g.run(g.NFT, '-j', 'list', 'table', 'inet', policy.TABLE))) != sealed:
        raise RuntimeError('REFUSED_RELEASE_MUST_REMAIN_CLOSED')
    emit('release_refused', mode, new_connections=refused, policy_unchanged=True)
    opened = []
    try:
        old_m = [g.connect(a, 22) for a in g.PEERS]; opened.extend(old_m)
        g.run(g.NFT, '-f', '-', input=f'table inet {g.UNRELATED} {{ chain sentinel {{ counter drop; }}; }}\n'.encode())
        unrelated = json.loads(g.run(g.NFT, '-j', 'list', 'table', 'inet', g.UNRELATED))
        started = g.clocks(); deadline_ns = int(started['boottime'] * 1e9) + 8000000000
        g.run(g.NFT, '-f', '-', input=lease.install(socket.if_nametoindex('host0')).encode())
        initial = g.reports(lease); lease_seal = lease.snapshot(initial); original = g.identity(initial)
        proof = json.loads(g.run('/boot-guard', str(deadline_ns)))
        if proof.get('deadline_ns') != deadline_ns or proof.get('loader_exits') is not True: raise RuntimeError('IMMUTABLE_DEADLINE_REQUIRED')
        original_tc = g.tc_identity(proof)
        g.release_startup(policy, sealed, lease, lease_seal, proof, original_tc, deadline_ns)
        emit('released', mode, lease_start=started, boottime_guard=proof)
        old_q = [g.connect(a, 443) for a in g.PEERS]; opened.extend(old_q)
        live = g.probes(old_q, old_m); g.require(live, True)
        if time.monotonic() - started['monotonic'] >= 3: raise RuntimeError('LIVE_PRE_SUSPEND_WINDOW_REQUIRED')
        emit('before', mode, lease_start=started, boottime_guard=proof, **live)
        if mode == 'suspend':
            if 'deep' not in Path('/sys/power/mem_sleep').read_text(): raise RuntimeError('ACTUAL_DEEP_SUSPEND_REQUIRED')
            Path('/sys/power/mem_sleep').write_text('deep'); Path('/sys/power/state').write_text('mem')
        else: time.sleep(10)
        # First post-resume network operations, before any policy read or SSH check.
        after_clock = g.clocks(); observed = g.probes(old_q, old_m); g.require(observed, False)
        unchanged = g.identity(g.reports(lease)) == original and json.loads(g.run(g.NFT, '-j', 'list', 'table', 'inet', g.UNRELATED)) == unrelated
        tc_unchanged = g.tc_identity(proof) == original_tc
        if not unchanged or not tc_unchanged: raise RuntimeError('ORIGINAL_POLICY_IDENTITY_REQUIRED')
        if mode == 'suspend' and observed['probe_finished_monotonic'] - started['monotonic'] >= 7:
            raise RuntimeError('FIRST_RESUME_PROBE_WINDOW_REQUIRED')
        outcome = 'BOOTTIME_AWAKE_EXPIRY_CONFIRMED' if mode == 'awake' else 'BOOTTIME_SUSPEND_EXPIRY_OBSERVED'
        # Use pre-probe clocks for suspend accounting, as the existing harness does.
        print('SYSTEMD_LEASE_RECORD ' + json.dumps(dict(event='after', mode=mode, boot=b.boot(),
              **after_clock, **observed, marker=marker(), outcome=outcome, rule_identity_unchanged=unchanged,
              tc_identity_unchanged=tc_unchanged, boottime_guard=proof)), flush=True)
        authenticated = request(b'ssh-check')
        if authenticated != {'established': [True]*2, 'fresh': [True]*2}: raise RuntimeError('SSH_CONTINUITY_REQUIRED')
        emit('ssh_after', mode, **authenticated)
        time.sleep(max(0, started['monotonic'] + 10 - time.monotonic()))
        late = g.probes(old_q, old_m); g.require(late, False)
        if g.identity(g.reports(lease)) != original or g.tc_identity(proof) != original_tc: raise RuntimeError('LATE_IDENTITY_REQUIRED')
        emit('awake_expired', mode, **late)
        b.write('lease', dict(boot=b.boot(), outcome=outcome, deadline_ns=deadline_ns,
                              boottime_guard=proof, rule_identity=original, tc_identity=original_tc))
    finally:
        for s in opened: s.close()


def completion(g, boot_case):
    b, _, mode = context()
    states = {n: b.properties(g, 'kc-' + n) for n in ('link', 'observe', 'auth', 'lease')}
    if boot_case == 'closed':
        if b.read('lease')['boot'] != b.boot() or any(s['ActiveState'] != 'active' or s['ExecMainStatus'] != '0' for s in states.values()):
            raise RuntimeError('COMPOSED_SERVICE_COMPLETION_REQUIRED')
    elif any((b.STATE / n).exists() or int(states[n]['ExecMainStartTimestampMonotonic']) != 0 for n in ('auth', 'lease')):
        raise RuntimeError('FAILED_BOOT_MUST_PREVENT_AUTH_AND_LEASE')
    emit('completed', mode, boot_case=boot_case, states=states, activation_allowed=False)


def before_clean(g, boot_case):
    b, _, _ = context()
    if boot_case == 'closed' and request(b'ssh-stop') != {'stopped': True}: raise RuntimeError('SSH_CLIENT_CLEANUP_REQUIRED')
    g.run('/usr/bin/systemctl', 'stop', 'kc-lease.service', 'kc-auth.service', 'kc-observe.service')
    if boot_case == 'closed':
        lease = module('lease', '/lease.py')
        for family, name in (*lease.TABLES, ('inet', g.UNRELATED)): g.run(g.NFT, 'delete', 'table', family, name)


def after_clean():
    # PID1 reaps the service children; this also checks all guest SSH processes.
    module('ssh', '/ssh_probe.py').stop_server(None)


if __name__ == '__main__':
    try: main(sys.argv[1] if len(sys.argv) == 2 else '')
    except Exception as exc:
        print('SYSTEMD_LEASE_FAIL ' + repr(exc), flush=True)
        raise

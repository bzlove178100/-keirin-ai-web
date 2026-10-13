"""Normal shutdown of the restored synthetic inbound guest, never host power."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

SERVICES = ('report', 'recover', 'lease', 'check', 'link', 'gate', 'setup')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def context():
    b = module('boot', '/boot_probe.py'); b.guard()
    flags = Path('/proc/cmdline').read_text().split()
    if (flags.count('kc_inbound_restart=1') != 1 or flags.count('kc_inbound_lease=1') != 1
            or flags.count('kc_inbound_boot=closed') != 1 or b.composition() not in ('awake', 'suspend')):
        raise RuntimeError('FIXED_INBOUND_RESTART_OPT_IN_REQUIRED')
    return b, module('inbound', '/inbound_boot.py'), module('packets', '/probe.py')


def expired(state, recovery, boot, now):
    proof = state.get('proof')
    if (state.get('boot') != boot or recovery.get('boot') != boot
            or not isinstance(proof, dict) or type(proof.get('deadline_ns')) is not int
            or proof['deadline_ns'] <= 0 or proof.get('loader_exits') is not True
            or type(now) is not int or now <= proof['deadline_ns'] or not state.get('restored_identity')):
        raise RuntimeError('SAME_BOOT_EXPIRED_RECOVERY_REQUIRED')


def fingerprint(public_key):
    # Hash the public algorithm/key fields only, not comments or private keys.
    fields = public_key.split()
    if len(fields) < 2 or fields[0] != 'ssh-ed25519': raise RuntimeError('FIXED_PUBLIC_KEY_REQUIRED')
    return hashlib.sha256(' '.join(fields[:2]).encode()).hexdigest()


def emit(b, event, **values):
    print('INBOUND_RESTART_RECORD ' + json.dumps(dict(event=event, boot=b.boot(),
          monotonic=time.monotonic(), activation_allowed=False, **values)), flush=True)


def profile(b, h, g, i):
    try:
        state = b.read('inbound-lease'); recovery = b.read('inbound-recovery')
    except FileNotFoundError as exc:
        raise RuntimeError('COMPLETED_INBOUND_RECOVERY_REQUIRED') from exc
    expired(state, recovery, b.boot(), time.clock_gettime_ns(time.CLOCK_BOOTTIME))
    if h.identity(i) != state['restored_identity']: raise RuntimeError('RESTORED_PROFILE_IDENTITY_REQUIRED')
    tables = json.loads(g.run(g.NFT, '-j', 'list', 'tables'))['nftables']
    actual = {(r['table']['family'], r['table']['name']) for r in tables if 'table' in r}
    if actual != {('inet', i.t.r.TABLE), ('inet', i.OBS)}: raise RuntimeError('UNMASKED_RESTORED_TABLES_REQUIRED')
    return state


def intact(b, h, g, i):
    state = profile(b, h, g, i)
    h.require_seal(h.shape(i), h.rpc(b, 'expected'))
    if any(json.loads(g.run(g.TC, '-j', 'filter', 'show', 'dev', 'host0', direction))
           for direction in ('ingress', 'egress')):
        raise RuntimeError('EXPIRED_TC_FILTERS_MUST_BE_REMOVED')
    blocked = module('inbound_lease', '/inbound_lease.py').probes(g, [])['qualification']
    if blocked != [False, False]: raise RuntimeError('RESTORED_SHUTDOWN_PACKETS_MUST_BE_CLOSED')
    return state, blocked


def main(action):
    b, h, g = context(); _, i, _ = h.context()
    if action in ('restart', 'halt'):
        state, blocked = intact(b, h, g, i)
        if [h.up(i, n) for n in ('host0', 'host1')] != [True, True]: raise RuntimeError('TWO_LIVE_INTERNAL_LINKS_REQUIRED')
        target = {'restart': 'reboot.target', 'halt': 'poweroff.target'}[action]
        persistence = {}
        if Path('/inbound_persistence.py').is_file():
            persistence['persistence'] = module('inbound_persistence', '/inbound_persistence.py').save()
        b.write('inbound-shutdown-request', dict(boot=b.boot(), target=target))
        public = {n: fingerprint((Path('/run/ssh-probe') / (n + '.pub')).read_text()) for n in ('host', 'client')}
        emit(b, 'requested', target=target, qualification=blocked, profile_unchanged=True,
             guards_absent=True, links=[True, True], public_key_sha256=public, deadline_ns=state['proof']['deadline_ns'], **persistence)
        # Actual PID1's normal stop transaction, never forced reboot/QMP reset.
        g.run('/usr/bin/systemctl', '--no-block', 'start', target)
        return
    request = b.read('inbound-shutdown-request')
    if request['boot'] != b.boot() or request['target'] not in ('reboot.target', 'poweroff.target'):
        raise RuntimeError('MATCHED_INBOUND_SHUTDOWN_REQUIRED')
    if action == 'link-down':
        _, blocked = intact(b, h, g, i)
        if [h.up(i, n) for n in ('host0', 'host1')] != [True, True]: raise RuntimeError('LINKS_UP_BEFORE_STOP_REQUIRED')
        for name in ('host0', 'host1'): g.run(g.IP, 'link', 'set', name, 'down')
        links = [h.up(i, n) for n in ('host0', 'host1')]
        if links != [False, False]: raise RuntimeError('BOTH_LINKS_DOWN_REQUIRED')
        _, after = intact(b, h, g, i)
        if not Path('/proc/' + str(b.read('setup')['peer_pid'])).exists(): raise RuntimeError('LINK_DOWN_BEFORE_PEER_STOP_REQUIRED')
        b.write('inbound-shutdown-link', dict(boot=b.boot(), target=request['target'], monotonic=time.monotonic()))
        emit(b, 'link_down', target=request['target'], qualification=blocked, after_down=after,
             profile_unchanged=True, guards_absent=True, links=links, peer_alive=True)
    elif action == 'check':
        link = b.read('inbound-shutdown-link')
        if link['boot'] != b.boot() or link['target'] != request['target']: raise RuntimeError('ORDERED_INBOUND_LINK_STOP_REQUIRED')
        states = {n: b.properties(g, 'kc-' + n) for n in SERVICES}
        for n, state in states.items():
            extra = g.run('/usr/bin/systemctl', 'show', 'kc-' + n + '.service', '--no-pager',
                          '--property=InactiveEnterTimestampMonotonic,Before,Conflicts')
            state.update(dict(line.split('=', 1) for line in extra.decode().splitlines() if '=' in line))
            if state['ActiveState'] != 'inactive' or state['Result'] != 'success':
                raise RuntimeError('ALL_INBOUND_SERVICES_STOPPED_REQUIRED ' + n + ' ' + json.dumps(state))
        # One link-state snapshot avoids racing peer-namespace destruction
        # between an interface-name query and a separate per-link read.
        links = json.loads(g.run(g.IP, '-j', 'link', 'show'))
        if any(r['ifname'] not in ('lo', 'host0', 'host1') or
               (r['ifname'] != 'lo' and 'UP' in r['flags']) for r in links):
            raise RuntimeError('NO_LIVE_INTERNAL_LINK_AFTER_STOP_REQUIRED')
        interfaces = sorted(r['ifname'] for r in links)
        if Path('/proc/' + str(b.read('setup')['peer_pid'])).exists(): raise RuntimeError('INBOUND_PEER_STOP_REQUIRED')
        module('ssh', '/ssh_probe.py').stop_server(None)
        # The peer namespace may have destroyed veths, but the complete inet
        # maintenance profile must remain until the kernel itself reboots.
        profile(b, h, g, i)
        persistence = {}
        if Path('/inbound_persistence.py').is_file():
            persistence['persistence'] = module('persist', '/persist_probe.py').shutdown_check()
        emit(b, 'stopped', target=request['target'], states=states, interfaces=interfaces,
             profile_unchanged=True, guards_absent=True, peer_stopped=True, ssh_stopped=True,
             link_stopped_at=link['monotonic'], **persistence)
    else: raise RuntimeError('FIXED_INBOUND_RESTART_ACTION_REQUIRED')


if __name__ == '__main__':
    try: main(sys.argv[1] if len(sys.argv) == 2 else '')
    except Exception as exc:
        print('INBOUND_RESTART_FAIL ' + repr(exc), flush=True)
        raise

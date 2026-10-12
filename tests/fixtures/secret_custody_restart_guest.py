"""Normal guest-manager shutdown transaction, never host power control."""
import importlib.util
import json
from pathlib import Path
import sys
import time


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def context():
    b = module('boot', '/boot_probe.py'); b.guard()
    flags = Path('/proc/cmdline').read_text().split()
    if flags.count('kc_systemd_restart=1') != 1 or not b.composition():
        raise RuntimeError('ISOLATED_RESTART_OPT_IN_REQUIRED')
    return b, module('packets', '/probe.py'), module('lease', '/lease.py')


def expired(state, boot, now):
    if (state.get('boot') != boot or type(state.get('deadline_ns')) is not int
            or state['deadline_ns'] <= 0 or now <= state['deadline_ns']
            or state.get('boottime_guard', {}).get('deadline_ns') != state['deadline_ns']):
        raise RuntimeError('SAME_BOOT_EXPIRED_IMMUTABLE_LEASE_REQUIRED')


def emit(b, event, **values):
    print('SYSTEMD_RESTART_RECORD ' + json.dumps(dict(event=event, boot=b.boot(),
          monotonic=time.monotonic(), activation_allowed=False, **values)), flush=True)


def intact(b, g, lease):
    state = b.read('lease')
    expired(state, b.boot(), time.clock_gettime_ns(time.CLOCK_BOOTTIME))
    if (g.identity(g.reports(lease)) != state['rule_identity']
            or g.tc_identity(state['boottime_guard']) != state['tc_identity']):
        raise RuntimeError('SHUTDOWN_ORIGINAL_GUARDS_REQUIRED')
    blocked = [g.reaches(a, 443) for a in g.PEERS]
    if blocked != [False, False]: raise RuntimeError('SHUTDOWN_PACKETS_MUST_REMAIN_CLOSED')
    return state, blocked


def main(action):
    b, g, lease = context()
    if action in ('restart', 'halt'):
        state, blocked = intact(b, g, lease)
        target = {'restart': 'reboot.target', 'halt': 'poweroff.target'}[action]
        b.write('shutdown-request', dict(boot=b.boot(), target=target, deadline_ns=state['deadline_ns']))
        emit(b, 'requested', target=target, qualification=blocked, guards_unchanged=True)
        # Starting the installed target asks PID1 for its normal dependency/stop
        # transaction. No force option, host command or QMP reset is used.
        g.run('/usr/bin/systemctl', '--no-block', 'start', target)
        return
    request = b.read('shutdown-request')
    if request['boot'] != b.boot() or request['target'] not in ('reboot.target', 'poweroff.target'):
        raise RuntimeError('MATCHED_SHUTDOWN_REQUEST_REQUIRED')
    if action == 'link-down':
        state, blocked = intact(b, g, lease)
        if not b.link_up(g): raise RuntimeError('LIVE_LINK_BEFORE_ORDERED_STOP_REQUIRED')
        g.run(g.IP, 'link', 'set', 'host0', 'down')
        if b.link_up(g): raise RuntimeError('LINK_DOWN_REQUIRED')
        if g.identity(g.reports(lease)) != state['rule_identity'] or g.tc_identity(state['boottime_guard']) != state['tc_identity']:
            raise RuntimeError('LINK_DOWN_MUST_RETAIN_GUARDS')
        b.write('shutdown-link', dict(boot=b.boot(), monotonic=time.monotonic(), target=request['target']))
        emit(b, 'link_down', target=request['target'], qualification=blocked, guards_unchanged=True, link_up=False)
    elif action == 'check':
        link = b.read('shutdown-link')
        if link['boot'] != b.boot() or link['target'] != request['target']: raise RuntimeError('ORDERED_LINK_STOP_REQUIRED')
        states = {n: b.properties(g, 'kc-' + n) for n in ('report', 'lease', 'auth', 'observe', 'link', 'gate', 'setup')}
        failed = {n: {k: s[k] for k in ('ActiveState', 'Result', 'ExecMainStatus')} for n, s in states.items()
                  if s['ActiveState'] != 'inactive' or s['Result'] != 'success'}
        if failed: raise RuntimeError('ALL_OWNED_SERVICES_STOPPED_REQUIRED ' + json.dumps(failed))
        if 'host0' in g.interfaces() and b.link_up(g): raise RuntimeError('NO_ACTIVE_LINK_AFTER_STOP_REQUIRED')
        if any(n not in ('lo', 'host0') for n in g.interfaces()): raise RuntimeError('INTERNAL_INTERFACES_ONLY')
        if Path('/proc/' + str(b.read('setup')['peer_pid'])).exists(): raise RuntimeError('PEER_PROCESS_STOPPED_REQUIRED')
        module('ssh', '/ssh_probe.py').stop_server(None)
        # Namespace destruction can remove the veth and its TC/netdev hooks.
        # The inet guard must still match; full identities were checked before
        # and after link-down while the interface still existed.
        retained = g.identity([json.loads(g.run(g.NFT, '-j', 'list', 'table', *lease.TABLES[0]))])[0]
        if retained != b.read('lease')['rule_identity'][0]: raise RuntimeError('INET_GUARD_RETAINED_REQUIRED')
        emit(b, 'stopped', target=request['target'], states=states, interfaces=g.interfaces(),
             inet_guard_unchanged=True, peer_stopped=True, ssh_stopped=True, link_stopped_at=link['monotonic'])
    else: raise RuntimeError('FIXED_RESTART_ACTION_REQUIRED')


if __name__ == '__main__':
    try: main(sys.argv[1] if len(sys.argv) == 2 else '')
    except Exception as exc:
        print('SYSTEMD_RESTART_FAIL ' + repr(exc), flush=True)
        raise

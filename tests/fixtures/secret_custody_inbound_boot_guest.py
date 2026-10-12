"""Fixed diskless systemd guest: sealed inbound policy before first link-up.

No live inputs, host installer, lease grant or persistent credentials. The
unfiltered control is a separate disposable boot, never a startup fallback.
"""
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

CASES = ('control', 'closed', 'missing', 'invalid', 'widened')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def units():
    def service(action, dependencies=''):
        return ('[Unit]\nDefaultDependencies=no\n' + dependencies +
                '[Service]\nType=oneshot\nRemainAfterExit=yes\nTimeoutStartSec=90\n'
                'StandardOutput=tty\nStandardError=tty\nTTYPath=/dev/ttyS0\n'
                'ExecStart=/usr/bin/python3 -I -B /inbound_boot.py ' + action + '\n')
    result = {'default.target': '[Unit]\nDefaultDependencies=no\nWants=kc-report.service\n',
              'kc-setup.service': service('setup')}
    for action, dependency in (('gate', 'setup'), ('link', 'gate'), ('check', 'link')):
        result['kc-' + action + '.service'] = service(action,
            'Requires=kc-' + dependency + '.service\nAfter=kc-' + dependency + '.service\n')
    result['kc-report.service'] = service('report', 'Wants=kc-check.service\nAfter=kc-check.service\n') + 'StandardInput=tty\n'
    return result


def context():
    b = module('boot', '/boot_probe.py'); b.guard()
    values = [p.split('=', 1)[1] for p in Path('/proc/cmdline').read_text().split()
              if p.startswith('kc_inbound_boot=')]
    if len(values) != 1 or values[0] not in CASES:
        raise RuntimeError('FIXED_INBOUND_BOOT_OPT_IN_REQUIRED')
    return b, module('inbound', '/tests/test_secret_custody_inbound.py'), values[0]


def rpc(b, *command):
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as s:
        s.settimeout(30); s.connect(str(b.STATE / 'inbound-control'))
        s.sendall(json.dumps(command).encode())
        return json.loads(s.recv(32768))


def up(i, name):
    rows = json.loads(i.t.run(i.t.IP, '-j', 'link', 'show', 'dev', name).stdout)
    if len(rows) != 1: raise RuntimeError('SINGLE_OWNED_LINK_REQUIRED')
    return 'UP' in rows[0]['flags']


def shape(i):
    return i.t.shape(i.t.r.TABLE)


def identity(i):
    rows = json.loads(i.t.run(i.t.NFT, '-j', 'list', 'table', 'inet', i.t.r.TABLE).stdout)['nftables']
    return [r for r in rows if 'metainfo' not in r]


def require_seal(actual, expected):
    if not actual or actual != expected: raise RuntimeError('EXACT_INBOUND_STARTUP_SEAL_REQUIRED')


def peer(b, i):
    os.unshare(os.CLONE_NEWNET)
    b.write('peer-isolated', {'pid': os.getpid()})
    b.wait_file('peer-configure')
    for name in ('peer0', 'peer1'): i.t.run(i.t.IP, 'link', 'set', name, 'addrgenmode', 'none')
    i.t.setup('peer0', i.t.MAC_PEER, ('2', '3', '9'))
    i.t.run(i.t.IP, 'link', 'set', 'peer1', 'address', '02:00:00:00:03:02', 'up')
    for family, prefix in i.t.r.FAMILIES:
        flag = '-6' if family == 'ip6' else '-4'
        for suffix, mac, dev in (('4', i.t.MAC_HOST, 'peer0'), ('1', '02:00:00:00:03:01', 'peer1')):
            i.t.run(i.t.IP, flag, 'neigh', 'replace', prefix + suffix, 'lladdr', mac, 'nud', 'permanent', 'dev', dev)
    # Compile the exact fixed renderer in this independent namespace. It has no
    # external NIC and never supplies operator addresses or live policy input.
    i.t.nft(i.t.r.profile('maintenance')); expected = shape(i)
    i.t.run(i.t.NFT, 'delete', 'table', 'inet', i.t.r.TABLE)
    ssh = module('ssh', '/ssh_probe.py').PeerClients()
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as control:
        control.bind(str(b.STATE / 'inbound-control')); control.listen(4)
        b.write('peer-ready', {'expected': expected})
        while True:
            with control.accept()[0] as request:
                op = json.loads(request.recv(512))
                if op == ['expected']: result = expected
                elif len(op) == 2 and op[0] == 'fresh' and op[1] in i.FLOWS:
                    result = i.fresh(i.FLOWS[op[1]])
                elif len(op) == 2 and op[0] == 'route':
                    i.route(op[1], peer=True); result = True
                elif op == ['ssh-start']: result = ssh.start()
                elif op == ['ssh-check']: result = ssh.check()
                elif op == ['ssh-stop']:
                    ssh.stop(); result = {'stopped': True}
                else: raise RuntimeError('FIXED_INBOUND_PEER_COMMAND_REQUIRED')
                request.sendall(json.dumps(result).encode())


def listeners(b, i):
    with ExitStack() as stack:
        for address in ('0.0.0.0', '::'):
            for protocol, port in i.PORTS:
                if protocol == 'udp': i.udp_listener(stack, address, port)
                else: i.t.listen(stack, address, port)
        b.write('listeners', True)
        while True: time.sleep(1)


def packet_evidence(row, result, before, after, allowed):
    key = row['key']
    early = after['early_' + key] - before['early_' + key]
    late = after['late_' + key] - before['late_' + key]
    if result is not allowed or early <= 0 or (late > 0) is not allowed:
        raise RuntimeError('ACTUAL_INPUT_BOUNDARY_REQUIRED ' + json.dumps(
            dict(key=key, result=result, expected=allowed, early=early, late=late)))
    return dict(key=key, allowed=allowed, result=result, early=early, late=late)


def matrix(b, i, case):
    process = subprocess.Popen(['/usr/bin/python3', '-I', '-B', '/inbound_boot.py', 'listen'],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=sys.stderr)
    rows = []
    try:
        b.wait_file('listeners')
        for row in i.FLOWS.values():
            alternate = row['interface'] == 'host1'
            if alternate: i.route(True); rpc(b, 'route', True)
            try:
                before, _ = i.report(); result = rpc(b, 'fresh', row['key']); after, _ = i.report()
                rows.append(packet_evidence(row, result, before, after, case == 'control' or row['allowed']))
            finally:
                if alternate: i.route(False); rpc(b, 'route', False)
        live = [i.t.reaches(a, port, udp=protocol == 'udp')
                for a in ('127.0.0.1', '::1') for protocol, port in i.PORTS]
        if live != [True] * 16: raise RuntimeError('ACTIVE_WILDCARD_LISTENERS_REQUIRED')
        return dict(packets=rows, loopback=live)
    finally:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        if Path('/proc/' + str(process.pid)).exists(): raise RuntimeError('LISTENER_CLEANUP_REQUIRED')


def emit(b, event, case, **values):
    print('INBOUND_BOOT_RECORD ' + json.dumps(dict(event=event, case=case, boot=b.boot(),
          pid1=Path('/proc/1/comm').read_text().strip(), monotonic=time.monotonic(), **values)), flush=True)


def main(action):
    b, i, case = context()
    g = module('packets', '/probe.py')
    if action == 'peer': peer(b, i); return
    if action == 'listen': listeners(b, i); return
    if action == 'setup':
        if g.interfaces() != ['lo'] or b.STATE.exists(): raise RuntimeError('FRESH_INBOUND_BOOT_REQUIRED')
        b.STATE.mkdir(mode=0o700)
        g.run('/sbin/modprobe', '-C', '/module-config', '-a', 'ipv6', 'veth', 'nf_tables')
        if [r for r in json.loads(g.run(g.NFT, '-j', 'list', 'ruleset'))['nftables'] if 'metainfo' not in r]:
            raise RuntimeError('EMPTY_INBOUND_BOOT_RULESET_REQUIRED')
        module('ssh', '/ssh_probe.py').prepare(systemd=True)
        subprocess.Popen(['/usr/bin/python3', '-I', '-B', '/inbound_boot.py', 'peer'],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=sys.stderr)
        b.wait_file('peer-isolated'); pid = b.read('peer-isolated')['pid']
        if os.readlink(f'/proc/{pid}/ns/net') == os.readlink('/proc/self/ns/net'):
            raise RuntimeError('DISTINCT_INBOUND_PEER_REQUIRED')
        for suffix, mac in (('0', i.t.MAC_HOST), ('1', '02:00:00:00:03:01')):
            g.run(g.IP, 'link', 'add', 'host' + suffix, 'type', 'veth', 'peer', 'name', 'peer' + suffix)
            g.run(g.IP, 'link', 'set', 'peer' + suffix, 'netns', str(pid))
            g.run(g.IP, 'link', 'set', 'host' + suffix, 'address', mac, 'addrgenmode', 'none')
        g.setup('host0', 1, up=False)
        g.run(g.IP, 'addr', 'add', '192.0.2.4/24', 'dev', 'host0')
        g.run(g.IP, '-6', 'addr', 'add', '2001:db8:1::4/64', 'dev', 'host0', 'nodad')
        for family, prefix in i.t.r.FAMILIES:
            flag = '-6' if family == 'ip6' else '-4'
            for suffix in ('2', '3', '9'):
                g.run(g.IP, flag, 'neigh', 'replace', prefix + suffix, 'lladdr', i.t.MAC_PEER, 'nud', 'permanent', 'dev', 'host0')
            g.run(g.IP, flag, 'neigh', 'replace', prefix + '2', 'lladdr', '02:00:00:00:03:02', 'nud', 'permanent', 'dev', 'host1')
        b.write('peer-configure', True); b.wait_file('peer-ready')
        if any(up(i, n) for n in ('host0', 'host1')): raise RuntimeError('BOTH_STARTUP_LINKS_DOWN_REQUIRED')
        b.write('setup', dict(boot=b.boot(), peer_pid=pid))
    elif action == 'gate':
        if any(up(i, n) for n in ('host0', 'host1')): raise RuntimeError('GATE_BEFORE_LINK_REQUIRED')
        i.t.nft(i.observer())
        if case != 'control':
            text = i.t.r.profile('maintenance')
            if case == 'invalid': text += 'add rule inet kc_missing missing counter drop\n'
            if case != 'missing': i.t.nft(text)
            if case == 'widened': i.t.nft(f'insert rule inet {i.t.r.TABLE} input tcp dport 8080 accept\n')
            require_seal(shape(i), rpc(b, 'expected'))
        b.write('gate', dict(boot=b.boot(), sealed_ns=time.monotonic_ns(), links_down=True,
                            identity=identity(i) if case != 'control' else None))
    elif action == 'link':
        b.write('link-entered', True)
        sealed = b.read('gate')
        if sealed['boot'] != b.boot() or any(up(i, n) for n in ('host0', 'host1')):
            raise RuntimeError('SAME_CLOSED_STARTUP_REQUIRED')
        if case != 'control':
            require_seal(shape(i), rpc(b, 'expected'))
            if identity(i) != sealed['identity']: raise RuntimeError('SEALED_IDENTITY_CHANGED')
        for name in ('host0', 'host1'): g.run(g.IP, 'link', 'set', name, 'up')
        b.write('link', dict(boot=b.boot(), up_ns=time.monotonic_ns()))
    elif action == 'check':
        if case not in ('closed', 'control'): raise RuntimeError('FAILED_GATE_MUST_PREVENT_CHECK')
        result = matrix(b, i, case)
        if case == 'closed':
            ssh = module('ssh', '/ssh_probe.py'); server = ssh.start_server(systemd=True)
            try:
                result['ssh_ready'] = rpc(b, 'ssh-start')
                result['ssh_after'] = rpc(b, 'ssh-check')
            finally:
                rpc(b, 'ssh-stop'); ssh.stop_server(server)
            require_seal(shape(i), rpc(b, 'expected'))
            result['identity_unchanged'] = identity(i) == b.read('gate')['identity']
            if not result['identity_unchanged']: raise RuntimeError('AUTHENTICATED_POLICY_IDENTITY_REQUIRED')
        b.write('check', result)
    elif action == 'report':
        states = {n: b.properties(g, 'kc-' + n) for n in ('setup', 'gate', 'link', 'check')}
        emit(b, 'observed', case, states=states, links=[up(i, n) for n in ('host0', 'host1')],
             link_entered=(b.STATE / 'link-entered').exists(),
             sealed=b.read('gate') if (b.STATE / 'gate').exists() else None,
             linked=b.read('link') if (b.STATE / 'link').exists() else None,
             checked=b.read('check') if (b.STATE / 'check').exists() else None,
             activation_allowed=False)
        if sys.stdin.readline(8).strip() != 'clean': raise RuntimeError('FIXED_INBOUND_CLEANUP_REQUIRED')
        pid = b.read('setup')['peer_pid']
        g.run('/usr/bin/systemctl', 'stop', 'kc-check.service', 'kc-link.service', 'kc-gate.service', 'kc-setup.service')
        for table in (i.t.r.TABLE, i.OBS): i.t.run(i.t.NFT, 'delete', 'table', 'inet', table, success=False)
        for name in ('host0', 'host1'):
            if name in g.interfaces(): g.run(g.IP, 'link', 'del', name)
        remaining = [r for r in json.loads(g.run(g.NFT, '-j', 'list', 'ruleset'))['nftables'] if 'metainfo' not in r]
        module('ssh', '/ssh_probe.py').stop_server(None)
        if remaining or g.interfaces() != ['lo'] or Path(f'/proc/{pid}').exists():
            raise RuntimeError('INBOUND_BOOT_CLEANUP_REQUIRED')
        emit(b, 'done', case, interfaces=g.interfaces(), activation_allowed=False)
        while True: time.sleep(1)
    else: raise RuntimeError('FIXED_INBOUND_BOOT_ACTION_REQUIRED')


if __name__ == '__main__':
    try: main(sys.argv[1] if len(sys.argv) == 2 else '')
    except Exception as exc:
        print('INBOUND_BOOT_STAGE_ERROR ' + repr(exc), flush=True)
        raise

"""Real systemd guest boot ordering, fixed internal packets and guest reboot."""
import importlib.util
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import time

STATE = Path('/run/kc-boot')


def guard():
    if (os.geteuid() != 0 or os.getpid() == 1
            or Path('/proc/1/comm').read_text().strip() != 'systemd'
            or ' kc_systemd_probe=1 ' not in Path('/proc/cmdline').read_text()
            or Path('/sys/class/dmi/id/sys_vendor').read_text().strip() != 'QEMU'):
        raise RuntimeError('ISOLATED_SYSTEMD_GUEST_REQUIRED')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def wait_file(name):
    limit = time.monotonic() + 10
    while time.monotonic() < limit:
        if (STATE / name).is_file(): return
        time.sleep(.02)
    raise RuntimeError('PEER_MARKER_TIMEOUT ' + name)


def boot():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def write(name, value):
    (STATE / name).write_text(json.dumps(value))


def read(name):
    return json.loads((STATE / name).read_text())


def link_up(g):
    rows = json.loads(g.run(g.IP, '-j', 'link', 'show', 'dev', 'host0'))
    if len(rows) != 1: raise RuntimeError('SINGLE_INTERNAL_LINK_REQUIRED')
    return 'UP' in rows[0]['flags']


def peer(g):
    os.unshare(os.CLONE_NEWNET)
    write('peer-isolated', {'pid': os.getpid()})
    wait_file('peer-configure')
    g.setup('peer0', 2)
    if g.interfaces() != ['lo', 'peer0']: raise RuntimeError('INTERNAL_PEER_ONLY')
    servers, clients = [], []
    for address in g.PEERS:
        for port in (22, 443):
            s = socket.socket(socket.AF_INET6 if ':' in address else socket.AF_INET, socket.SOCK_STREAM)
            s.bind((address, port)); s.listen(8); servers.append(s)
    write('peer-ready', True)
    while True:
        ready, _, _ = select.select(servers + clients, [], [], 1)
        for s in ready:
            if s in servers:
                child, _ = s.accept(); child.settimeout(.25); clients.append(child)
            else:
                try:
                    data = s.recv(64)
                    if data: s.sendall(data); continue
                except OSError: pass
                clients.remove(s); s.close()


def properties(g, unit):
    result = g.run('/usr/bin/systemctl', 'show', unit + '.service', '--no-pager',
                   '--property=ActiveState,SubState,Result,ExecMainStatus,ExecMainStartTimestampMonotonic,ExecMainExitTimestampMonotonic,Requires,After')
    return dict(line.split('=', 1) for line in result.decode().splitlines() if '=' in line)


def emit(event, mode, **values):
    print('SYSTEMD_BOOT_RECORD ' + json.dumps(dict(event=event, mode=mode, boot=boot(),
          pid1=Path('/proc/1/comm').read_text().strip(), monotonic=time.monotonic(), **values)), flush=True)


def main(action):
    guard()
    g = module('packets', '/probe.py')
    policy = module('policy', '/startup_policy.py')
    modes = [part.split('=', 1)[1] for part in Path('/proc/cmdline').read_text().split() if part.startswith('kc_boot_case=')]
    if len(modes) != 1 or modes[0] not in ('closed', 'missing', 'invalid'): raise RuntimeError('FIXED_BOOT_CASE_REQUIRED')
    mode = modes[0]
    if action == 'peer': peer(g); return
    if action == 'setup':
        if g.interfaces() != ['lo'] or STATE.exists(): raise RuntimeError('FRESH_BOOT_REQUIRED')
        STATE.mkdir(mode=0o700)
        g.run('/sbin/modprobe', '-C', '/module-config', '-a', 'ipv6', 'veth', 'nf_tables')
        if [r for r in json.loads(g.run(g.NFT, '-j', 'list', 'ruleset'))['nftables'] if 'metainfo' not in r]:
            raise RuntimeError('EMPTY_BOOT_RULESET_REQUIRED')
        subprocess.Popen(['/usr/bin/python3', '-I', '-B', '/boot_probe.py', 'peer'],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=sys.stderr)
        wait_file('peer-isolated'); pid = read('peer-isolated')['pid']
        if os.readlink(f'/proc/{pid}/ns/net') == os.readlink('/proc/self/ns/net'): raise RuntimeError('PEER_NAMESPACE_REQUIRED')
        g.run(g.IP, 'link', 'add', 'host0', 'type', 'veth', 'peer', 'name', 'peer0')
        g.run(g.IP, 'link', 'set', 'peer0', 'netns', str(pid))
        g.setup('host0', 1, up=False)
        write('peer-configure', True); wait_file('peer-ready')
        if link_up(g): raise RuntimeError('SETUP_LINK_DOWN_REQUIRED')
        write('setup', {'boot': boot(), 'fresh': True, 'peer_pid': pid})
    elif action == 'gate':
        if link_up(g) or read('setup')['boot'] != boot(): raise RuntimeError('CLOSED_GATE_PRECONDITION')
        text = policy.install()
        if mode == 'invalid': text += 'add rule inet kc_missing missing counter drop\n'
        if mode != 'missing': g.run(g.NFT, '-f', '-', input=text.encode())
        seal = policy.seal(json.loads(g.run(g.NFT, '-j', 'list', 'table', 'inet', policy.TABLE)))
        write('gate', {'boot': boot(), 'seal': seal, 'sealed_ns': time.monotonic_ns(), 'link_up': link_up(g)})
    elif action == 'link':
        write('link-entered', True)
        sealed = read('gate')
        if (sealed['boot'] != boot() or sealed['link_up'] is not False or link_up(g)
                or policy.seal(json.loads(g.run(g.NFT, '-j', 'list', 'table', 'inet', policy.TABLE))) != sealed['seal']):
            raise RuntimeError('SEALED_POLICY_BEFORE_LINK_REQUIRED')
        g.run(g.IP, 'link', 'set', 'host0', 'up')
        write('link', {'boot': boot(), 'up_ns': time.monotonic_ns()})
    elif action == 'report':
        states = {n: properties(g, 'kc-' + n) for n in ('setup', 'gate', 'link')}
        qualification = [g.reaches(a, 443) for a in g.PEERS]
        management = [g.reaches(a, 22) for a in g.PEERS]
        sealed = read('gate') if (STATE / 'gate').exists() else None
        rules = [r for r in json.loads(g.run(g.NFT, '-j', 'list', 'ruleset'))['nftables'] if 'metainfo' not in r]
        emit('observed', mode, states=states, link_up=link_up(g), link_entered=(STATE / 'link-entered').exists(),
             qualification=qualification, management=management, fresh=read('setup')['fresh'],
             sealed=sealed, linked=read('link') if (STATE / 'link').exists() else None,
             policy_unchanged=policy.seal({'nftables': rules}) == sealed['seal'] if sealed else None,
             ruleset_empty=not rules)
        command = sys.stdin.readline(8).strip()
        if command == 'reboot' and mode == 'closed':
            emit('reboot_requested', mode)
            # Ask the actual guest PID1 to reboot; no host power operation.
            g.run('/usr/bin/systemctl', 'reboot', '--force')
        elif command == 'clean':
            pid = read('setup')['peer_pid']
            g.run('/usr/bin/systemctl', 'stop', 'kc-link.service', 'kc-gate.service', 'kc-setup.service')
            subprocess.run([g.NFT, 'delete', 'table', 'inet', policy.TABLE], capture_output=True, timeout=5)
            if 'host0' in g.interfaces(): g.run(g.IP, 'link', 'del', 'host0')
            remaining = [r for r in json.loads(g.run(g.NFT, '-j', 'list', 'ruleset'))['nftables'] if 'metainfo' not in r]
            if remaining or g.interfaces() != ['lo'] or Path(f'/proc/{pid}').exists(): raise RuntimeError('BOOT_CLEANUP_REQUIRED')
            emit('done', mode, interfaces=g.interfaces(), activation_allowed=False)
        else: raise RuntimeError('FIXED_GUEST_COMMAND_REQUIRED')
        while True: time.sleep(1)
    else: raise RuntimeError('FIXED_SERVICE_ACTION_REQUIRED')


if __name__ == '__main__':
    try: main(sys.argv[1] if len(sys.argv) == 2 else '')
    except Exception as exc:
        print('SYSTEMD_BOOT_STAGE_ERROR ' + repr(exc), flush=True)
        raise

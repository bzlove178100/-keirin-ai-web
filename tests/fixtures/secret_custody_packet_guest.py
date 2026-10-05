"""Fixed guest-only packet experiment. Never a host installer or activation."""
import importlib.util
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import time

IP, NFT = '/usr/sbin/ip', '/usr/sbin/nft'
PEERS = ('192.0.2.2', '2001:db8:1::2')
UNRELATED = 'kc_vm_unrelated'
sequence = 0


def run(*args, input=None):
    result = subprocess.run(args, input=input, capture_output=True, timeout=8)
    if result.returncode:
        raise RuntimeError('GUEST_COMMAND_FAILED ' + repr(args) + ' ' + result.stderr.decode(errors='replace')[-2000:])
    return result.stdout


def clocks():
    return {'monotonic': time.monotonic(), 'boottime': time.clock_gettime(time.CLOCK_BOOTTIME)}


def emit(event, **values):
    row = dict(event=event, boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
               interfaces=sorted(p.name for p in Path('/sys/class/net').iterdir()),
               marker=int(Path('/run/probe.marker').exists()), **values)
    print('PACKET_RECORD ' + json.dumps(row), flush=True)


def setup(name, number):
    run(IP, 'link', 'set', name, 'addrgenmode', 'none')
    run(IP, 'addr', 'add', f'192.0.2.{number}/24', 'dev', name)
    run(IP, '-6', 'addr', 'add', f'2001:db8:1::{number}/64', 'dev', name, 'nodad')
    run(IP, 'link', 'set', name, 'up')
    run(IP, 'link', 'set', 'lo', 'up')


def peer(control):
    os.unshare(os.CLONE_NEWNET)
    control.sendall(b'isolated\n')
    if control.recv(16) != b'setup\n':
        raise RuntimeError('PEER_SETUP_REQUIRED')
    setup('peer0', 2)
    if sorted(p.name for p in Path('/sys/class/net').iterdir()) != ['lo', 'peer0']:
        raise RuntimeError('FIXED_PEER_INTERFACES_REQUIRED')
    servers, clients = [], []
    for address in PEERS:
        for port in (22, 443):
            s = socket.socket(socket.AF_INET6 if ':' in address else socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((address, port)); s.listen(16); servers.append(s)
    control.sendall(b'ready\n')
    while True:
        readable, _, _ = select.select([control, *servers, *clients], [], [], 1)
        for s in readable:
            if s is control:
                return
            if s in servers:
                child, _ = s.accept(); child.settimeout(.25); clients.append(child)
            else:
                try:
                    data = s.recv(64)
                    if data:
                        s.sendall(data)
                        continue
                except OSError:
                    pass
                clients.remove(s); s.close()


def connect(address, port):
    s = socket.socket(socket.AF_INET6 if ':' in address else socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(.25)
    try:
        s.connect((address, port))
        return s
    except Exception:
        s.close()
        raise


def exchange(s):
    global sequence
    sequence += 1
    token = sequence.to_bytes(8, 'big')
    try:
        s.sendall(token)
        return s.recv(8) == token
    except OSError:
        return False


def reaches(address, port):
    try:
        with connect(address, port) as s:
            return exchange(s)
    except OSError:
        return False


def probes(old_qualification, old_management):
    # Qualification packets are the first network actions after resume. No nft
    # read/write, renewal, restoration worker or controller runs ahead of them.
    qualification = [exchange(s) for s in old_qualification] + [reaches(a, 443) for a in PEERS]
    management = [exchange(s) for s in old_management] + [reaches(a, 22) for a in PEERS]
    return {'qualification': qualification, 'management': management,
            'probe_finished_monotonic': time.monotonic()}


def reports(lease):
    return [json.loads(run(NFT, '-j', 'list', 'table', family, name)) for family, name in lease.TABLES]


def identity(reports):
    # Ignore only measurements (counters and element presence/expiry), retaining
    # handles, rules, set timeout, hooks, interface match and all other fields.
    value = json.loads(json.dumps(reports))
    for report in value:
        report['nftables'] = [r for r in report['nftables'] if 'metainfo' not in r]
        for row in report['nftables']:
            if 'set' in row:
                row['set'].pop('elem', None)
            if 'rule' in row:
                for expr in row['rule']['expr']:
                    if 'counter' in expr:
                        expr['counter'].pop('packets', None); expr['counter'].pop('bytes', None)
    return value


def require(values, expected):
    if values['qualification'] != [expected] * 4 or values['management'] != [True] * 4:
        raise RuntimeError('PACKET_CONTROL_REQUIRED ' + json.dumps(values))


def main():
    if (os.getpid() != 1 or os.geteuid() != 0 or ' kc_packet_probe=1 ' not in Path('/proc/cmdline').read_text()
            or Path('/sys/class/dmi/id/sys_vendor').read_text().strip() != 'QEMU'
            or sorted(p.name for p in Path('/sys/class/net').iterdir()) != ['lo']):
        raise RuntimeError('FIXED_PACKET_GUEST_REQUIRED')
    mode = sys.stdin.readline(16).strip()
    if mode not in ('awake', 'suspend'):
        raise RuntimeError('FIXED_PACKET_CASE_REQUIRED')
    spec = importlib.util.spec_from_file_location('lease', '/lease.py')
    lease = importlib.util.module_from_spec(spec); spec.loader.exec_module(lease)
    run('/sbin/modprobe', '-C', '/module-config', '-a', 'ipv6', 'veth', 'nf_tables', 'nft_counter')
    if [r for r in json.loads(run(NFT, '-j', 'list', 'ruleset'))['nftables'] if 'metainfo' not in r]:
        raise RuntimeError('EMPTY_GUEST_RULESET_REQUIRED')
    parent, child = socket.socketpair(type=socket.SOCK_SEQPACKET)
    pid = os.fork()
    if pid == 0:
        parent.close()
        try:
            peer(child)
            os._exit(0)
        except Exception as exc:
            print('PACKET_FAIL peer ' + str(exc), flush=True)
            os._exit(2)
    child.close(); parent.settimeout(8)
    opened = []
    try:
        if parent.recv(32) != b'isolated\n' or os.readlink(f'/proc/{pid}/ns/net') == os.readlink('/proc/self/ns/net'):
            raise RuntimeError('DISTINCT_PEER_NAMESPACE_REQUIRED')
        run(IP, 'link', 'add', 'host0', 'type', 'veth', 'peer', 'name', 'peer0')
        run(IP, 'link', 'set', 'peer0', 'netns', str(pid))
        setup('host0', 1)
        parent.sendall(b'setup\n')
        if parent.recv(32) != b'ready\n':
            raise RuntimeError('PEER_READY_REQUIRED')
        # Fresh boot WITHOUT a policy is an explicit open negative control.
        startup = [reaches(a, port) for port in (443, 22) for a in PEERS]
        if startup != [True] * 4:
            raise RuntimeError('UNFILTERED_STARTUP_POSITIVE_REQUIRED')
        emit('startup_unprotected', mode=mode, new_connections=startup, **clocks())
        old_q = [connect(a, 443) for a in PEERS]; opened.extend(old_q)
        old_m = [connect(a, 22) for a in PEERS]; opened.extend(old_m)
        require(probes(old_q, old_m), True)
        run(NFT, '-f', '-', input=f'table inet {UNRELATED} {{ chain sentinel {{ counter drop; }}; }}\n'.encode())
        unrelated = json.loads(run(NFT, '-j', 'list', 'table', 'inet', UNRELATED))
        started = clocks()
        run(NFT, '-f', '-', input=lease.install(socket.if_nametoindex('host0')).encode())
        initial = reports(lease)
        lease.snapshot(initial) # Real live fixed renderer policy and set required.
        original = identity(initial)
        require(probes(old_q, old_m), True)
        before = clocks()
        if before['monotonic'] - started['monotonic'] >= 3:
            raise RuntimeError('LIVE_PRE_SUSPEND_WINDOW_REQUIRED')
        emit('before', mode=mode, lease_start=started, **before)
        if mode == 'suspend':
            if 'deep' not in Path('/sys/power/mem_sleep').read_text():
                raise RuntimeError('ACTUAL_DEEP_SUSPEND_REQUIRED')
            Path('/sys/power/mem_sleep').write_text('deep')
            Path('/sys/power/state').write_text('mem')
        else:
            time.sleep(10)
        after = clocks()
        observed = probes(old_q, old_m)
        unchanged = identity(reports(lease)) == original and json.loads(run(NFT, '-j', 'list', 'table', 'inet', UNRELATED)) == unrelated
        if not unchanged or observed['management'] != [True] * 4:
            raise RuntimeError('RULE_IDENTITY_AND_MANAGEMENT_REQUIRED')
        if mode == 'awake':
            require(observed, False)
            outcome = 'AWAKE_EXPIRY_CONFIRMED'
        else:
            if observed['probe_finished_monotonic'] - started['monotonic'] >= 7:
                raise RuntimeError('FIRST_RESUME_PROBE_WINDOW_REQUIRED')
            if observed['qualification'] == [True] * 4:
                outcome = 'BLOCKED_SUSPEND_EXPIRY_GAP'
            elif observed['qualification'] == [False] * 4:
                outcome = 'SUSPEND_EXPIRY_OBSERVED'
            else:
                raise RuntimeError('MIXED_RESUME_OBSERVATION ' + json.dumps(observed))
        emit('after', mode=mode, outcome=outcome, rule_identity_unchanged=unchanged, **after, **observed)
        time.sleep(max(0, started['monotonic'] + 10 - time.monotonic()))
        late = probes(old_q, old_m)
        require(late, False)
        if identity(reports(lease)) != original:
            raise RuntimeError('LATE_RULE_IDENTITY_REQUIRED')
        emit('awake_expired', mode=mode, **late, **clocks())
    finally:
        for s in opened: s.close()
        parent.close()
        os.kill(pid, signal.SIGTERM); os.waitpid(pid, 0)
        for family, name in (*lease.TABLES, ('inet', UNRELATED)):
            subprocess.run([NFT, 'delete', 'table', family, name], capture_output=True, timeout=5)
        subprocess.run([IP, 'link', 'del', 'host0'], capture_output=True, timeout=5)
    remaining = [r for r in json.loads(run(NFT, '-j', 'list', 'ruleset'))['nftables'] if 'metainfo' not in r]
    if remaining or Path(f'/proc/{pid}').exists() or sorted(p.name for p in Path('/sys/class/net').iterdir()) != ['lo']:
        raise RuntimeError('GUEST_CLEANUP_REQUIRED')
    emit('done', mode=mode, outcome=outcome, activation_allowed=False, **clocks())
    while True: time.sleep(1) # PID 1 remains alive until its owned VM is reaped.


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('PACKET_FAIL ' + repr(error), flush=True)
        raise

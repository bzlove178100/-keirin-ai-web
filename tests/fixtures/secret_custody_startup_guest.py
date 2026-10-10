"""Disposable PID1-only closed-startup experiment; no external NIC or live use."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def main():
    # Refuse before any network mutation or loading guest-only helper paths.
    if (os.getpid() != 1 or os.geteuid() != 0
            or ' kc_startup_probe=1 ' not in Path('/proc/cmdline').read_text()
            or Path('/sys/class/dmi/id/sys_vendor').read_text().strip() != 'QEMU'
            or sorted(n for _, n in socket.if_nameindex()) != ['lo']):
        raise RuntimeError('FIXED_STARTUP_GUEST_REQUIRED')
    g = module('packets', '/packets.py')
    policy = module('startup_policy', '/startup_policy.py')
    mode = g.sys.stdin.readline(32).strip()
    if mode not in ('closed', 'missing', 'invalid', 'open'):
        raise RuntimeError('FIXED_STARTUP_CASE_REQUIRED')
    g.run('/sbin/modprobe', '-C', '/module-config', '-a', 'ipv6', 'veth', 'nf_tables')
    if [r for r in json.loads(g.run(g.NFT, '-j', 'list', 'ruleset'))['nftables'] if 'metainfo' not in r]:
        raise RuntimeError('EMPTY_STARTUP_RULESET_REQUIRED')
    parent, child = socket.socketpair(type=socket.SOCK_SEQPACKET)
    pid = os.fork()
    if pid == 0:
        parent.close()
        try:
            g.peer(child); os._exit(0)
        except Exception as exc:
            print('PACKET_FAIL peer ' + repr(exc), flush=True); os._exit(2)
    child.close(); parent.settimeout(8)

    def link_up():
        rows = json.loads(g.run(g.IP, '-j', 'link', 'show', 'dev', 'host0'))
        if len(rows) != 1 or rows[0]['ifname'] != 'host0':
            raise RuntimeError('FIXED_STARTUP_LINK_REQUIRED')
        return 'UP' in rows[0]['flags']

    def read_policy():
        return json.loads(g.run(g.NFT, '-j', 'list', 'table', 'inet', policy.TABLE))

    try:
        if parent.recv(32) != b'isolated\n' or os.readlink(f'/proc/{pid}/ns/net') == os.readlink('/proc/self/ns/net'):
            raise RuntimeError('DISTINCT_STARTUP_PEER_REQUIRED')
        g.run(g.IP, 'link', 'add', 'host0', 'type', 'veth', 'peer', 'name', 'peer0')
        g.run(g.IP, 'link', 'set', 'peer0', 'netns', str(pid))
        # Configure fixed addresses while the host end remains administratively DOWN.
        g.run(g.IP, 'link', 'set', 'host0', 'addrgenmode', 'none')
        g.run(g.IP, 'addr', 'add', '192.0.2.1/24', 'dev', 'host0')
        g.run(g.IP, '-6', 'addr', 'add', '2001:db8:1::1/64', 'dev', 'host0', 'nodad')
        g.run(g.IP, 'link', 'set', 'lo', 'up')
        parent.sendall(b'setup\n')
        if parent.recv(32) != b'ready\n' or link_up():
            raise RuntimeError('PEER_READY_HOST_LINK_DOWN_REQUIRED')
        g.emit('startup_down', mode=mode, link_up=False, **g.clocks())
        original = None
        error = None
        try:
            if mode in ('closed', 'invalid'):
                text = policy.install()
                if mode == 'invalid':
                    # Real rejected nft transaction; no mock/readiness boolean.
                    text += 'add rule inet kc_nonexistent nonexistent counter drop\n'
                g.run(g.NFT, '-f', '-', input=text.encode())
            if mode != 'open':
                original = policy.seal(read_policy())
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            error = str(exc)
        if mode in ('missing', 'invalid'):
            if error is None or link_up():
                raise RuntimeError('STARTUP_FAILURE_MUST_RETAIN_DOWN_LINK')
            remaining = [r for r in json.loads(g.run(g.NFT, '-j', 'list', 'ruleset'))['nftables'] if 'metainfo' not in r]
            if remaining:
                raise RuntimeError('FAILED_TRANSACTION_MUST_LEAVE_NO_POLICY')
            g.emit('startup_rejected', mode=mode, link_up=False,
                   reason='missing_policy' if mode == 'missing' else 'install_failed',
                   ruleset_empty=True, **g.clocks())
            result = 'STARTUP_REFUSED_LINK_DOWN'
        else:
            if error is not None:
                raise RuntimeError(error)
            if link_up():
                raise RuntimeError('POLICY_BEFORE_FIRST_LINK_UP_REQUIRED')
            g.emit('startup_ready', mode=mode, link_up=False, closed_policy=original is not None, **g.clocks())
            g.run(g.IP, 'link', 'set', 'host0', 'up')
            if not link_up():
                raise RuntimeError('STARTUP_LINK_UP_REQUIRED')
            # First application probes after link-up; no policy mutation occurs.
            qualification = [g.reaches(a, 443) for a in g.PEERS]
            management = [g.reaches(a, 22) for a in g.PEERS]
            unchanged = policy.seal(read_policy()) == original if mode == 'closed' else None
            if qualification != [mode == 'open'] * 2 or management != [True] * 2:
                raise RuntimeError('STARTUP_PACKET_CONTROL_REQUIRED')
            if mode == 'closed' and unchanged is not True:
                raise RuntimeError('STARTUP_POLICY_IDENTITY_REQUIRED')
            result = 'CLOSED_BEFORE_LINK_OBSERVED' if mode == 'closed' else 'UNPROTECTED_STARTUP_DETECTED'
            g.emit('startup_packets', mode=mode, link_up=True, qualification=qualification,
                   management=management, policy_unchanged=unchanged, outcome=result, **g.clocks())
    finally:
        parent.close(); os.kill(pid, signal.SIGTERM); os.waitpid(pid, 0)
        subprocess.run([g.NFT, 'delete', 'table', 'inet', policy.TABLE], capture_output=True, timeout=5)
        subprocess.run([g.IP, 'link', 'del', 'host0'], capture_output=True, timeout=5)
    remaining = [r for r in json.loads(g.run(g.NFT, '-j', 'list', 'ruleset'))['nftables'] if 'metainfo' not in r]
    if remaining or Path(f'/proc/{pid}').exists() or g.interfaces() != ['lo']:
        raise RuntimeError('STARTUP_GUEST_CLEANUP_REQUIRED')
    g.emit('done', mode=mode, outcome=result, activation_allowed=False, **g.clocks())
    while True: time.sleep(1)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('PACKET_FAIL ' + repr(exc), flush=True)
        raise

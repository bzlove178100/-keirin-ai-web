"""Ephemeral OpenSSH inside a diskless guest only; never a host SSH installer."""
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import time

ADDRESSES = ('192.0.2.1', '2001:db8:1::1')
ROOT = Path('/run/ssh-probe')


def guest_guard():
    if (os.getpid() != 1 or os.geteuid() != 0
            or ' kc_ssh_probe=1 ' not in Path('/proc/cmdline').read_text()
            or Path('/sys/class/dmi/id/sys_vendor').read_text().strip() != 'QEMU'):
        raise RuntimeError('FIXED_SSH_GUEST_REQUIRED')


def configuration():
    return '''Port 22
ListenAddress 192.0.2.1
ListenAddress 2001:db8:1::1
HostKey /run/ssh-probe/host
PidFile /run/ssh-probe/sshd.pid
AuthorizedKeysFile /run/ssh-probe/authorized_keys
PermitRootLogin forced-commands-only
PubkeyAuthentication yes
AuthenticationMethods publickey
PasswordAuthentication no
KbdInteractiveAuthentication no
HostbasedAuthentication no
UsePAM no
UseDNS no
StrictModes yes
AllowUsers root
DisableForwarding yes
PermitTTY no
PermitUserRC no
LoginGraceTime 10
MaxAuthTries 1
LogLevel ERROR
'''


def prepare():
    guest_guard()
    ROOT.mkdir(mode=0o700)
    Path('/run/sshd').mkdir(mode=0o755)
    # All material is generated afresh inside this VM, never on CI's host.
    for name in ('host', 'client', 'wrong'):
        subprocess.run(['/usr/bin/ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(ROOT / name)],
                       check=True, capture_output=True, timeout=10)
    key = (ROOT / 'client.pub').read_text().strip()
    (ROOT / 'authorized_keys').write_text('restrict,command="/usr/bin/python3 -I -B /ssh_echo.py" ' + key + '\n')
    (ROOT / 'authorized_keys').chmod(0o600)
    for name, pub in (('known_hosts', 'host.pub'), ('wrong_hosts', 'wrong.pub')):
        key = ' '.join((ROOT / pub).read_text().split()[:2])
        (ROOT / name).write_text('\n'.join(address + ' ' + key for address in ADDRESSES) + '\n')
    (ROOT / 'config').write_text(configuration())


def start_server():
    guest_guard()
    args = ['/usr/sbin/sshd', '-f', str(ROOT / 'config')]
    subprocess.run(args + ['-t'], check=True, capture_output=True, timeout=5)
    log = (ROOT / 'server.log').open('wb')
    server = subprocess.Popen(args + ['-D', '-e'], stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=log, start_new_session=True)
    log.close()
    # Bounded readiness, not authentication evidence. The peer's real SSH
    # exchanges and wrong-key controls below establish authentication.
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError('SSH_SERVER_START_FAILED ' + (ROOT / 'server.log').read_text()[-1500:])
        if (ROOT / 'sshd.pid').exists(): return server
        time.sleep(.02)
    raise RuntimeError('SSH_SERVER_READINESS_TIMEOUT')


def client_args(address, key='client', hosts='known_hosts'):
    if address not in ADDRESSES or key not in ('client', 'wrong') or hosts not in ('known_hosts', 'wrong_hosts'):
        raise ValueError('FIXED_SSH_CLIENT_REQUIRED')
    return ['/usr/bin/ssh', '-F', '/dev/null', '-T', '-o', 'BatchMode=yes',
            '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none',
            '-o', 'StrictHostKeyChecking=yes', '-o', 'GlobalKnownHostsFile=/dev/null',
            '-o', 'UserKnownHostsFile=' + str(ROOT / hosts),
            '-o', 'UpdateHostKeys=no', '-o', 'PreferredAuthentications=publickey',
            '-o', 'PasswordAuthentication=no', '-o', 'KbdInteractiveAuthentication=no',
            '-o', 'ConnectTimeout=5', '-o', 'ConnectionAttempts=1',
            '-o', 'LogLevel=ERROR', '-i', str(ROOT / key), 'root@' + address, 'probe']


class PeerClients:
    def __init__(self):
        self.processes = []
        self.sequence = 0

    def token(self):
        self.sequence += 1
        return ('ssh-synthetic-' + str(self.sequence) + '\n').encode()

    def exchange(self, process):
        token = self.token()
        if process.poll() is not None: raise RuntimeError('SSH_SESSION_EXITED')
        process.stdin.write(token); process.stdin.flush()
        if not select.select([process.stdout], [], [], 5)[0]: raise RuntimeError('SSH_RESPONSE_TIMEOUT')
        if process.stdout.readline() != token: raise RuntimeError('SSH_RESPONSE_MISMATCH')
        return True

    def fresh(self, address, key='client', hosts='known_hosts'):
        token = self.token()
        result = subprocess.run(client_args(address, key, hosts), input=token,
                                capture_output=True, timeout=8, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
        if key == 'wrong':
            return result.returncode == 255 and not result.stdout and b'Permission denied (publickey)' in result.stderr
        if hosts == 'wrong_hosts':
            return result.returncode == 255 and not result.stdout and b'Host key verification failed' in result.stderr
        if result.returncode != 0 or result.stdout != token:
            raise RuntimeError('SSH_FRESH_FAILED ' + result.stderr.decode(errors='replace')[-1500:])
        return True

    def start(self):
        # A one-shot exchange preserves stderr if initial authentication fails.
        for address in ADDRESSES: self.fresh(address)
        for address in ADDRESSES:
            self.processes.append(subprocess.Popen(client_args(address), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'}))
        established = [self.exchange(p) for p in self.processes]
        wrong_keys = [self.fresh(a, key='wrong') for a in ADDRESSES]
        wrong_hosts = [self.fresh(a, hosts='wrong_hosts') for a in ADDRESSES]
        if wrong_keys != [True]*2 or wrong_hosts != [True]*2:
            raise RuntimeError('SSH_NEGATIVE_AUTH_CONTROLS_REQUIRED')
        return dict(established=established, wrong_keys_rejected=wrong_keys, wrong_hosts_rejected=wrong_hosts)

    def check(self):
        return dict(established=[self.exchange(p) for p in self.processes],
                    fresh=[self.fresh(a) for a in ADDRESSES])

    def stop(self):
        for p in self.processes:
            p.stdin.close()
            try: p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.terminate(); p.wait(timeout=5)
            p.stdout.close()
        self.processes.clear()


def stop_server(server):
    if server is not None:
        server.terminate()
        try: server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(server.pid, signal.SIGKILL); server.wait(timeout=5)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            while os.waitpid(-1, os.WNOHANG)[0]: pass
        except ChildProcessError:
            pass
        ssh_processes = []
        for entry in Path('/proc').iterdir():
            if entry.name.isdigit():
                try:
                    if (entry / 'comm').read_text().strip() in ('ssh', 'sshd', 'sshd-session', 'sshd-auth'):
                        ssh_processes.append(entry.name)
                except FileNotFoundError:
                    pass
        if not ssh_processes: return
        time.sleep(.02)
    raise RuntimeError('SSH_PROCESS_CLEANUP_REQUIRED')


if __name__ == '__main__':
    guest_guard()

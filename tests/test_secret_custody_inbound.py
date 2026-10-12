"""Broader inbound transport/flow-direction checks in empty CI net namespaces.

The two veth paths and every address/listener are synthetic. Static neighbours
deliberately exclude DHCP/ND, live SSH authentication and production binding.
"""
from contextlib import ExitStack
import copy
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import struct
import threading
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('transition', Path(__file__).with_name('test_secret_custody_network_transition.py'))
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
OBS = 'kc_inbound_observer'
PORTS = (('tcp', 22), ('tcp', 80), ('tcp', 443), ('tcp', 8080),
         ('udp', 22), ('udp', 53), ('udp', 443), ('udp', 8080))


def guard():
    t.guard()
    if os.environ.get('KC_INBOUND_CI') != '1': raise RuntimeError('INBOUND_CI_OPT_IN_REQUIRED')


def flows():
    rows = []
    for family, prefix in t.r.FAMILIES:
        def add(label, protocol='tcp', port=22, source='2', dest='1', interface='host0', sport=0, allowed=False):
            rows.append(dict(key=family + '_' + label, family=family, protocol=protocol, port=port,
                             source=prefix + source, dest=prefix + dest, interface=interface,
                             sport=sport, allowed=allowed))
        add('admin2', allowed=True); add('admin3', source='3', allowed=True)
        add('wrong_source', source='9'); add('wrong_destination', dest='4')
        add('wrong_interface', interface='host1')
        for protocol, port in PORTS:
            if (protocol, port) != ('tcp', 22): add(protocol + str(port), protocol, port)
        # Established ORIGINAL-direction inbound flows must not masquerade as
        # replies to the host's allowed DNS dependency merely by using sport 53.
        add('tcp_dns_origin', 'tcp', 8080, sport=53)
        add('udp_dns_origin', 'udp', 8080, sport=53)
    return rows


FLOWS = {row['key']: row for row in flows()}


def flow_socket(row):
    family = socket.AF_INET6 if row['family'] == 'ip6' else socket.AF_INET
    s = socket.socket(family, socket.SOCK_DGRAM if row['protocol'] == 'udp' else socket.SOCK_STREAM)
    s.settimeout(.4)
    try:
        s.bind((row['source'], row['sport'])); s.connect((row['dest'], row['port']))
        return s
    except BaseException:
        s.close(); raise


def fresh(row):
    try:
        with flow_socket(row) as s: return t.exchange(s)
    except OSError: return False


def route(alternate, peer=False):
    if type(alternate) is not bool: raise ValueError('FIXED_ROUTE_REQUIRED')
    device = ('peer' if peer else 'host') + str(int(alternate))
    for family, prefix in t.r.FAMILIES:
        target = prefix + ('1' if peer else '2') + ('/128' if family == 'ip6' else '/32')
        t.run(t.IP, '-6' if family == 'ip6' else '-4', 'route', 'replace', target, 'dev', device)


def peer():
    guard()
    if os.readlink('/proc/self/ns/net') == os.environ.get('FIXTURE_PARENT_NETNS'):
        raise RuntimeError('DISTINCT_PEER_NAMESPACE_REQUIRED')
    with ExitStack() as stack:
        opened = {}
        print('READY', flush=True)
        for line in sys.stdin:
            if len(line) > 256: raise ValueError('BOUNDED_PEER_COMMAND_REQUIRED')
            op = json.loads(line)
            if op == ['setup']:
                for name in ('peer0', 'peer1'): t.run(t.IP, 'link', 'set', name, 'addrgenmode', 'none')
                t.setup('peer0', t.MAC_PEER, ('2', '3', '9'))
                t.run(t.IP, 'link', 'set', 'peer1', 'address', '02:00:00:00:03:02', 'up')
                for family, prefix in t.r.FAMILIES:
                    flag = '-6' if family == 'ip6' else '-4'
                    t.run(t.IP, flag, 'neigh', 'replace', prefix + '4', 'lladdr', t.MAC_HOST, 'nud', 'permanent', 'dev', 'peer0')
                    t.run(t.IP, flag, 'neigh', 'replace', prefix + '1', 'lladdr', '02:00:00:00:03:01', 'nud', 'permanent', 'dev', 'peer1')
                result = True
            elif len(op) == 2 and op[0] == 'route':
                route(op[1], peer=True); result = True
            elif len(op) == 2 and op[0] in ('open', 'fresh', 'old') and op[1] in FLOWS:
                row = FLOWS[op[1]]
                if op[0] == 'open':
                    if op[1] in opened: raise ValueError('SINGLE_OWNED_FLOW_REQUIRED')
                    opened[op[1]] = stack.enter_context(flow_socket(row))
                    result = t.exchange(opened[op[1]])
                elif op[0] == 'fresh': result = fresh(row)
                else: result = t.exchange(opened[op[1]])
            elif op == ['stop']: break
            else: raise ValueError('FIXED_PEER_COMMAND_REQUIRED')
            print(json.dumps(result), flush=True)


def udp_reply(sock):
    """Preserve the addressed endpoint of a wildcard UDP socket's reply."""
    data, ancillary, flags, source = sock.recvmsg(64, socket.CMSG_SPACE(20))
    if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC): raise RuntimeError('BOUNDED_UDP_PACKET_REQUIRED')
    if sock.family == socket.AF_INET6:
        expected = (socket.IPPROTO_IPV6, socket.IPV6_PKTINFO)
        info = [value for level, kind, value in ancillary if (level, kind) == expected]
        if len(info) != 1 or len(info[0]) != 20: raise RuntimeError('IPV6_DESTINATION_REQUIRED')
        reply = info[0]
    else:
        expected = (socket.IPPROTO_IP, 8)  # Linux IP_PKTINFO.
        info = [value for level, kind, value in ancillary if (level, kind) == expected]
        if len(info) != 1 or len(info[0]) != 12: raise RuntimeError('IPV4_DESTINATION_REQUIRED')
        index, _, destination = struct.unpack('=I4s4s', info[0])
        reply = struct.pack('=I4s4s', index, destination, b'\0' * 4)
    sock.sendmsg([data], [(*expected, reply)], 0, source)


def udp_listener(stack, address, port):
    family = socket.AF_INET6 if ':' in address else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_DGRAM)
    stop = threading.Event()
    try:
        if family == socket.AF_INET6:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_RECVPKTINFO, 1)
        else: sock.setsockopt(socket.IPPROTO_IP, 8, 1)
        sock.bind((address, port)); sock.settimeout(.2)
    except BaseException:
        sock.close(); raise
    def serve():
        while not stop.is_set():
            try: udp_reply(sock)
            except socket.timeout: continue
            except OSError:
                if not stop.is_set(): raise
    thread = threading.Thread(target=serve, daemon=True); thread.start()
    def close():
        stop.set(); sock.close(); thread.join(timeout=1)
        if thread.is_alive(): raise RuntimeError('UDP_LISTENER_CLEANUP_REQUIRED')
    stack.callback(close)
    return sock


def server():
    guard()
    if os.readlink('/proc/self/ns/net') != os.environ.get('FIXTURE_PARENT_NETNS'):
        raise RuntimeError('OWNED_SERVER_NAMESPACE_REQUIRED')
    with ExitStack() as stack:
        for address in ('0.0.0.0', '::'):
            for protocol, port in PORTS:
                if protocol == 'udp': udp_listener(stack, address, port)
                else: t.listen(stack, address, port)
        print('READY', flush=True)
        for line in sys.stdin:
            op = json.loads(line)
            if op == ['stop']: break
            if op != ['loopback']: raise ValueError('FIXED_SERVER_COMMAND_REQUIRED')
            # All wildcard listeners remain alive under the filtered policy.
            result = [t.reaches(a, port, udp=protocol == 'udp')
                      for a in ('127.0.0.1', '::1') for protocol, port in PORTS]
            print(json.dumps(result), flush=True)


def spawn(stack, role):
    if role not in ('peer', 'server'): raise ValueError('FIXED_CHILD_ROLE_REQUIRED')
    proc = subprocess.Popen((['unshare', '--net'] if role == 'peer' else []) +
        [sys.executable, '-I', '-B', __file__, '--' + role], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        text=True, env=dict(os.environ, FIXTURE_PARENT_NETNS=os.readlink('/proc/self/ns/net')))
    def close():
        if proc.poll() is None: proc.terminate()
        try: proc.wait(timeout=3)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=3)
        proc.stdin.close(); proc.stdout.close()
        if Path('/proc/' + str(proc.pid)).exists(): raise RuntimeError('OWNED_CHILD_CLEANUP_REQUIRED')
    stack.callback(close)
    if t.read_line(proc).strip() != 'READY': raise RuntimeError('CHILD_READY_REQUIRED')
    return proc


def observer():
    text = f'create table inet {OBS}\n'
    for chain, priority in (('early', -10), ('late', 10)):
        text += f'add chain inet {OBS} {chain} {{ type filter hook input priority {priority}; policy accept; }}\n'
        for row in FLOWS.values():
            match = (f'iifname "{row["interface"]}" {row["family"]} saddr {row["source"]} '
                     f'{row["family"]} daddr {row["dest"]} {row["protocol"]} dport {row["port"]}')
            if row['sport']: match += f' {row["protocol"]} sport {row["sport"]}'
            text += f'add rule inet {OBS} {chain} {match} counter comment "{chain}_{row["key"]}"\n'
            if chain == 'early':
                text += f'add rule inet {OBS} {chain} {match} ct state established ct direction original counter comment "tracked_{row["key"]}"\n'
    return text


def report():
    raw = json.loads(t.run(t.NFT, '-j', 'list', 'table', 'inet', OBS).stdout)
    counters, identity = {}, copy.deepcopy(raw)
    for row in identity['nftables']:
        if 'rule' not in row: continue
        for expr in row['rule']['expr']:
            if 'counter' in expr:
                counters[row['rule']['comment']] = expr['counter']['packets']
                expr['counter'] = {}
    identity['nftables'] = [row for row in identity['nftables'] if 'metainfo' not in row]
    return counters, identity


def legacy_control():
    """Reconstruct only the prior candidate's missing bindings inside this test."""
    text = t.r.profile('maintenance')
    for item in ('iifname "host0" ', 'oifname "host0" ', 'ct direction original ', 'ct direction reply '):
        text = text.replace(item, '')
    for family, prefix in t.r.FAMILIES:
        text = text.replace(f'{family} daddr {prefix}1 ', '').replace(f'{family} saddr {prefix}1 ', '')
    return text


def measured(peer_proc, row, operation, allowed):
    before, _ = report()
    value = t.rpc(peer_proc, operation, row['key'])
    after, _ = report()
    key = row['key']
    if value is not allowed or after['early_' + key] <= before['early_' + key]:
        raise RuntimeError('ACTUAL_PACKET_REQUIRED ' + json.dumps(dict(key=key, operation=operation,
            result=value, expected=allowed, counters={part: [before[part + key], after[part + key]]
                for part in ('early_', 'late_', 'tracked_')})))
    if (after['late_' + key] > before['late_' + key]) is not allowed:
        raise RuntimeError('INPUT_DROP_REQUIRED_BEFORE_REPLY_FILTER ' + key)
    if operation == 'old' and after['tracked_' + key] <= before['tracked_' + key]:
        raise RuntimeError('PREEXISTING_ORIGINAL_DIRECTION_REQUIRED ' + key)


def check(peer_proc, server_proc, label, identity):
    for row in FLOWS.values():
        alternate = row['interface'] == 'host1'
        if alternate: route(True); t.rpc(peer_proc, 'route', True)
        try:
            if not row['sport']: measured(peer_proc, row, 'fresh', row['allowed'])
            if not alternate: measured(peer_proc, row, 'old', row['allowed'])
        finally:
            if alternate: route(False); t.rpc(peer_proc, 'route', False)
    if t.rpc(server_proc, 'loopback') != [True] * 16 or report()[1] != identity:
        raise RuntimeError('LIVE_LISTENERS_AND_UNCHANGED_OBSERVER_REQUIRED')
    print('PASS INBOUND_IPV4_IPV6_FRESH_EXISTING_TCP_UDP ' + label, flush=True)


def kernel():
    guard()
    host_ns = os.readlink('/proc/1/ns/net')
    if set(name for _, name in socket.if_nameindex()) != {'lo'}:
        raise RuntimeError('EMPTY_INBOUND_NAMESPACE_REQUIRED')
    if any('metainfo' not in row for row in json.loads(t.run(t.NFT, '-j', 'list', 'ruleset').stdout)['nftables']):
        raise RuntimeError('EMPTY_INBOUND_RULESET_REQUIRED')
    try:
        with ExitStack() as stack:
            child = spawn(stack, 'peer')
            for suffix, mac in (('0', t.MAC_HOST), ('1', '02:00:00:00:03:01')):
                t.run(t.IP, 'link', 'add', 'host' + suffix, 'type', 'veth', 'peer', 'name', 'peer' + suffix)
                t.run(t.IP, 'link', 'set', 'peer' + suffix, 'netns', str(child.pid))
                t.run(t.IP, 'link', 'set', 'host' + suffix, 'address', mac, 'addrgenmode', 'none')
            t.setup('host0', t.MAC_HOST, ('1', '4'))
            t.run(t.IP, 'link', 'set', 'host1', 'up')
            for family, prefix in t.r.FAMILIES:
                t.run(t.IP, '-6' if family == 'ip6' else '-4', 'neigh', 'replace', prefix + '2',
                      'lladdr', '02:00:00:00:03:02', 'nud', 'permanent', 'dev', 'host1')
            if not t.rpc(child, 'setup'): raise RuntimeError('PEER_SETUP_REQUIRED')
            listener = spawn(stack, 'server')
            t.nft(observer()); identity = report()[1]
            for row in FLOWS.values():
                alternate = row['interface'] == 'host1'
                if alternate: route(True); t.rpc(child, 'route', True)
                try: measured(child, row, 'fresh' if alternate else 'open', True)
                finally:
                    if alternate: route(False); t.rpc(child, 'route', False)
            print('PASS INBOUND_ALL_REACHABLE_POSITIVE_CONTROLS_AND_TRACKING', flush=True)
            # The old source-only / state-only policy must demonstrably expose
            # each missing-boundary case. No skipped or mocked kernel success.
            t.nft(legacy_control())
            for row in FLOWS.values():
                if row['key'].endswith(('wrong_destination', 'dns_origin')):
                    measured(child, row, 'old', True)
                elif row['interface'] == 'host1':
                    route(True); t.rpc(child, 'route', True)
                    try: measured(child, row, 'fresh', True)
                    finally: route(False); t.rpc(child, 'route', False)
            print('PASS LEGACY_INTERFACE_DESTINATION_AND_REPLY_DIRECTION_GAPS_REPRODUCED', flush=True)
            t.nft(t.r.replacement('maintenance'))
            maintenance = t.shape(t.r.TABLE)
            check(child, listener, 'maintenance', identity)
            candidate = t.owned_transition(maintenance, 'qualification')
            check(child, listener, 'qualification', identity)
            restored = t.owned_transition(candidate, 'maintenance')
            if restored != maintenance: raise RuntimeError('EXACT_RESTRICTED_RESTORE_REQUIRED')
            check(child, listener, 'restored', identity)
            for process in (child, listener):
                process.stdin.write('["stop"]\n'); process.stdin.flush()
                if process.wait(timeout=5) != 0: raise RuntimeError('CHILD_STOP_REQUIRED')
    finally:
        for table in (t.r.TABLE, OBS): t.run(t.NFT, 'delete', 'table', 'inet', table, success=False)
        for name in ('host0', 'host1'):
            if name in dict((name, index) for index, name in socket.if_nameindex()): t.run(t.IP, 'link', 'del', name)
    if (set(name for _, name in socket.if_nameindex()) != {'lo'} or os.readlink('/proc/1/ns/net') != host_ns
            or any('metainfo' not in row for row in json.loads(t.run(t.NFT, '-j', 'list', 'ruleset').stdout)['nftables'])):
        raise RuntimeError('INBOUND_CLEANUP_AND_HOST_NAMESPACE_REQUIRED')
    print('PASS INBOUND_OWNED_CHILDREN_LINKS_TABLES_CLEANED_HOST_UNCHANGED NO_LIVE_APPLY', flush=True)


class Tests(unittest.TestCase):
    def test_udp_reply_uses_received_local_destination(self):
        # Real unprivileged loopback sockets; no namespace/sysctl or host changes.
        for address, family in (('127.0.0.1', socket.AF_INET), ('::1', socket.AF_INET6)):
            with self.subTest(address=address), ExitStack() as stack:
                server_sock = udp_listener(stack, address, 0)
                client = stack.enter_context(socket.socket(family, socket.SOCK_DGRAM)); client.settimeout(1)
                client.connect(server_sock.getsockname()); client.sendall(b'endpoint')
                self.assertEqual(client.recv(64), b'endpoint')

    def test_host_non_ci_and_missing_optin_stop_before_commands(self):
        for ci, uid, namespaces in (('true', 0, ['same', 'same']), ('false', 0, []), ('true', 1000, [])):
            with patch.dict(os.environ, {'GITHUB_ACTIONS': ci, 'KC_INBOUND_CI': '1'}), patch.object(os, 'geteuid', return_value=uid), \
                    patch.object(os, 'readlink', side_effect=namespaces), patch.object(t, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'DISPOSABLE_CI'): kernel()
                run.assert_not_called()
        with patch.object(t, 'guard'), patch.dict(os.environ, {'KC_INBOUND_CI': '0'}), patch.object(t, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'OPT_IN'): kernel()
            run.assert_not_called()

    def test_false_denial_and_nontracked_old_flow_are_rejected(self):
        row = FLOWS['ip_wrong_source']; key = row['key']
        before = {'early_' + key: 0, 'late_' + key: 0, 'tracked_' + key: 0}
        for after in (before, dict(before, **{'early_' + key: 1, 'late_' + key: 1}),
                      dict(before, **{'early_' + key: 1})):
            with patch.object(t, 'rpc', return_value=False), patch(__name__ + '.report', side_effect=[(before, {}), (after, {})]):
                with self.assertRaises(RuntimeError): measured(None, row, 'old', False)

    def test_legacy_control_matches_previous_unbound_candidate(self):
        for mode in ('maintenance', 'qualification'):
            text = t.r.profile(mode)
            for line in text.splitlines():
                if 'ct state' in line and 'accept' in line:
                    self.assertIn('ct direction', line)
                    self.assertIn('ifname "host0"', line)
                    self.assertIn(' saddr ', line); self.assertIn(' daddr ', line)
        self.assertNotEqual(legacy_control(), t.r.profile('maintenance'))
        self.assertNotIn('ct direction', legacy_control())
        self.assertNotIn('ifname "host0"', legacy_control())

    def test_observer_counts_original_established_before_and_after_policy(self):
        text = observer()
        self.assertEqual(len(FLOWS), 28)
        self.assertEqual(text.count('ct state established ct direction original'), 28)
        self.assertIn('priority -10;', text); self.assertIn('priority 10;', text)
        self.assertNotIn(' accept\n', text); self.assertNotIn(' drop\n', text)
        with self.assertRaises(ValueError): route('host-interface')


if __name__ == '__main__':
    if sys.argv[1:] == ['--kernel']: kernel()
    elif sys.argv[1:] == ['--peer']: peer()
    elif sys.argv[1:] == ['--server']: server()
    else: unittest.main(verbosity=2)

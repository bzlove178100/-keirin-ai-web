"""Opt-in QEMU composition of sealed inbound startup and real SSH authentication."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('boot', HERE / 'test_secret_custody_systemd_boot.py')
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
p, vm = b.p, b.vm
guest = b.module('inbound_guest', HERE / 'fixtures/secret_custody_inbound_boot_guest.py')
i = b.module('inbound', HERE / 'test_secret_custody_inbound.py')


def command(path, case):
    if case not in guest.CASES: raise ValueError('FIXED_INBOUND_BOOT_CASE_REQUIRED')
    args = b.command(path, 'closed')
    args[args.index('-append') + 1] += ' kc_inbound_boot=' + case + ' kc_ssh_probe=1 end=9'
    return args


def record(lines, event, case):
    diagnostic, deadline = [], time.monotonic() + 100
    while True:
        try: line = lines.line(deadline)
        except Exception:
            print('INBOUND_BOOT_DIAGNOSTIC ' + '\n'.join(diagnostic)[-8000:], flush=True); raise
        diagnostic.append(line[-2000:]); diagnostic = diagnostic[-40:]
        if 'Kernel panic' in line or 'Freezing execution' in line:
            raise RuntimeError('INBOUND_BOOT_FATAL ' + '\n'.join(diagnostic)[-8000:])
        if line.startswith('INBOUND_BOOT_STAGE_ERROR '):
            expected_gate = case in ('missing', 'invalid', 'widened') and line.startswith('INBOUND_BOOT_STAGE_ERROR gate ')
            if not expected_gate: raise RuntimeError('INBOUND_BOOT_STAGE_FAILED ' + '\n'.join(diagnostic)[-8000:])
        # Gate failures are deliberate in the negative cases; final systemd
        # states must prove that link/check never ran. Other failures cannot pass.
        if not line.startswith('INBOUND_BOOT_RECORD '): continue
        row = json.loads(line[len('INBOUND_BOOT_RECORD '):])
        if row.get('event') != event or row.get('case') != case or row.get('pid1') != 'systemd':
            raise RuntimeError('INBOUND_BOOT_SEQUENCE_REQUIRED')
        if str(vm.uuid.UUID(row['boot'])) != row['boot']: raise RuntimeError('VALID_GUEST_BOOT_REQUIRED')
        print(line, flush=True); return row


def evidence(row):
    case, states = row['case'], row['states']
    if case not in guest.CASES or row.get('activation_allowed') is not False:
        raise RuntimeError('FIXED_INBOUND_BOOT_EVIDENCE_REQUIRED')
    if states['setup']['ActiveState'] != 'active' or states['setup']['ExecMainStatus'] != '0':
        raise RuntimeError('INBOUND_SETUP_SUCCESS_REQUIRED')
    for name, dep in (('gate', 'setup'), ('link', 'gate'), ('check', 'link')):
        for prop in ('Requires', 'After'):
            if 'kc-' + dep + '.service' not in states[name][prop].split():
                raise RuntimeError('INBOUND_SERVICE_DEPENDENCY_REQUIRED')
    if case in ('missing', 'invalid', 'widened'):
        if (row.get('links') != [False, False] or row.get('link_entered') is not False
                or row.get('sealed') is not None or row.get('linked') is not None or row.get('checked') is not None
                or states['gate']['ActiveState'] != 'failed' or states['gate']['Result'] != 'exit-code'
                or states['gate']['ExecMainStatus'] == '0'):
            raise RuntimeError('FAILED_INBOUND_GATE_MUST_STAY_CLOSED')
        for name in ('link', 'check'):
            if states[name]['ActiveState'] != 'inactive' or int(states[name]['ExecMainStartTimestampMonotonic']) != 0:
                raise RuntimeError('FAILED_GATE_MUST_PREVENT_LINK_AND_AUTH')
        return
    if (row.get('links') != [True, True] or row.get('link_entered') is not True
            or row['sealed']['boot'] != row['boot'] or row['linked']['boot'] != row['boot']
            or row['sealed']['links_down'] is not True
            or not 0 < row['sealed']['sealed_ns'] < row['linked']['up_ns']):
        raise RuntimeError('INBOUND_SEAL_BEFORE_FIRST_LINK_REQUIRED')
    for name, dep in (('gate', 'setup'), ('link', 'gate'), ('check', 'link')):
        if (states[name]['ActiveState'] != 'active' or states[name]['ExecMainStatus'] != '0'
                or not 0 < int(states[dep]['ExecMainExitTimestampMonotonic']) <= int(states[name]['ExecMainStartTimestampMonotonic'])):
            raise RuntimeError('INBOUND_REAL_SERVICE_ORDER_REQUIRED')
    checked = row['checked']
    if checked.get('loopback') != [True] * 16 or len(checked.get('packets', [])) != len(i.FLOWS):
        raise RuntimeError('COMPLETE_INBOUND_MATRIX_REQUIRED')
    for actual, expected in zip(checked['packets'], i.FLOWS.values()):
        allowed = case == 'control' or expected['allowed']
        if (actual.get('key') != expected['key'] or actual.get('allowed') is not allowed
                or actual.get('result') is not allowed or type(actual.get('early')) is not int or actual['early'] <= 0
                or type(actual.get('late')) is not int or actual['late'] < 0 or (actual['late'] > 0) is not allowed):
            raise RuntimeError('ACTUAL_ORDERED_INPUT_MATRIX_REQUIRED')
    if case == 'closed':
        if not row['sealed']['identity'] or checked.get('identity_unchanged') is not True:
            raise RuntimeError('UNCHANGED_AUTHENTICATED_POLICY_REQUIRED')
        p.ssh_evidence(checked['ssh_ready'], initial=True)
        p.ssh_evidence(checked['ssh_after'])
    elif row['sealed']['identity'] is not None or 'ssh_ready' in checked:
        raise RuntimeError('CONTROL_IS_NOT_SEALED_AUTHENTICATION')


def case(path, mode, host_boot):
    process = None
    try:
        with (path / 'stderr').open('wb') as err:
            process = subprocess.Popen(command(path, mode), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=err, cwd=path, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
            with vm.connect(path / 'qmp', process) as monitor, vm.connect(path / 'serial', process) as serial:
                qmp, lines = vm.QMP(monitor), vm.Lines(serial)
                if qmp.call('query-block') != []: raise RuntimeError('DISKLESS_INBOUND_GUEST_REQUIRED')
                first = record(lines, 'observed', mode); evidence(first)
                if first['boot'] == host_boot: raise RuntimeError('DISTINCT_INBOUND_BOOT_REQUIRED')
                serial.sendall(b'clean\n'); done = record(lines, 'done', mode)
                if done['boot'] != first['boot'] or done.get('interfaces') != ['lo'] or done.get('activation_allowed') is not False:
                    raise RuntimeError('INBOUND_OWNED_CLEANUP_REQUIRED')
                print('PASS INBOUND_SEALED_STARTUP_AND_AUTH ' + mode, flush=True)
                return first['boot']
    finally:
        if process is not None:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        for name in ('qmp', 'serial'): (path / name).unlink(missing_ok=True)


def run_vm():
    p.guard()
    if os.environ.get('KC_INBOUND_BOOT_CI') != '1': raise RuntimeError('INBOUND_BOOT_OPT_IN_REQUIRED')
    host_boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    host_netns = os.readlink('/proc/self/ns/net')
    with tempfile.TemporaryDirectory(prefix='kc-inbound-boot-') as value:
        path = Path(value)
        kernel = subprocess.run(['sudo', '-n', '/usr/bin/cat', '/boot/vmlinuz-' + os.uname().release],
                                check=True, capture_output=True, timeout=10).stdout
        if not 1024*1024 <= len(kernel) <= 64*1024*1024: raise RuntimeError('KERNEL_SIZE_BOUND')
        (path / 'vmlinuz').write_bytes(kernel); b.payload(path, inbound=True)
        boots = [case(path, mode, host_boot) for mode in guest.CASES]
        if len(set(boots)) != len(guest.CASES): raise RuntimeError('FRESH_INBOUND_CASE_BOOTS_REQUIRED')
    if path.exists() or Path('/proc/sys/kernel/random/boot_id').read_text().strip() != host_boot or os.readlink('/proc/self/ns/net') != host_netns:
        raise RuntimeError('INBOUND_HOST_UNCHANGED_CLEANUP_REQUIRED')
    print('PASS INBOUND_BOOT_IMAGES_PROCESSES_CLEANED_HOST_UNCHANGED NO_LIVE_APPLY', flush=True)


class Tests(unittest.TestCase):
    def test_bound_ssh_uses_only_approved_source_and_preserves_default(self):
        ssh = b.module('ssh', HERE / 'fixtures/secret_custody_ssh_guest.py')
        for address, source in (('192.0.2.1', '192.0.2.2'), ('2001:db8:1::1', '2001:db8:1::2')):
            self.assertNotIn('-b', ssh.client_args(address))
            for key, hosts in (('client', 'known_hosts'), ('wrong', 'known_hosts'), ('client', 'wrong_hosts')):
                args = ssh.client_args(address, key, hosts, bind_source=True)
                self.assertEqual(args[args.index('-b')+1], source)
        with self.assertRaises(ValueError): ssh.PeerClients(bind_source='arbitrary')

    def test_conntrack_module_is_explicit_and_original_payloads_unchanged(self):
        self.assertEqual(p.module_names(), ('ipv6', 'veth', 'nf_tables'))
        self.assertEqual(p.module_names(conntrack=True), ('ipv6', 'veth', 'nf_tables', 'nft_ct'))
        self.assertNotIn('nft_ct', p.module_names(boottime_guard=True, storage=True))

    def test_unexpected_guest_stage_error_fails_without_waiting_for_report(self):
        class Lines:
            def line(self, deadline): return "INBOUND_BOOT_STAGE_ERROR peer RuntimeError('synthetic')"
        for mode in guest.CASES:
            with self.assertRaisesRegex(RuntimeError, 'STAGE_FAILED'): record(Lines(), 'observed', mode)

    def test_fixed_opt_in_and_host_refusal(self):
        real_boot = b.module('real_boot', HERE / 'fixtures/secret_custody_boot_guest.py')
        with patch.object(guest, 'module', return_value=real_boot), patch.object(subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'ISOLATED_SYSTEMD_GUEST_REQUIRED'): guest.main('setup')
            run.assert_not_called()
        with patch.object(p, 'guard'), patch.dict(os.environ, {'KC_INBOUND_BOOT_CI': '0'}), patch.object(subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'OPT_IN'): run_vm()
            run.assert_not_called()
        with self.assertRaises(ValueError): command(Path('/tmp/owned'), 'live')
        with self.assertRaises(ValueError): b.payload(Path('/tmp/owned'), composed=True, inbound=True)
        args = command(Path('/tmp/owned'), 'closed')
        self.assertEqual(args[args.index('-nic') + 1], 'none'); self.assertNotIn('-drive', args)

    def test_missing_widened_or_changed_seal_is_refused(self):
        expected = [{'chain': {'policy': 'drop', 'hook': 'input'}}]
        guest.require_seal(copy.deepcopy(expected), expected)
        for value in ([], expected + [{'rule': {'accept': None}}], [{'chain': {'policy': 'accept', 'hook': 'input'}}]):
            with self.assertRaisesRegex(RuntimeError, 'SEAL'): guest.require_seal(value, expected)

    def test_denied_socket_without_observed_input_or_with_late_packet_fails(self):
        row = {'key': 'probe'}; before = {'early_probe': 2, 'late_probe': 1}
        good = {'early_probe': 3, 'late_probe': 1}
        guest.packet_evidence(row, False, before, good, False)
        for result, after in ((True, good), (False, before), (False, {'early_probe': 3, 'late_probe': 2})):
            with self.assertRaisesRegex(RuntimeError, 'ACTUAL_INPUT'): guest.packet_evidence(row, result, before, after, False)

    def test_failed_gate_never_accepts_link_or_auth_entry(self):
        states = {'setup': {'ActiveState': 'active', 'ExecMainStatus': '0'}}
        for name, dep in (('gate', 'setup'), ('link', 'gate'), ('check', 'link')):
            states[name] = dict(Requires='kc-' + dep + '.service', After='kc-' + dep + '.service',
                                ActiveState='inactive', ExecMainStartTimestampMonotonic='0')
        states['gate'].update(ActiveState='failed', Result='exit-code', ExecMainStatus='1')
        row = dict(case='widened', states=states, links=[False]*2, link_entered=False,
                   sealed=None, linked=None, checked=None, activation_allowed=False)
        evidence(row)
        for change in ({'links': [True, False]}, {'link_entered': True}, {'checked': {}}, {'sealed': {}}):
            with self.assertRaises(RuntimeError): evidence(dict(row, **change))
        states['check']['ExecMainStartTimestampMonotonic'] = '1'
        with self.assertRaisesRegex(RuntimeError, 'PREVENT'): evidence(row)

    def test_units_require_gate_then_link_then_check(self):
        units = guest.units()
        for name, dep in (('gate', 'setup'), ('link', 'gate'), ('check', 'link')):
            self.assertIn('Requires=kc-' + dep + '.service\nAfter=kc-' + dep + '.service', units['kc-' + name + '.service'])
        self.assertIn('Wants=kc-check.service\nAfter=kc-check.service', units['kc-report.service'])

    def test_success_requires_full_packets_authentication_and_order(self):
        states = {'setup': dict(ActiveState='active', ExecMainStatus='0', ExecMainExitTimestampMonotonic='1')}
        for n, (name, dep) in enumerate((('gate', 'setup'), ('link', 'gate'), ('check', 'link')), 1):
            states[name] = dict(Requires='kc-' + dep + '.service', After='kc-' + dep + '.service',
                ActiveState='active', ExecMainStatus='0', ExecMainStartTimestampMonotonic=str(n*2),
                ExecMainExitTimestampMonotonic=str(n*2+1))
        checked = dict(loopback=[True]*16, identity_unchanged=True,
            ssh_ready=dict(established=[True]*2, wrong_keys_rejected=[True]*2, wrong_hosts_rejected=[True]*2),
            ssh_after=dict(established=[True]*2, fresh=[True]*2),
            packets=[dict(key=r['key'], allowed=r['allowed'], result=r['allowed'], early=1,
                          late=int(r['allowed'])) for r in i.FLOWS.values()])
        row = dict(case='closed', boot='same', states=states, links=[True]*2, link_entered=True,
            activation_allowed=False, sealed=dict(boot='same', links_down=True, sealed_ns=1, identity=['synthetic']),
            linked=dict(boot='same', up_ns=2), checked=checked)
        evidence(row)
        for mutate in (lambda r: r['checked']['packets'].pop(),
                       lambda r: r['checked']['packets'][0].update(early=0),
                       lambda r: r['checked']['ssh_ready'].update(wrong_keys_rejected=[False]*2),
                       lambda r: r['checked'].update(identity_unchanged=False),
                       lambda r: r['linked'].update(up_ns=0),
                       lambda r: r['states']['check'].update(ExecMainStartTimestampMonotonic='1')):
            changed = copy.deepcopy(row); mutate(changed)
            with self.assertRaises(RuntimeError): evidence(changed)


if __name__ == '__main__':
    if sys.argv[1:] == ['--vm']: run_vm()
    else: unittest.main(verbosity=2)

"""Opt-in disposable guests: fixed TCP/443 policy must precede first link-up."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


p = module('packets', HERE / 'test_secret_custody_suspend_packets.py')
policy = module('startup_policy', HERE.parent / 'review/secret_custody_closed_startup.py')
CASES = ('open', 'missing', 'invalid', 'closed')


def evidence(mode, down, ready, packets=None):
    if mode not in CASES:
        raise ValueError('FIXED_STARTUP_CASE_REQUIRED')
    if down.get('link_up') is not False or ready.get('link_up') is not False:
        raise RuntimeError('STARTUP_LINK_DOWN_EVIDENCE_REQUIRED')
    records = [down, ready] + ([] if packets is None else [packets])
    for row in records:
        if row.get('boot') != down.get('boot') or row.get('mode') != mode:
            raise RuntimeError('SAME_STARTUP_CASE_REQUIRED')
    for previous, later in zip(records, records[1:]):
        if any(later[key] < previous[key] for key in ('monotonic', 'boottime')):
            raise RuntimeError('STARTUP_EVIDENCE_ORDER_REQUIRED')
    if mode in ('missing', 'invalid'):
        if (packets is not None or ready.get('ruleset_empty') is not True
                or ready.get('reason') != ('missing_policy' if mode == 'missing' else 'install_failed')):
            raise RuntimeError('STARTUP_REFUSAL_EVIDENCE_REQUIRED')
        return 'STARTUP_REFUSED_LINK_DOWN'
    expected = 'CLOSED_BEFORE_LINK_OBSERVED' if mode == 'closed' else 'UNPROTECTED_STARTUP_DETECTED'
    if (packets is None or ready.get('closed_policy') is not (mode == 'closed')
            or packets.get('link_up') is not True or packets.get('outcome') != expected
            or packets.get('qualification') != [mode == 'open'] * 2
            or packets.get('management') != [True] * 2
            or any(type(v) is not bool for v in packets['qualification'] + packets['management'])
            or packets.get('policy_unchanged') is not (True if mode == 'closed' else None)):
        raise RuntimeError('STARTUP_PACKET_EVIDENCE_REQUIRED')
    return expected


def case(path, mode, host_boot):
    process = None
    try:
        with (path / 'stderr').open('wb') as errors:
            args = p.command(path)
            args[args.index('-append') + 1] += ' kc_startup_probe=1 end=4'
            process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=errors, cwd=path, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
            with p.vm.connect(path / 'qmp', process) as monitor, p.vm.connect(path / 'serial', process) as serial:
                qmp, lines = p.vm.QMP(monitor), p.vm.Lines(serial)
                if qmp.call('query-block') != []:
                    raise RuntimeError('DISKLESS_STARTUP_GUEST_REQUIRED')
                boot = p.vm.record(lines, 'boot')['boot']
                if boot == host_boot:
                    raise RuntimeError('DISTINCT_STARTUP_GUEST_BOOT_REQUIRED')
                serial.sendall((mode + '\n').encode())
                down = p.record(lines, 'startup_down', mode, boot)
                ready = p.record(lines, 'startup_rejected' if mode in ('missing', 'invalid') else 'startup_ready', mode, boot)
                packets = p.record(lines, 'startup_packets', mode, boot) if mode in ('open', 'closed') else None
                result = evidence(mode, down, ready, packets)
                done = p.record(lines, 'done', mode, boot)
                if done.get('activation_allowed') is not False or done.get('outcome') != result:
                    raise RuntimeError('STARTUP_CLEANUP_NO_ACTIVATION_REQUIRED')
                print('PASS STARTUP_GUEST', mode, result, flush=True)
                return boot
    except Exception:
        print((path / 'stderr').read_text(errors='replace')[-4000:], flush=True)
        raise
    finally:
        if process is not None:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
            if Path(f'/proc/{process.pid}').exists():
                raise RuntimeError('OWNED_STARTUP_VM_REAP_REQUIRED')
        for name in ('serial', 'qmp'):
            (path / name).unlink(missing_ok=True)


def run_vm():
    p.guard()
    if os.environ.get('KC_CLOSED_STARTUP_CI') != '1':
        raise RuntimeError('CLOSED_STARTUP_CI_OPT_IN_REQUIRED')
    host_boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    host_netns = os.readlink('/proc/self/ns/net')
    with tempfile.TemporaryDirectory(prefix='kc-startup-vm-') as value:
        path = Path(value)
        source = Path('/boot') / ('vmlinuz-' + os.uname().release)
        if not source.is_file(): raise RuntimeError('INSTALLED_CI_KERNEL_REQUIRED')
        kernel = subprocess.run(['sudo', '-n', '/usr/bin/cat', str(source)], check=True, capture_output=True, timeout=10).stdout
        if not 1024 * 1024 <= len(kernel) <= 64 * 1024 * 1024:
            raise RuntimeError('KERNEL_SIZE_BOUND')
        (path / 'vmlinuz').write_bytes(kernel)
        p.payload(path, startup=True)
        print('STARTUP_VM_PROVENANCE', json.dumps({'kernel_release': os.uname().release,
              'kernel_sha256': hashlib.sha256(kernel).hexdigest(),
              'qemu_sha256': hashlib.sha256(Path(p.vm.QEMU).read_bytes()).hexdigest()}), flush=True)
        boots = [case(path, mode, host_boot) for mode in CASES]
        if len(set(boots)) != len(CASES):
            raise RuntimeError('FRESH_BOOT_PER_STARTUP_CASE_REQUIRED')
    if path.exists() or Path('/proc/sys/kernel/random/boot_id').read_text().strip() != host_boot or os.readlink('/proc/self/ns/net') != host_netns:
        raise RuntimeError('STARTUP_CLEANUP_HOST_CONTEXT_REQUIRED')
    print('PASS STARTUP_IMAGES_CHANNELS_PROCESSES_CLEANED_HOST_UNCHANGED NO_LIVE_APPLY', flush=True)


class Tests(unittest.TestCase):
    def fixture(self):
        rows = [{'table': {'family': 'inet', 'name': policy.TABLE, 'handle': 1}}]
        for hook in ('input', 'output'):
            rows.append({'chain': {'family': 'inet', 'table': policy.TABLE, 'name': hook,
                                  'handle': len(rows) + 1, 'type': 'filter', 'hook': hook,
                                  'prio': -20, 'policy': 'accept'}})
            for field in ('sport', 'dport'):
                rows.append({'rule': {'family': 'inet', 'table': policy.TABLE, 'chain': hook, 'handle': len(rows) + 1,
                    'expr': [{'match': {'op': '==', 'left': {'payload': {'protocol': 'tcp', 'field': field}}, 'right': 443}},
                             {'counter': {'packets': 0, 'bytes': 0}}, {'drop': None}]}})
        return {'nftables': rows}

    def test_closed_policy_rejects_allow_wrong_hook_extra_or_missing_rule(self):
        report = self.fixture()
        sealed = policy.seal(report)
        # Actual first guest stopped on object ordering. Both nft layouts must
        # express the same exact chain membership and ordered drop rules.
        grouped = {'nftables': sorted(report['nftables'], key=lambda row: ('table', 'chain', 'rule').index(next(iter(row))))}
        self.assertEqual(policy.seal(grouped), sealed)
        changed = copy.deepcopy(report)
        changed['nftables'][2]['rule']['expr'][1]['counter']['packets'] = 7
        self.assertEqual(policy.seal(changed), sealed)
        changes = []
        wrong = copy.deepcopy(report); wrong['nftables'][2]['rule']['expr'][-1] = {'accept': None}; changes.append(wrong)
        wrong = copy.deepcopy(report); wrong['nftables'][1]['chain']['hook'] = 'forward'; changes.append(wrong)
        wrong = copy.deepcopy(report); wrong['nftables'][2]['rule']['expr'][0]['match']['right'] = 22; changes.append(wrong)
        changes += [{'nftables': report['nftables'][:-1]}, {'nftables': report['nftables'] + report['nftables'][-1:]}]
        wrong = copy.deepcopy(report); wrong['nftables'][2], wrong['nftables'][3] = wrong['nftables'][3], wrong['nftables'][2]; changes.append(wrong)
        for wrong in changes:
            with self.subTest(wrong=wrong), self.assertRaises(ValueError): policy.seal(wrong)

    def test_startup_evidence_rejects_open_link_leak_missing_management_and_reordering(self):
        down = dict(mode='closed', boot='a', monotonic=1., boottime=1., link_up=False)
        ready = dict(down, monotonic=2., boottime=2., closed_policy=True)
        packets = dict(ready, monotonic=3., boottime=3., link_up=True, qualification=[False]*2,
                       management=[True]*2, policy_unchanged=True, outcome='CLOSED_BEFORE_LINK_OBSERVED')
        self.assertEqual(evidence('closed', down, ready, packets), 'CLOSED_BEFORE_LINK_OBSERVED')
        for changed in ({'qualification': [True, False]}, {'management': [False, True]},
                        {'qualification': [0, 0]}, {'boot': 'b'}, {'monotonic': 0.}, {'policy_unchanged': False}):
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                evidence('closed', down, ready, dict(packets, **changed))
        with self.assertRaises(RuntimeError): evidence('closed', down, dict(ready, link_up=True), packets)
        with self.assertRaises(RuntimeError): evidence('closed', down, dict(ready, closed_policy=False), packets)

    def test_install_failure_requires_link_down_and_empty_ruleset(self):
        for mode, reason in (('missing', 'missing_policy'), ('invalid', 'install_failed')):
            down = dict(mode=mode, boot='a', monotonic=1., boottime=1., link_up=False)
            ready = dict(down, reason=reason, ruleset_empty=True)
            self.assertEqual(evidence(mode, down, ready), 'STARTUP_REFUSED_LINK_DOWN')
            with self.assertRaises(RuntimeError): evidence(mode, down, dict(ready, link_up=True))
            with self.assertRaises(RuntimeError): evidence(mode, down, dict(ready, ruleset_empty=False))

    def test_opt_in_precedes_build_and_guest_refuses_ordinary_execution(self):
        with patch.object(p, 'guard'), patch.dict(os.environ, {'KC_CLOSED_STARTUP_CI': '0'}), patch.object(subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'OPT_IN'): run_vm()
            run.assert_not_called()
        result = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'fixtures/secret_custody_startup_guest.py')], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'FIXED_STARTUP_GUEST_REQUIRED', result.stdout)


if __name__ == '__main__':
    if sys.argv[1:] == ['--vm']: run_vm()
    else: unittest.main(verbosity=2)

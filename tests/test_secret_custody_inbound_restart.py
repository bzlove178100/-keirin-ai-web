"""Restored input policy -> normal reboot -> full fresh composition -> poweroff."""
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('lease', HERE / 'test_secret_custody_inbound_lease.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
b, p, vm, h = c.b, c.p, c.vm, c.h
guest = b.module('inbound_restart', HERE / 'fixtures/secret_custody_inbound_restart_guest.py')


def command(path, mode):
    args = c.command(path, mode)
    args[args.index('-append') + 1] += ' kc_inbound_restart=1 end=11'
    return args


def record(lines, event, boot, target):
    diagnostic, deadline = [], time.monotonic() + 75
    while True:
        try: line = lines.line(deadline)
        except Exception:
            print('INBOUND_RESTART_DIAGNOSTIC ' + '\n'.join(diagnostic)[-8000:], flush=True); raise
        diagnostic.append(line[:1500] + (' ... ' + line[-1500:] if len(line) > 1500 else '')); diagnostic = diagnostic[-30:]
        if line.startswith(('INBOUND_RESTART_FAIL', 'INBOUND_BOOT_STAGE_ERROR')) or 'Kernel panic' in line:
            raise RuntimeError('INBOUND_NORMAL_SHUTDOWN_FAILED ' + '\n'.join(diagnostic)[-8000:])
        if not line.startswith('INBOUND_RESTART_RECORD '): continue
        row = json.loads(line[len('INBOUND_RESTART_RECORD '):])
        if (row.get('event') != event or row.get('boot') != boot or row.get('target') != target
                or row.get('activation_allowed') is not False or type(row.get('monotonic')) not in (int,float)
                or not math.isfinite(row['monotonic']) or row['monotonic'] < 0):
            raise RuntimeError('MATCHED_INBOUND_RESTART_RECORD_REQUIRED')
        print(line, flush=True); return row


def evidence(request, down, stopped):
    if not request['monotonic'] <= down['monotonic'] <= stopped['monotonic']:
        raise RuntimeError('ORDERED_INBOUND_SHUTDOWN_REQUIRED')
    for row in (request, down, stopped):
        if row.get('profile_unchanged') is not True or row.get('guards_absent') is not True:
            raise RuntimeError('UNMASKED_PROFILE_RETAINED_REQUIRED')
    for row in (request, down):
        if row.get('qualification') != [False, False] or any(type(v) is not bool for v in row['qualification']):
            raise RuntimeError('CLOSED_INBOUND_SHUTDOWN_REQUIRED')
    if (request.get('links') != [True, True] or down.get('links') != [False, False]
            or down.get('after_down') != [False, False] or down.get('peer_alive') is not True
            or stopped.get('peer_stopped') is not True or stopped.get('ssh_stopped') is not True
            or not request['monotonic'] <= stopped['link_stopped_at'] <= down['monotonic']
            or any(n not in ('lo', 'host0', 'host1') for n in stopped.get('interfaces', []))
            or 'lo' not in stopped.get('interfaces', [])):
        raise RuntimeError('CLOSED_LINK_THEN_PEER_STOP_REQUIRED')
    states = stopped['states']
    if set(states) != set(guest.SERVICES): raise RuntimeError('COMPLETE_STOPPED_SERVICES_REQUIRED')
    times = []
    for name in guest.SERVICES:
        s = states[name]
        if (s['ActiveState'] != 'inactive' or s['Result'] != 'success'
                or 'shutdown.target' not in s['Conflicts'].split() or 'shutdown.target' not in s['Before'].split()):
            raise RuntimeError('NORMAL_MANAGER_STOP_REQUIRED')
        times.append(int(s['InactiveEnterTimestampMonotonic']))
    if (not all(t > 0 for t in times) or times != sorted(times)
            or not request['monotonic'] <= times[0] / 1e6
            or times[-1] / 1e6 > stopped['monotonic']
            or stopped['link_stopped_at'] > times[guest.SERVICES.index('link')] / 1e6):
        raise RuntimeError('ACTUAL_REVERSE_SERVICE_STOP_ORDER_REQUIRED')
    public = request.get('public_key_sha256', {})
    if set(public) != {'host','client'} or any(not re.fullmatch('[0-9a-f]{64}',str(v)) for v in public.values()):
        raise RuntimeError('FRESH_PUBLIC_KEY_DIGESTS_REQUIRED')


def fresh(first, second):
    if (first['boot'] == second['boot'] or first['public_key_sha256']['host'] == second['public_key_sha256']['host']
            or first['public_key_sha256']['client'] == second['public_key_sha256']['client']):
        raise RuntimeError('FRESH_BOOT_AND_EPHEMERAL_KEYS_REQUIRED')


def case(path, mode, host_boot):
    process = None
    try:
        with (path / 'stderr').open('wb') as err:
            process = subprocess.Popen(command(path, mode), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=err, cwd=path, env={'PATH':'/usr/bin:/bin','LANG':'C'})
            with vm.connect(path/'qmp',process) as monitor, vm.connect(path/'serial',process) as serial:
                qmp, lines = vm.QMP(monitor), vm.Lines(serial)
                if qmp.call('query-block') != [] or qmp.call('query-current-machine').get('wakeup-suspend-support') is not True:
                    raise RuntimeError('DISKLESS_RESTART_S3_MACHINE_REQUIRED')
                boots, requests = {host_boot}, []
                for instruction, target, event in ((b'restart\n','reboot.target','RESET'),(b'halt\n','poweroff.target','SHUTDOWN')):
                    first, outcome = c.cycle(lines,qmp,mode,host_boot); boot = first['boot']
                    if boot in boots: raise RuntimeError('DISTINCT_POST_RESTART_BOOT_REQUIRED')
                    boots.add(boot)
                    qmp.events = [e for e in qmp.events if e.get('event') in ('SUSPEND','WAKEUP')]
                    serial.sendall(instruction)
                    rows = [record(lines,name,boot,target) for name in ('requested','link_down','stopped')]
                    evidence(*rows); requests.append(rows[0])
                    observed = qmp.event(event,time.monotonic()+30)
                    if observed.get('data',{}).get('guest') is not True: raise RuntimeError('GUEST_NORMAL_TRANSITION_REQUIRED')
                    print('PASS INBOUND_NORMAL_SYSTEMD_TRANSITION '+mode+' '+target+' '+boot+' '+outcome,flush=True)
                fresh(*requests)
                if process.wait(timeout=10) != 0: raise RuntimeError('NORMAL_INBOUND_POWEROFF_EXIT_REQUIRED')
                print('PASS INBOUND_REBOOT_FRESH_KEYS_RESEALED_AND_RETESTED '+mode,flush=True)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        for name in ('qmp','serial'): (path/name).unlink(missing_ok=True)


def run_vm(mode):
    p.guard()
    if os.environ.get('KC_INBOUND_RESTART_CI') != '1' or mode not in ('awake','suspend'):
        raise RuntimeError('FIXED_INBOUND_RESTART_OPT_IN_REQUIRED')
    host_boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip(); host_ns = os.readlink('/proc/self/ns/net')
    with tempfile.TemporaryDirectory(prefix='kc-inbound-restart-') as value:
        path = Path(value)
        kernel = subprocess.run(['sudo','-n','/usr/bin/cat','/boot/vmlinuz-'+os.uname().release],check=True,capture_output=True,timeout=10).stdout
        if not 1024*1024 <= len(kernel) <= 64*1024*1024: raise RuntimeError('KERNEL_SIZE_BOUND')
        (path/'vmlinuz').write_bytes(kernel)
        b.payload(path,inbound=True,inbound_lease=True,inbound_restart=True)
        case(path,mode,host_boot)
    if path.exists() or Path('/proc/sys/kernel/random/boot_id').read_text().strip() != host_boot or os.readlink('/proc/self/ns/net') != host_ns:
        raise RuntimeError('INBOUND_RESTART_HOST_UNCHANGED_REQUIRED')
    print('PASS INBOUND_RESTART_IMAGES_PROCESSES_CLEANED_HOST_UNCHANGED NO_LIVE_APPLY',flush=True)


class Tests(unittest.TestCase):
    def test_normal_shutdown_units_require_lease_and_reverse_dependencies(self):
        with self.assertRaises(ValueError): h.guest.units(inbound_restart=True)
        with self.assertRaises(ValueError): b.payload(Path('/tmp/owned'),inbound_restart=True)
        self.assertNotIn('shutdown.target',''.join(h.guest.units(inbound_lease=True).values()))
        units = h.guest.units(inbound_lease=True,inbound_restart=True)
        self.assertIn('Type=exec',units['kc-report.service'])
        for name in guest.SERVICES:
            self.assertIn('Conflicts=shutdown.target\nBefore=shutdown.target',units['kc-'+name+'.service'])
        self.assertIn('ExecStop=/usr/bin/python3 -I -B /inbound_restart.py link-down',units['kc-link.service'])
        self.assertIn('Requires=shutdown.target\nAfter=shutdown.target\nBefore=final.target',units['kc-shutdown-check.service'])
        self.assertIn('Requires=kc-shutdown-check.service',units['final.target.d/kc-check.conf'])

    def test_host_refusal_and_fixed_opt_in_precede_actions(self):
        with patch.object(subprocess,'run') as run:
            with self.assertRaises((FileNotFoundError,RuntimeError)): guest.main('restart')
            run.assert_not_called()
        with patch.object(p,'guard'),patch.dict(os.environ,{'KC_INBOUND_RESTART_CI':'0'}),patch.object(subprocess,'run') as run:
            with self.assertRaisesRegex(RuntimeError,'OPT_IN'): run_vm('awake')
            run.assert_not_called()
        with self.assertRaises(ValueError): command(Path('/tmp/owned'),'live')
        args=command(Path('/tmp/owned'),'awake')
        self.assertEqual(args[args.index('-nic')+1],'none'); self.assertNotIn('-drive',args)

    def test_missing_stale_or_unexpired_recovery_rejected(self):
        state=dict(boot='one',restored_identity=['fixed'],proof=dict(deadline_ns=10,loader_exits=True))
        guest.expired(state,dict(boot='one'),'one',11)
        for modified,recovery,now in ((state,dict(boot='old'),11),(state,dict(boot='one'),10),
            (dict(state,restored_identity=[]),dict(boot='one'),11),(dict(state,proof=None),dict(boot='one'),11),
            (dict(state,proof=dict(deadline_ns=True,loader_exits=True)),dict(boot='one'),11)):
            with self.assertRaisesRegex(RuntimeError,'EXPIRED'): guest.expired(modified,recovery,'one',now)

    def test_key_comment_changes_do_not_prove_fresh_credentials(self):
        self.assertEqual(guest.fingerprint('ssh-ed25519 YWJj old'),guest.fingerprint('ssh-ed25519 YWJj new'))
        first=dict(boot='one',public_key_sha256=dict(host='a'*64,client='b'*64))
        second=dict(boot='two',public_key_sha256=dict(host='c'*64,client='d'*64))
        fresh(first,second)
        for changed in (dict(second,boot='one'),dict(second,public_key_sha256=dict(host='a'*64,client='d'*64)),
                        dict(second,public_key_sha256=dict(host='c'*64,client='b'*64))):
            with self.assertRaisesRegex(RuntimeError,'FRESH'): fresh(first,changed)

    def test_shutdown_evidence_rejects_open_mutated_masked_or_unordered_state(self):
        request=dict(monotonic=1,qualification=[False]*2,profile_unchanged=True,guards_absent=True,links=[True]*2,
                     public_key_sha256=dict(host='a'*64,client='b'*64))
        down=dict(monotonic=2,qualification=[False]*2,after_down=[False]*2,profile_unchanged=True,
                  guards_absent=True,links=[False]*2,peer_alive=True)
        states={n:dict(ActiveState='inactive',Result='success',Before='shutdown.target',Conflicts='shutdown.target',
                       InactiveEnterTimestampMonotonic=str(1100000+j*200000)) for j,n in enumerate(guest.SERVICES)}
        stopped=dict(monotonic=3,profile_unchanged=True,guards_absent=True,peer_stopped=True,ssh_stopped=True,
                     link_stopped_at=1.8,interfaces=['lo'],states=states)
        evidence(request,down,stopped)
        for change in ({'profile_unchanged':False},{'guards_absent':False},{'qualification':[True]*2},{'links':[False]*2}):
            with self.assertRaises(RuntimeError): evidence(dict(request,**change),down,stopped)
        for change in ({'links':[False,True]},{'peer_alive':False},{'after_down':[True,False]}):
            with self.assertRaises(RuntimeError): evidence(request,dict(down,**change),stopped)
        for change in ({'peer_stopped':False},{'interfaces':['lo','eth0']},{'states':{}},{'link_stopped_at':2.1}):
            with self.assertRaises(RuntimeError): evidence(request,down,dict(stopped,**change))
        changed=copy.deepcopy(stopped);changed['states']['setup']['InactiveEnterTimestampMonotonic']='1100000'
        with self.assertRaisesRegex(RuntimeError,'ORDER'): evidence(request,down,changed)


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--vm': run_vm(sys.argv[2])
    else: unittest.main(verbosity=2)

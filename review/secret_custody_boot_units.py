"""Fixed units for an isolated synthetic guest; not a production installer."""


def units(composed=False, restart=False):
    if restart and not composed: raise ValueError("RESTART_REQUIRES_COMPOSITION")
    def service(action, dependencies=''):
        return ('[Unit]\nDefaultDependencies=no\n' + dependencies +
                '[Service]\nType=oneshot\nRemainAfterExit=yes\nTimeoutStartSec=90\n'
                'StandardOutput=tty\nStandardError=tty\nTTYPath=/dev/ttyS0\n'
                'ExecStart=/usr/bin/python3 -I -B /boot_probe.py ' + action + '\n')
    result = {
        'default.target': '[Unit]\nDescription=Isolated boot experiment\nDefaultDependencies=no\nWants=kc-report.service\n',
        'kc-setup.service': service('setup'),
        'kc-gate.service': service('gate', 'Requires=kc-setup.service\nAfter=kc-setup.service\n'),
        'kc-link.service': service('link', 'Requires=kc-gate.service\nAfter=kc-gate.service\n'),
        'kc-report.service': service('report', 'Wants=kc-link.service\nAfter=kc-link.service\n') + 'StandardInput=tty\n',
    }
    if composed:
        result['kc-observe.service'] = service('observe', 'Requires=kc-link.service\nAfter=kc-link.service\n')
        for action, dependency in (('auth', 'observe'), ('lease', 'auth')):
            result['kc-' + action + '.service'] = service(action, 'Requires=kc-' + dependency + '.service\nAfter=kc-' + dependency + '.service\n').replace('/boot_probe.py ', '/composed.py ')
        result['kc-report.service'] = service('report', 'Wants=kc-lease.service\nAfter=kc-lease.service\n') + 'StandardInput=tty\n'
    if restart:
        for name in tuple(result):
            if name.startswith('kc-'):
                result[name] = result[name].replace('[Service]', 'Conflicts=shutdown.target\nBefore=shutdown.target\n[Service]')
        result['kc-link.service'] += 'ExecStop=/usr/bin/python3 -I -B /restart_probe.py link-down\n'
        result['kc-shutdown-check.service'] = service('check', 'Requires=shutdown.target\nAfter=shutdown.target\nBefore=final.target\n').replace('/boot_probe.py ', '/restart_probe.py ')
        result['final.target.d/kc-check.conf'] = '[Unit]\nRequires=kc-shutdown-check.service\nAfter=kc-shutdown-check.service\n'
    return result

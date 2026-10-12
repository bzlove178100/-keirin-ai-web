"""Fixed units for an isolated synthetic guest; not a production installer."""


def units():
    def service(action, dependencies=''):
        return ('[Unit]\nDefaultDependencies=no\n' + dependencies +
                '[Service]\nType=oneshot\nRemainAfterExit=yes\nTimeoutStartSec=90\n'
                'StandardOutput=tty\nStandardError=tty\nTTYPath=/dev/ttyS0\n'
                'ExecStart=/usr/bin/python3 -I -B /boot_probe.py ' + action + '\n')
    return {
        'default.target': '[Unit]\nDescription=Isolated boot experiment\nDefaultDependencies=no\nWants=kc-report.service\n',
        'kc-setup.service': service('setup'),
        'kc-gate.service': service('gate', 'Requires=kc-setup.service\nAfter=kc-setup.service\n'),
        'kc-link.service': service('link', 'Requires=kc-gate.service\nAfter=kc-gate.service\n'),
        'kc-report.service': service('report', 'Wants=kc-link.service\nAfter=kc-link.service\n') + 'StandardInput=tty\n',
    }

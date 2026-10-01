# H2b: bounded synthetic sandbox verification

H2a recovery, apply and read-only verify succeeded in the user's Termius screenshot
IMG_8925 at 2026-10-02 00:23 JST. The user said `次` at 00:25 JST immediately after
the proposed next step of checking the installed restrictions. This authorizes
the bounded no-secret verification described here, not agent activation.

Implementation: `review/secret_custody_h2b.py`. Default `inspect` is read-only;
`run --approve H2_SYNTHETIC_PROBE_V1` executes one fixed synthetic probe. The CLI
token guards accidents; it is not a new user approval request. Work has no live
SSH session, so actual host execution uses the existing phone Termius session.

## Exact behavior

The controller receives the existing H2a validator source via stdin, rejects it
unless its SHA-256 is exactly
`8e4ff9838829ce466b9913ea2dd39e2b5adf1854eacec96925fe9ac5e594a0f1`, and reuses its
current-installation verification and advisory lock. This is an immediate drift
guard before/after a new probe, not a repeat of provisioning or H1.

The only executed service is a uniquely named `keirin-custody-h2b-<uuid>.service`
transient unit. It inherits every H2a service restriction, substituting only
the placeholder command/type/output with a fixed Python probe, `Type=exec`, and
captured pipes. It adds `RuntimeMaxSec=10s`. Type=exec is necessary because
RuntimeMaxSec has no effect on a oneshot service. The installed
`keirin-custody.service` remains inactive with manual start refused.

The transient unit has the same non-login account, memory 128 MiB, swap 0,
tasks 24, CPU 50% of one CPU, capabilities empty, private network, AF_UNIX-only
socket creation, read-only system paths and other H2a service protections.
The child starts through `env -i`, system Python `-I -B`, and fixed PATH/locale.
No credential, application payload or caller environment is handed to it.

The probe checks actual child/kernel observations:

| Check | Evidence |
| --- | --- |
| Identity | Real/effective/saved UID/GID equal dedicated identity; no other groups |
| Privilege restrictions | NoNewPrivs=1 and all five capability masks zero |
| Core/creation mask | Core soft/hard limits zero; umask 0077 |
| Code and configuration | `statvfs` reports read-only mounted paths |
| Private temporary directories | `/tmp` and `/var/tmp` differ from parent directory identities; one-byte anonymous temporary files work |
| Private network | Child network namespace differs from controller |
| IPv4/IPv6 | Socket creation is denied; no connect, DNS, listener or packet is attempted |
| Cgroup | Child belongs to this exact transient system.slice unit |
| Resource limits | Child reads memory.max=134217728, memory.swap.max=0, pids.max=24 and CPU quota/period=0.5 |

This is not a workload, OOM, fork-limit or CPU-throttling stress test. Reading
effective cgroup settings is distinct from proving resource exhaustion behavior,
capacity, recovery under load or a whole-host default-deny firewall.

## Termination, cleanup and output

systemd owns the 10-second execution deadline independently of the controller;
inherited start/stop deadlines are 10 seconds each and KillMode is control-group.
The controller bounds systemd-run to 35 seconds. Normal errors and handled
SIGINT/SIGTERM trigger cleanup. If a unit remains, cleanup verifies its transient
flag and unique description before stopping only that unit. It never stops the
H2a placeholder or a foreign service. `--collect` permits collection after success
or failure. The controller requires the transient unit and its private temporary
directories to disappear, then verifies H2a again before reporting success.

SIGKILL, power loss, broken SSH or kernel failure cannot guarantee that a final
result is returned. The manager deadline remains independent while systemd is
running; an uncertain outcome is not success and does not authorize an unchanged
retry. Diagnose the exact remaining unit/state first. This is not reboot or
controller-crash qualification.

Only a fixed sequence of named PASS records is accepted. Malformed, missing,
duplicated, reordered or unknown child output cannot prove success. Raw stderr,
account records and unexpected exception text are not printed. systemd may retain
ordinary no-secret service lifecycle metadata; journal isolation is not claimed.

Successful final line: `RESULT H2B_BASIC_SANDBOX_OK_NO_RUNTIME`.
On a STOP, runtime stays off and no automatic retry, reinstall or permission
relaxation follows. This script installs no packages, edits no persistent files,
creates no account, changes no firewall/cloud policy and activates no real agent.
systemd creates and removes its own transient unit/private directories.

## Required validation and next boundary

Eleven local tests cover hash rejection, fixed profile, strict evidence sequence,
acknowledgement-before-actions, collisions, error/interrupt cleanup, refusal to
stop foreign units, leftover cleanup rejection and redacted diagnostics.

The mandatory Ubuntu 24.04 CI job uses actual systemd 255, account tools, kernel
cgroups and namespaces. It installs an owned H2a fixture on the disposable runner,
normalizes any developer-writable parent directory entry to root-owned/non-writable
for the fixture and restores its exact original metadata afterwards, then
tests success, failed-child redaction/collection, and a stricter one-second
manager deadline, then removes the fixture through the H2a bounded rollback.
The CI global-host swap precondition alone is synthetic because runner swap is
outside this fixture's scope; no host swap setting is changed. Actual per-cgroup
zero-swap remains tested. Production uses all unmodified H2a host preconditions.
No offline test is live Lightsail evidence. All required CI must pass on the
exact pinned implementation before the phone command is delivered.

Full H2-H7 qualification remains incomplete even if H2b passes: bounded private
tmpfs/secret handoff, stronger syscall/local-socket boundaries, whole-host ingress
and default-deny egress, TLS, memory/process/CPU stress, application compatibility,
capacity and reboot/recovery need their own concrete bounded work. All runtime,
provider, credential, prediction, data-fetch, scheduler and report gates stay off.

Primary sources reviewed at systemd v255:
[systemd-run](https://github.com/systemd/systemd/blob/v255/man/systemd-run.xml),
[service deadlines](https://github.com/systemd/systemd/blob/v255/man/systemd.service.xml),
[execution isolation](https://github.com/systemd/systemd/blob/v255/man/systemd.exec.xml),
[resource controls](https://github.com/systemd/systemd/blob/v255/man/systemd.resource-control.xml).

# H2d: bounded synthetic process-failure verification

Prepared after the user's H2c success screenshot at 2026-10-02 01:16 JST
and continuation at 01:18 JST. H2d live execution succeeded at 01:38 JST: IMG_8928
shows all ten PASS records and `RESULT H2D_SYNTHETIC_PROCESS_FAILURE_OK_NO_RUNTIME`,
followed by the shell prompt. [PR #170](https://github.com/bzlove178100/-keirin-ai-web/pull/170)
records this separate user-supplied evidence at immutable commit
`d27a9db571b6496642fae7046b6220406cac0ee3`, script SHA-256
`fb7745501818a395af1beaea04145e6abc34a43e2d08a0871be3116b767932e5`.
Do not repeat this completed test. This closes a
specific gap: previous H2c tested a hung child while its launcher remained alive;
it did not inject service-parent death or launcher death on this host profile.
Existing application parent-death and Docker recovery fixtures are separate
CI evidence, not evidence for the current Lightsail systemd host.

Implementation: `review/secret_custody_h2d.py`. Default `inspect` is read-only.
The fixed action is `run --approve H2_SYNTHETIC_PROCESS_FAILURE_V1`. The token
is an accident guard for the authorized continuation, not a new approval flow.
This adds no persistent hardening or actual application runtime.

## Scope and pinned inputs

The phone command pins an immutable commit and verifies the H2d script hash.
H2d accepts only three source files separated by `--H2D-VALIDATOR--` lines.
All hashes must match before any source executes:

| Source | SHA-256 |
| --- | --- |
| H2a | `8e4ff9838829ce466b9913ea2dd39e2b5adf1854eacec96925fe9ac5e594a0f1` |
| H2b | `b3c6513d382623f732fc9634ffe414b34c0da93048ce351df17cd2429a70d0bf` |
| H2c | `d9564bc9ea308ad5584e866c3443c09a04829feda8e5bc5d7ca5bf90134cd166` |

Two sequential, uniquely named transient services use the H2c private-tmpfs
profile and every inherited H2a service restriction. The installed H2a placeholder
is never started, edited or restarted. Only the test payload changes, the runtime
ceiling tightens from ten to six seconds and the stop grace tightens from ten to
one second. The limits are not a capacity test. The tests sleep rather than burn
CPU, allocate only one sealed 64-byte synthetic record per case and do no network I/O.

Unlike H2b/H2c, H2d temporarily retains failed-unit metadata by omitting
`--collect`. This allows reliable manager failure-reason read-back, rather than
racing automatic garbage collection. After checking the dead processes, cleanup
stops/resets only the unique unit whose transient flag and exact description
match. It then requires unit disappearance, absent cgroup and no matching
systemd-private temporary directories. An unrelated unit is never adopted,
stopped or reset. No account-wide kill, globbed reset-failed or raw service PID
signal is used. A pre-existing name fails before entering cleanup.

## Two measured failures

Both services use a fixed parent and one executable child. Before data handling,
both disable/read back dumpability and verify NoNewPrivs and zero core limits.
The parent creates the sealed anonymous record and passes only its descriptor
and a readiness pipe explicitly. The child verifies record size, ownership,
permissions, checksum and seals, then ignores SIGTERM and retains the record.
Neither process has a parent-death signal: the purpose is to test the independent
systemd fallback. There is no real credential and no record/checksum in a log,
argument, environment variable or named file.

The root observer accepts only a bounded readiness line containing two process
IDs into its private pipe. It checks the manager's exact main PID, service state,
cgroup and deadline/kill/restart properties. It opens pidfds and verifies both
processes' dedicated UID/GID and exact unit cgroup, parent-child relationship and
the child's actual SIGTERM-ignore mask before injecting a fault.

1. **Service-parent death:** an ownership-checked `systemctl kill --kill-whom=main
   --signal=SIGKILL` targets only the unique test unit's main process. The manager
   must report `Result=signal`, no restart and failed state. Both original
   processes must terminate and be reaped even though the child ignores SIGTERM.
2. **Launcher death:** the observer kills/reaps its own direct `systemd-run`
   subprocess with SIGKILL. The service must first remain active with the same
   verified profile, proving this is a real orphaned-launcher case. The observer
   does not call stop during observation. The manager must independently reach
   `Result=timeout`, no restart and failed state; both service processes must be
   terminated and reaped before fallback cleanup begins.

Pidfd readiness alone is insufficient: a zombie fails the accompanying original
PID/start-time check. Changed/reused PID identities are not signalled. Cleanup
after an error is required but cannot convert the failed assertion into success.
The H2a lock spans both cases; exact installed files, gates, inactive placeholder,
absence of service-identity processes and host /run mount identity are checked
before/after and between cases. Output contains only fixed PASS/STOP records.

Readiness is bounded by five seconds, manager observation by twelve seconds,
individual state commands by three seconds, and inherited fallback stop/cleanup
waits remain bounded. A normal run takes roughly ten seconds after downloads.
The kernel/systemd manager must remain responsive; these are not hard real-time
or power-loss guarantees. Repeated user interrupts can prevent final evidence.

Expected final line after ten PASS records:
`RESULT H2D_SYNTHETIC_PROCESS_FAILURE_OK_NO_RUNTIME`.
On STOP, missing completion or connection loss, retain the output and diagnose;
do not blindly repeat a fault injection or retry installation.

## Validation and interpretation

Twelve offline tests cover all-source tampering before exec, inherited profile,
acknowledgement before host access, strict/partial readiness, zombies/PID reuse,
identity-handle cleanup, foreign-unit protection, failure-reason rejection,
fallback not masking failure, default inspect and error redaction.

Four mandatory real-systemd Ubuntu 24.04 CI cases exercise both actual deaths,
unexpected output cleanup, child rejection of a corrupted record and a deliberately
wrong manager-result assertion that must stay failed despite successful cleanup.
The existing owned disposable H2a CI fixture supplies real accounts/files/systemd
and rolls them back. Only its global swap precheck is synthetic; production's
no-active-swap guard remains intact. CI parent-directory metadata is tightened
and restored by that fixture. Local offline success does not substitute for CI
or the separate user-supplied live result recorded above.

This qualifies only these process-failure scenarios and this fixed transient
profile. The verification controller itself stays alive: launcher death is not
proof of full controller reconciliation, SSH-loss recovery or a power failure.
If that observer is killed, the manager still has the configured deadline, but
final cleanup/result is unconfirmed and failed-unit metadata may remain. Reboot
recovery, unexpected restart, every local IPC/syscall route, application load,
host-wide default-deny egress and TLS trust remain outside this step.

No packages, persistent settings, firewall rules, credentials, IAM permissions,
providers or databases are changed. Ordinary no-secret systemd lifecycle logs
can persist. All runtime/provider/credential/prediction/data-fetch/scheduler/report
gates remain OFF; the candidate remains **untrusted / no-secret** pending the
remaining qualification and separately scoped activation.

Primary references: [systemd v255 service lifetime](https://github.com/systemd/systemd/blob/v255/man/systemd.service.xml),
[systemd v255 kill behavior](https://github.com/systemd/systemd/blob/v255/man/systemd.kill.xml),
[systemd v255 launcher](https://github.com/systemd/systemd/blob/v255/man/systemd-run.xml),
[Linux pidfd lifetime](https://man7.org/linux/man-pages/man2/pidfd_open.2.html).

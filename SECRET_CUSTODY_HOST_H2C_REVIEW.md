# H2c: bounded synthetic memory verification

Prepared after H2b live success (IMG_8926, 2026-10-02 00:46 JST, PR #168)
and the user's continuation at 00:59 JST. This is one temporary no-secret test,
not a persistent installation, actual credential handoff or runtime activation.
H2c live execution remains pending until its separate terminal result is observed.

Implementation: `review/secret_custody_h2c.py`. Default `inspect` is read-only.
`run --approve H2_SYNTHETIC_MEMORY_V1` is the fixed bounded action. The token is
an accident guard, not an extra permission prompt for the existing continuation.

## Trust and lifecycle

The controller accepts exactly the H2a/H2b source bundle over stdin, separated by
a `--H2C-VALIDATOR--` line. Both hashes must match before either source is executed:

| Source | SHA-256 |
| --- | --- |
| H2a | `8e4ff9838829ce466b9913ea2dd39e2b5adf1854eacec96925fe9ac5e594a0f1` |
| H2b | `b3c6513d382623f732fc9634ffe414b34c0da93048ce351df17cd2429a70d0bf` |

The verified H2b lifecycle is reused verbatim with a private module instance:
H2a pre/post drift guards and lock, unique transient unit, no adoption of an
existing name, fixed description ownership, manager deadline 10 seconds,
control-group stop, bounded command waits, strict output, collection and cleanup.
All H2a Service protections remain. The installed placeholder is never started.
Only fixed H2c probe code, expected evidence, acknowledgement, unique name and the
additional private mount differ. No caller-selected payload, path or property
is accepted. The child starts with system Python `-I -B` and a cleared environment.

## What this measures

One `keirin-custody-h2c-<uuid>.service` gets a private tmpfs over its existing
`/run` path. No host directory is created. Options fix 1048576 bytes, 128 inodes,
dedicated UID/GID, mode 0700, nosuid/nodev/noexec/noswap. It hides host /run entries
in this transient namespace. Actual mount type, identity, mode, byte/inode limit
and flags are checked. This is not a capacity/exhaustion test.

The original H2b basic checks also run inside this changed profile to detect
interference with isolation and cgroup settings; this is not a request to repeat
the previous standalone H2b operation. Only a one-byte anonymous temporary file
is written on the new mount, then closed. Its link count must be zero and mode 0600.

The service disables and reads back process dumpability before generating any
synthetic record. Core limits were already checked as zero. A 32-byte random
synthetic value plus its 32-byte SHA-256 checksum is written into an anonymous
memfd. It is mode 0600, non-inheritable by default, then sealed against writes,
growth, shrinkage and further seal changes. This 64-byte object uses a separate
memory backing from the private /run mount: its sealed size and the existing
128 MiB memory/zero-swap cgroup bound it, not /run's 1 MiB limit. Production also
retains the full host no-active-swap guard.

Only its descriptor number is passed to a fixed executable child via explicit
pass_fds, with other descriptors closed. No synthetic value/checksum is put in
argv, environment, a named file or external output. After exec the child again
disables/reads back dumpability and checks NoNewPrivs/core limits before reading
the descriptor. It checks regular anonymous file metadata, exact 64-byte size,
required seals and checksum; actual write, grow and shrink attempts must return
EPERM. It closes the descriptor and emits only `HANDOFF_OK` into its parent's
private captured pipe. Unknown child output or timeout fails closed.

The service then closes its own descriptor and checks EBADF. Service collection,
no remaining service-identity process, removal of systemd private temporary
directories, unchanged H2a files/unit and unchanged controller /run device/inode,
mount namespace and /run mount entry are required before final success. As with
H2b, SIGINT/SIGTERM attempt owned cleanup; SIGKILL, SSH loss or power loss can
prevent a final result. No automatic retry follows an uncertain outcome.

Successful final line: `RESULT H2C_SYNTHETIC_MEMORY_OK_NO_RUNTIME`.
It follows 20 measured PASS records and one cleanup/read-back PASS record.

## Validation

Ten offline tests cover source tampering before exec, isolated controller
instances, preserved profile plus exact tmpfs property, acknowledgement before
host operations, host-mount drift, inherited error handling, strict extended
evidence, output redaction and default read-only behavior.

Five mandatory real systemd Ubuntu 24.04 CI cases cover actual success, generic
child failure, a stricter one-second manager deadline, corrupted record rejection
and missing-seal rejection by the actual executable child. The latter deliberately
fault-injects only the CI parent seal gate to exercise independent child validation.
The fixture reuses H2b's owned H2a installation and bounded rollback. As before,
only the disposable runner's global swap precheck is synthetic; real cgroup swap
and tmpfs noswap remain checked. The fixture temporarily tightens/restores /opt
parent metadata when necessary. Production trust checks are not relaxed.

Require all exact-head CI workflows to pass, merge/read back, then give one
immutable hash-checked phone command. Work has no independent live SSH session.
CI success and the future user-supplied live result must be recorded separately.

## Limits and next work

This establishes only the measured synthetic primitive/profile. It does not
authorize real secrets or permanently apply this profile. It does not prove
cryptographic memory erasure, protection from root/kernel compromise, every
same-identity access route, all inherited/local sockets, application compatibility,
host-wide default-deny egress, transport trust, workload capacity or crash/reboot
recovery. Python memory objects may have copies until process exit; dropping
references must not be described as proven zeroization.

No credential store, database, provider, cloud API or network endpoint is contacted.
No packages, accounts, persistent configuration, firewall rules or machine settings
are changed. systemd may retain ordinary no-secret service lifecycle metadata.
All runtime/provider/credential/prediction/data-fetch/scheduler/report gates stay
OFF. The host remains untrusted/no-secret pending remaining qualification.

Primary references: [systemd v255 execution isolation](https://github.com/systemd/systemd/blob/v255/man/systemd.exec.xml),
[Linux tmpfs](https://cdn.kernel.org/doc/html/latest/filesystems/tmpfs.html),
[memfd_create](https://www.man7.org/linux/man-pages/man2/memfd_create.2.html),
[dumpability](https://www.man7.org/linux/man-pages/man2/PR_SET_DUMPABLE.2const.html).

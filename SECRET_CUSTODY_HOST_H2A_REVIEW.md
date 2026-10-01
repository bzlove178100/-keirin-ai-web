# H2a identity and inactive service preparation

Status: implementation prepared offline; **live apply not yet authorized or performed**.
The candidate remains **untrusted / no-secret**. This is a small part of H2,
not completion of H2-H7 and not approval to activate an agent.

## Why this step exists

The created Tokyo candidate passed H1 at 23:23 JST on 2026-10-01. The next
bounded change creates the identity and root-controlled files needed for later
sandbox qualification. It deliberately installs no runtime payload. Existing
SSH administration remains the user's working Termius connection.

Implementation: [`review/secret_custody_h2.py`](review/secret_custody_h2.py).
It uses the Ubuntu system Python standard library and fixed absolute paths.
No package installation or additional cloud resource is needed.

## Exact proposed mutation

| Object | Proposed state |
| --- | --- |
| User/group `keirin-custody` | New system identity; locked password; `/usr/sbin/nologin`; no home creation; no supplementary groups |
| `/opt/keirin-custody` | Empty, root:root, mode 0755; reserved code directory |
| `/etc/keirin-custody` | root:keirin-custody, mode 0750 |
| `/etc/keirin-custody/gates.json` | Non-secret declaration, mode 0640; all seven runtime/provider/prediction/data-fetch/scheduler/report/credential gates false |
| `/etc/systemd/system/keirin-custody.service` | root:root, mode 0644; static inactive placeholder; manual start refused; only executable is `/usr/bin/false`; no install section |
| `/var/lib/keirin-custody-h2/receipt.json` | Root-only transaction receipt, directory 0700/file 0600; schema, random ownership tag and allocated UID/GID only |
| systemd manager | `daemon-reload`, followed by read-back; no start/enable/restart/stop operation |

Standard `useradd`/`userdel` tools update the local account databases and may
maintain their normal backups/locks. Rollback removes the package account by
name; it never restores an entire old password/group database over other users.

The placeholder declares no-new-privileges, empty capabilities, strict system
filesystem protection, protected home/kernel/control groups, private temporary
and device/network namespaces, AF_UNIX only, no core dumps, MemoryMax 128 MiB,
MemorySwapMax 0, TasksMax 24, CPUQuota 50%, and whole-control-group termination.
These are **candidate settings, not live effectiveness or workload-capacity evidence**.
The gates file is an inactive declaration, not a new enforcement integration
with an existing application. No real agent, credential or connection profile
is installed or launched. In particular, this does not prove bounded temporary
storage, memory-only secret handoff, OS-wide default-deny egress or log isolation.

SSH user/key/configuration, Lightsail/OS firewall rules, network routes, packages,
swap, kernel settings, AWS/IAM resources, paid plan, Supabase and application
state are outside this script's mutation set. There is no reboot or network
request in the Python program. Downloading its immutable source later is a
separate bootstrap operation, not runtime egress qualification.

## Preconditions and result meanings

The script checks root execution, Ubuntu 24.04, systemd 255 as PID 1, cgroup v2,
disabled swap, required existing tools, trusted parent directories, absent
target identity/paths and absent loaded unit before the first mutation. It
refuses to adopt or overwrite an existing object. These are immediate mutation
preconditions; the completed H1 procedure need not be repeated.

| Action | Behavior / successful final line |
| --- | --- |
| `inspect` (default) | Read-only readiness; `RESULT READY_FOR_SEPARATELY_APPROVED_H2A` |
| `apply --approve H2_IDENTITY_FILES_V1` | Creates the exact objects; verifies them; `RESULT INSTALLED_DISABLED_NOT_QUALIFIED` |
| `verify` | Read-only identity, lock/group, exact file bytes/modes/owners, no-process and inactive/static manager read-back; same installed result |
| `rollback --approve H2_REMOVE_OWNED_FILES_V1` | Deletes only proven package-owned artifacts and identity; `RESULT ROLLED_BACK_NO_RUNTIME` |

Use `/usr/bin/python3 -I -B` with source from a reviewed immutable commit and
verify its exact SHA-256 before execution. The future phone command must pin
both values and abort on download/hash mismatch. Never copy a branch URL into
a root execution pipeline. The acknowledgement values prevent accidents;
they do not grant authorization. Present this exact scope to the user before
any live apply. Existing creation/H1 approval does not cover host hardening.

## Failure and rollback

An exclusive root-only receipt directory prevents reapplying on partial state;
an advisory lock serializes package mutation. New files use exclusive creation
with symlink rejection. Receipt replacement is atomic and fsynced. No command
output, shadow field, process command line, environment, IP or key material is
printed. Subprocesses have a fixed environment, no shell and a 20-second timeout.

On any `STOP`, preserve the exact fixed error/result lines and **do not retry
apply**. No automatic rollback, service start, forced user removal or process
kill follows an error. Review the failed stage before proposing the bounded
rollback under its own acknowledgement. Rollback checks all remaining artifacts
before deletion, including contents, modes/ownership, absence of extra directory
entries, no symlinks/hardlinks, matching account ownership tag/UID/GID, locked
non-login identity, no shared groups/processes, and inactive/unmodified unit state.

Rollback permits absent files from an interrupted apply/removal. It refuses
modified files, foreign contents, active/enabled/overridden units, foreign
identity state or an incomplete receipt write. A group-only useradd failure
without a recorded GID is unproven and requires diagnosis. Interrupted bytes,
extra receipt files or an empty receipt directory may likewise require manual
review; the tool does not guess ownership or recursively delete them. Keep the
working administrator connection open. Do not relax SSH/egress rules to recover.

Scope assumes a trusted administrator with no concurrent out-of-band root edits;
it is not protection against a hostile root user or global account database
corruption. Receipt updates are durable, but this stage makes no power-loss or
reboot-recovery qualification claim. `daemon-reload` does not start this unit;
unrelated administrator changes in the manager remain outside this review.

## Validation and remaining boundary

`tests/test_secret_custody_h2.py` uses actual temporary-file metadata and fully
synthetic account/process/systemd adapters. Its 28 tests cover refusal before
mutation, file/identity collisions, partial failure recovery, exact read-back,
repeat-apply refusal, rollback drift/process protections, locking, sanitized
errors and systemd unit syntax. The required `custody-h2-offline` job runs on
Ubuntu 24.04 with real UID/GID mappings and forbids skipped ownership tests.
No test creates a real host account or activates a service.

The local Work sandbox maps only UID/GID 0. Five boundary/syntax tests passed
there; 23 filesystem transaction tests are explicitly skipped locally and must
pass in CI before merge. Its non-systemd PID 1 was correctly rejected by the
read-only CLI. CI is offline evidence, not an observation of the Lightsail host.

After separate approval and one successful apply, retain sanitized live result
lines and run the read-only verify. Only then plan the next bounded effective
sandbox/resource/network tests. C2 schema, real credential use and runtime
activation still need their existing independent gates/authorization. The H1
evidence, original declarative hardening plan and recovery review remain valid.

Primary references: [Ubuntu 24.04 useradd](https://manpages.ubuntu.com/manpages/noble/man8/useradd.8.html),
[systemd unit](https://www.freedesktop.org/software/systemd/man/systemd.unit.html),
[systemd execution](https://www.freedesktop.org/software/systemd/man/systemd.exec.html),
[systemctl 255](https://www.freedesktop.org/software/systemd/man/255/systemctl.html).

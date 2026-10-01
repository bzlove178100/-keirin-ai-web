# H2a identity and inactive service preparation

Status: **live H2a apply authorized at 2026-10-01 23:56:43 JST; first attempt failed**.
The correction and recovery tests below are pending their exact-commit CI gate.
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
they do not grant authorization. Present the exact scope to the user before
any initially unapproved live apply. The user subsequently approved this exact
H2a scope at 23:56:43 JST; that approval also covers its bounded correction and
recovery. Do not request it again. Creation/H1 alone would not have covered it.

## Failure and rollback

An exclusive root-only receipt directory prevents reapplying on partial state;
an advisory lock serializes package mutation. New files use exclusive creation
with symlink rejection. Receipt replacement is atomic and fsynced. No command
output, shadow field, process command line, environment, IP or key material is
printed. Subprocesses have a fixed environment, no shell and a 20-second timeout.

On any `STOP`, preserve the exact fixed error/result lines and **do not retry
apply**. No automatic rollback, service start, forced user removal or process
kill follows an error. Review the failed stage before using the bounded
rollback under its own CLI acknowledgement. The current H2a recovery is within
the existing user authorization; the token is not a request for new approval. Rollback checks all remaining artifacts
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

## First live failure and bounded correction

The first attempt used commit `5cc75aa40523e405ccd0a6515386d3a41eeb886d`,
SHA-256 `50a92a2b0c4585cc965a91faf737d81d337408573cf2668dd26dc49a825473e1`.
Screenshot IMG_8923 at 2026-10-02 00:00 JST shows `STOP HOST_COMMAND_FAILED`;
no completed installation or runtime qualification follows from that attempt.

IMG_8924 at 00:06 JST confirms the receipt directory is present, user/group
are absent (getent exit 2), reserved code/config directories and unit are absent,
and systemd reports not-found/inactive with show exit 0. The existing receipt
contents are not independently confirmed; rollback must validate them first.

The implementation incorrectly passed `--key CREATE_MAIL_SPOOL=no` to useradd.
That option only accepts login.defs keys, while CREATE_MAIL_SPOOL belongs to
useradd defaults. Shadow 4.13's [useradd source](https://github.com/shadow-maint/shadow/blob/4.13/src/useradd.c)
rejects unknown `-K` keys and already skips `create_mail()` when `--system` is
used; its [login.defs registry](https://github.com/shadow-maint/shadow/blob/4.13/lib/getdef.c)
has no CREATE_MAIL_SPOOL key. The observed partial state matches this failure.
Remove this invalid override, retaining system/non-login/locked/no-home options.
Command failure codes now identify fixed stages (e.g. USER_CREATE_FAILED) without
printing subprocess diagnostics, account fields or secrets.

Keep schema `keirin-custody-h2a-v1`: the original receipt remains recognizable.
After exact-head CI and merge, download the corrected script by immutable SHA,
check its SHA-256, run `rollback --approve H2_REMOVE_OWNED_FILES_V1`, and proceed
to `apply --approve H2_IDENTITY_FILES_V1` only if rollback exits zero. The existing
rollback validates ownership, metadata, receipt, remaining files, identities
and inactive unit before removing anything. Do not delete the directory manually
or retry the old apply. Follow with read-only verify and retain phone results.
This is recovery under the existing approval, not additional runtime authority.

## Validation and remaining boundary

`tests/test_secret_custody_h2.py` has 29 tests: real temporary-file metadata,
synthetic account/process/systemd behavior, collision/drift/process/locking and
partial-failure recovery, sanitized stage errors, and systemd unit syntax.
Local Work passes six boundary/syntax tests; 23 ownership tests require the
no-skips Ubuntu 24.04 CI job because Work maps only UID/GID 0.

`tests/test_secret_custody_h2_cli.py` adds two mandatory integration cases using
the actual Ubuntu 24.04 useradd/userdel/groupdel/passwd executables. A test-only
adapter injects `--root` pointing to a disposable chroot with synthetic account
databases; production gets no configurable root option. No runner account or
live AWS machine is changed. Manager/process behavior remains synthetic.
The tests reproduce the old invalid argument, verify receipt-only partial state,
perform ownership-checked recovery, then corrected apply/verify/removal. They
check locked system identity, non-login shell, absent home/mail even with mail
creation enabled in fixture defaults. They do not bypass audit restrictions;
local Work cannot run this CLI boundary, so CI success is required.

No offline success proves live installation, service enforcement or full H2-H7
qualification. Await successful phone apply and verify before planning effective
sandbox/resource/network tests. C2 schema, real credentials and runtime activation
retain their independent gates. H1 and the original recovery review remain valid.

Primary references: [Ubuntu 24.04 useradd](https://manpages.ubuntu.com/manpages/noble/man8/useradd.8.html),
[systemd unit](https://www.freedesktop.org/software/systemd/man/systemd.unit.html),
[systemd execution](https://www.freedesktop.org/software/systemd/man/systemd.exec.html),
[systemctl 255](https://www.freedesktop.org/software/systemd/man/255/systemctl.html).

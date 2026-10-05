# Disposable guest suspend/boot foundation — no live activation

## Packet experiment added after the foundation (2026-10-05)

The first packet CI attempt stopped before VM launch: job 111758239014 failed
while resolving an assumed standalone nft_counter module. Remove that standalone
module assumption and require the actual counter-bearing nft rule installation
and live snapshot to succeed. Dependency failures now preserve stderr. No timing
or packet requirement is relaxed; a new commit, not an unchanged rerun, tests this.

Second packet job `111759564417` built the image and booted the guest, then PID 1 exited with status 1 before packet evidence. The old parser discarded non-record stderr/console lines, so the underlying Python startup cause is NOT yet known. Preserve a bounded pre-failure console tail (32 lines/4000 characters), with a regression for preceding import errors. Local chroot reproduction was refused by this environment (operation not permitted), not treated as a guest result. The next changed CI must identify the startup cause before any success claim; packet and timing conditions are unchanged.

Third job `111761887414` resolved the startup cause: `_Py_HashRandomization_Init` could not obtain random numbers before Python initialization. The initramfs omitted /dev/urandom; add fixed guest character nodes for urandom (1:9) and null (1:3), without copying host entropy or disabling Python hash randomization. These are synthetic experiment runtime inputs, not cryptographic-entropy qualification. Review also found that the peer inherited the original sysfs mount; use socket.if_nameindex() to inspect the actual current network namespace, retaining the exact lo/peer0 and lo/host0 assertions. Kernel sysfs-tagging documentation explains the mount-specific namespace view: https://cdn.kernel.org/doc/html/latest/networking/sysfs-tagging.html . Packet/S3/clock gates remain unchanged; actual packets remain pending.

The foundation below completed in PR #204; it remains a separate mandatory job.
The new experiment runs two fresh guests using the same diskless/no-NIC QEMU
command. Inside each guest only, a veth connects a distinct peer network namespace.
Fixed 192.0.2.1/2 and 2001:db8:1::1/2 addresses carry TCP/443 qualification and
TCP/22 management echo. No guest route or backend reaches the real network.

The bounded initramfs contains the fixed guest code, existing qualification
renderer, system Python/ip/nft/kmod and their packaged libraries, and matching
installed kernel modules discovered with read-only modprobe --show-depends.
The experiment driver never inserts host modules or alters host networking. Module/image/kernel/emulator
hashes are printed; no host environment, secrets, configuration or /etc is copied.

Both cases first prove reachable ports under an empty fresh-boot ruleset. This is
an unprotected-startup negative control and cannot establish safe startup. Next,
install the exact existing eight-second inet/netdev guard once and prove both
existing and new dual-family connections while it is live. Keep original rule
handles/policy and an unrelated sentinel unchanged throughout the measurement.

The awake control waits ten seconds and must deny all qualification probes while
all management probes survive. The S3 case requires actual QMP SUSPEND, suspended
state, twelve host seconds, system_wakeup/WAKEUP and real clock evidence. After
resume, explicit old/new IPv4/IPv6 qualification probes precede any nft read/write.
They must finish within seven monotonic seconds of original installation, while
at least ten boottime seconds elapsed. No worker, controller, refresh or restoration
transaction may run ahead of these probes. This is not a trace of every packet or
proof about the kernel's first post-resume instruction.

All four denied yields SUSPEND_EXPIRY_OBSERVED. All four allowed yields
BLOCKED_SUSPEND_EXPIRY_GAP. Mixed/late/inconsistent observations fail instead of
being interpreted as a successful boundary. The diagnostic job can succeed while
reporting the blocking gap; activation_allowed stays false in either outcome.
Both cases must then show original ordinary awake expiry, management continuity,
unchanged rules and full guest/host-owned cleanup. There are nine mandatory packet
records and 28 regression jobs; the six original VM-foundation records remain.

Actual results are not inferred from upstream source or local models: the final
PR/main receipts contain measured packets, clocks, boot IDs and exact input hashes.
The existing upstream source finding below does not establish a version-matched
clock implementation. Closed-policy startup ordering, external authenticated
management, arbitrary endpoints, privileged edits and live installation remain
unqualified. All activation gates remain OFF.

The new mandatory CI job builds a static C PID 1 and a minimal initramfs containing
only that program and its initial console. An unprivileged Python supervisor runs
QEMU TCG with the disposable runner's installed kernel copied as read-only input.
The manifest prints the actual kernel release, kernel/initramfs/QEMU SHA-256 and
emulator version. No new host kernel is installed. QEMU packages are installed
only in the disposable CI runner; their package scripts may install service metadata
(the observed log creates qemu-kvm.service). The experiment explicitly uses TCG and
does not invoke that service or KVM. Package-script side effects are not claimed
absent. No cloud resource or hosted runtime is enabled.

## Isolation and observation contract

- Fixed arguments disable default devices, user configuration and all guest NICs.
  No disk, host filesystem share, passthrough device, KVM, or network backend exists.
  QMP query-block must be empty and the guest must report only loopback.
- QEMU runs as the non-root CI user with its syscall sandbox enabled. QMP and serial
  channels and input/output files live in one private temporary directory.
- The C guest refuses ordinary host execution before any mount or power operation.
  Before guest power writes it requires PID 1/root, the fixed kernel opt-in, QEMU
  DMI identity and loopback-only interface inventory.
- An actual guest S3 request must produce QMP SUSPEND and status=suspended. After
  twelve seconds the supervisor requires system_wakeup success and WAKEUP. Guest
  boottime-minus-monotonic elapsed difference must be at least ten seconds and
  bounded by observed host elapsed time plus five seconds; monotonic elapsed must
  be below five seconds. The boot identity and /run marker must survive S3.
- The same guest then requests reboot. Require RESET guest=true, a new boot ID,
  loopback-only inventory and no old marker in the freshly mounted /run.
- Bound every channel read, compiler operation, startup, suspend, reboot and cleanup.
  Unsupported suspend is failure, not skip. A paused VM is not S3 evidence.
  Terminate/reap only the owned QEMU PID; clean only its private directory. Host
  boot/network namespace identity must remain unchanged.

The target six records cover ordinary host refusal, diskless boot, actual S3,
suspend-inclusive clock evidence, reboot identity/fresh /run, and owned cleanup.
This foundation deliberately has no firewall or recovery worker. A successful
clock/boot record cannot imply packet expiry, safe startup order, durable recovery
claims or authenticated management access. No real host suspend/reboot occurs.

## Source findings and next packet experiment

The [retrieved upstream nf_tables header](https://github.com/torvalds/linux/blob/master/include/net/netfilter/nf_tables.h)
uses get_jiffies_64 in nft_set_elem_expired. This is a moving upstream reference;
the attempted v6.17 source retrieval failed, so it is not identified as the exact
runner source or used to claim suspend-time packet behavior. A version-matched
inspection and the guest packet experiment remain necessary.

[QEMU's QMP manual](https://www.qemu.org/docs/master/interop/qemu-qmp-ref.html)
distinguishes paused from suspended states and documents SUSPEND/WAKEUP, guest
reset evidence and the wakeup capability check. The
[invocation manual](https://www.qemu.org/docs/master/system/invocation.html)
documents disabling default NICs/devices/config and the syscall sandbox.
[Linux sleep-state documentation](https://docs.kernel.org/admin-guide/pm/sleep-states.html)
describes selecting deep suspend through mem_sleep before requesting mem.

Next, add an internal fixed-address peer and positive/negative packet controls,
then observe qualification and management packets immediately after S3 before any
userspace policy refresh. Record original kernel set/rule identity and elapsed
clocks, and compare with ordinary awake expiry. Separately test startup with and
without the intended closed policy before enabling a guest link. This is future
work; the current job neither constructs that policy nor proves its behavior.
All production/runtime/provider/credential/prediction/DB/data-fetch/scheduler/report
gates remain OFF.

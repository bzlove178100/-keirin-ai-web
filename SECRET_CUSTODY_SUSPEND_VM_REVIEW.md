# Disposable guest suspend/boot foundation — no live activation

The new mandatory CI job builds a static C PID 1 and a minimal initramfs containing
only that program and its initial console. An unprivileged Python supervisor runs
QEMU TCG with the disposable runner's installed kernel copied as read-only input.
The manifest prints the actual kernel release, kernel/initramfs/QEMU SHA-256 and
emulator version. No new host kernel or host service is installed. QEMU is installed
only in the disposable CI runner; no cloud resource or hosted runtime is enabled.

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

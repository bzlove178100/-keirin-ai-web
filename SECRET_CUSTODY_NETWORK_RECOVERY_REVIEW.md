# Independent recovery rehearsal and private dependency observation

Prepared 2026-10-02 (Asia/Tokyo). Repository/CI scope; no live firewall apply,
runtime activation, new cloud resource, IAM grant or credential use.

## Evidence already completed

PR #173 merged at `180e590d1cede88f1326642170b73856d40deeea` after all five
workflows passed on head `c321c22f89ec56c3432115993371535b0f9cc1dd`.
Regression run `36900487170`, transition job `110498113203`, passed four
offline tests and all seven actual kernel/packet markers, ending in
`SYNTHETIC_NETWORK_TRANSITION_OK_NO_LIVE_APPLY`. That proves the documented
synthetic transport/atomicity/manual fallback cases, not a live policy.
The earlier fixture grammar failure was corrected before this successful run.

The user's H1, H2a/H2b/H2c/H2d and 02:07–02:16 H3 baseline evidence remain
complete in their measured scopes. Do not ask for them again to resume.

## What the new recovery test actually executes

`tests/test_secret_custody_network_watchdog.py` uses the existing IPv4/IPv6
two-namespace veth fixture and fixed documentation addresses. A transient
systemd service enters only that fixture namespace through
`NetworkNamespacePath=/proc/<test-pid>/ns/net`. It refuses PID 1's namespace,
non-root/non-CI contexts and a missing explicit fixture flag. Its own parent
must be PID 1. No rule is installed in the CI runner's host namespace.

The worker reads synthetic expected table shapes into memory, checks an existing
maintenance anchor, publishes readiness and waits on its own monotonic deadline.
The applying child requires that readiness with enough time remaining. The child
then dies by SIGKILL. Recovery does not depend on that child, a shell trap,
an SSH connection, a DNS query or a GitHub request. The observing test parent
stays alive solely to inspect results; it does not perform fallback.

| Actual case | Required outcome |
| --- | --- |
| Child dies before apply | Worker sees maintenance and performs no replacement |
| Child dies after qualification apply | Worker atomically restores exact restricted maintenance |
| An unexpected owned-table rule appears | Worker stops; unknown drift is not overwritten |
| Missing or expired readiness (offline negative cases) | Controller never invokes nft mutation |

After restoration, actual new and established qualification TCP flows must fail,
existing and new administration transports must still pass in both families,
DNS/time fixture traffic must pass and unrelated rules must remain unchanged.
The test proves worker/unit/process cleanup and removes only its private unique
`/run` fixture. `Restart=no`, `RuntimeMaxSec=15`, `TimeoutStopSec=2` and
`KillMode=control-group` bound the service. CI fails rather than skipping these
checks. Local Work lacks namespace privileges, so local unit tests alone are
not kernel/systemd evidence. Exact-head CI results are recorded in the PR.

Initial head `0396f275d7e14ef7672e9480284e34841685dd4d` passed the actual recovery
job `110510991785` in run `36904340074`, including all three death/drift cases
and cleanup. The local dependency job `110510991708` failed its DNS parser
assertion on actual Ubuntu output. Inspection of pinned v255 `busctl.c` shows
that a property variant's array is unwrapped, unlike a method reply's argument
array. It also shows that `get-property` does not apply `arg_auto_start`.
The correction uses explicit `call ... Properties.Get ss ...`, which applies
`--auto-start=no`, and parses its typed variant correctly. Fixtures cover that
wire format, multiple families and empty arrays; no assertion is removed.
The corrected head `e0ae01e3d92d84e4f127e997cd36bcd9b54a3864` subsequently passed all five workflows and merged in PR #174. Regression run `36904707742` passed recovery job `110512222225` and dependency job `110512222345`.

`flock` serializes the cooperating fixture controller/worker. It is **not** an
nft generation compare-and-swap, an exclusion mechanism against other root
writers, or proof that the watchdog cannot die after readiness. A runtime
readback/mutation race, persistent authenticated manifests, verified code
ownership, cancellation/acknowledgment, boot recovery and live deployment are
not implemented by this test. A process-death case is not a power-loss test.

## Bounded local dependency reader

`review/secret_custody_network_dependencies.py` has no installation/apply mode.
It requires the root/systemd host namespace context and runs seven fixed readers,
each with a five-second deadline and a 256 KiB stdout ceiling. Stderr is discarded;
errors are reduced to fixed codes. No arbitrary shell command or diagnostic text
is executed/emitted. It reads local Netlink, D-Bus and a specific Chrony Unix
socket; `--auto-start=no` prevents D-Bus service activation and `chronyc -n -c`
with an explicit Unix socket prevents DNS lookup/network fallback.

| Reader | Selected private evidence | Limits |
| --- | --- | --- |
| `ip -j address show` | Interface/index, local address/prefix/scope | Current snapshot, not approved ownership |
| `ip -j -4/-6 route show table all` | Destination, gateway, device, protocol, table | Complex routes explicitly marked unmodeled |
| networkd Manager `Describe` | Selected address/route/DNS/NTP values and configuration provider/source | No raw leases, vendor data, SSID, MAC or configuration dump |
| resolved `DNSEx`/`FallbackDNSEx` | Interface, address, explicit/default port and server name | No lookup; fallback need not be in use; transport policy not qualified |
| Chrony `sources` over its Unix socket | Known source IP, mode and selection state | No config, NTS secrets or inference that ports are approved |
| Validated `KC_SSH_CONNECTION` | Caller-supplied peer/local endpoints | Not independently authenticated by this reader |

Default output is public-safe counts/states only. `--private` explicitly emits
the selected values to stdout and must be kept out of public repositories,
issues, CI logs and artifacts. The tool does not save a file. The phone can
share that result privately in this conversation, not a public GitHub comment.
No credential, PEM or config file is requested. The command loader may make its
one explicit HTTPS download; the reader itself makes no external request.

Unavailable services and parse/bounds failures are `unknown`, not empty evidence.
The final result deliberately says `WITH_UNRESOLVED_ITEMS`; every report has
`qualification=false` and `mutation=false`. Even all readers succeeding does not
authorize or generate firewall rules. A partial report is useful for selecting
the next diagnosis and must not trigger a blind identical retry. Synthetic
parser tests and an actual Ubuntu CI host check catch available-but-unrecognized
reader formats; optional uninstalled services may legitimately be unavailable.

## Remaining live boundary and next step

The immutable corrected reader was executed and its complete selected output
was supplied in IMG_8937–IMG_8946 at 08:17–08:32 JST. The final result is
`LOCAL_DEPENDENCIES_OBSERVED_WITH_UNRESOLVED_ITEMS_NO_MUTATION`.
This observation request is complete; do not repeat it. See the
[maintenance dependency design](SECRET_CUSTODY_NETWORK_MAINTENANCE_DESIGN.md)
for sanitized findings, their limits, concrete next tests and the initial-anchor
blocker. Private endpoints remain outside public GitHub.

Still unresolved: initial maintenance-anchor transition from the unfiltered
baseline, independently usable recovery, authoritative browser-SSH source-range
lifecycle, DHCP renewal and RA/ND/PMTU behavior, DNS/NTP lifecycle and transport,
bootstrap/runtime destinations, non-cooperating rule writers, persistence and
reboot recovery. Browser SSH shares the host network; it is not out-of-band.
The existing no-automatic-relaxation rule forbids using an unfiltered baseline
as fallback. Initial anchor installation cannot be justified by this watchdog
test: an incorrect shared administration allowlist would break both profiles.

Do not start or enable the H2a placeholder, add unrestricted egress/SSH, reset
UFW/nft, retry old H2 apply commands, create resources or request secrets. The
host stays untrusted/no-secret; all runtime/provider/credential/prediction/
data-fetch/scheduler/report gates stay OFF. A future concrete live proposal
requires its own scoped authorization; H2a's approval does not cover it.

## Primary interface references used

- [systemd v255 NetworkNamespacePath](https://github.com/systemd/systemd/blob/v255/man/systemd.exec.xml)
- [systemd v255 networkd Describe JSON builder](https://github.com/systemd/systemd/blob/v255/src/network/networkd-json.c)
- [systemd v255 resolved D-Bus signatures](https://github.com/systemd/systemd/blob/v255/man/org.freedesktop.resolve1.xml)
- [systemd v255 busctl method/variant formatting and auto-start flags](https://github.com/systemd/systemd/blob/v255/src/busctl/busctl.c)
- [Chrony command options and sources](https://chrony-project.org/doc/4.4/chronyc.html)
- [Chrony 4.5 CSV source renderer](https://github.com/mlichvar/chrony/blob/4.5/client.c)

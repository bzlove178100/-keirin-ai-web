# H3/H4: read-only network baseline

Prepared for the user's continuation at 2026-10-02 01:39 JST after H2d live
success at 01:38 JST. H2a-H2d measured bounded local isolation/memory/failure
scenarios; they did not inspect the complete host and Lightsail network policy.
This step collects the missing baseline needed before any concrete firewall plan.
It does not create another fault-injection service or repeat the completed probes.

Implementation: `review/secret_custody_network_readback.py`. Running it performs
only local observations. There is no apply mode, arbitrary command argument,
destination argument, network probe, secret input or service-management action.
The phone loader downloads the immutable hash-checked script; the observer itself
does not contact GitHub, AWS, a provider or any remote endpoint.

## Completed live observation — 2026-10-02 02:07–02:16 JST

The corrected PR #172 observer succeeded at 02:07 with
`H3_HOST_NETWORK_OBSERVED_NO_MUTATION`. Saved cloud rule/source/browser options
were observed at 02:12–02:13. UFW's own status was `inactive` at 02:16.
The [transition review](SECRET_CUSTODY_NETWORK_TRANSITION_REVIEW.md) records the
sanitized facts, immutable script identity, remaining dependencies and next work.
These completed observations supersede the pre-run instructions below. Do not
rerun the completed observer, UFW status or H2 probes merely to resume.

The original generic STOP did not capture its exact failed stage/input. The
corrected success and scoped IPv6 listener are consistent with the independently
reproduced parsing defect; no original exception input is invented. Full firewall
qualification, independent recovery and live apply remain incomplete.

## Historical live failure and scoped IPv6 correction — 2026-10-02 01:56 JST

IMG_8929 shows PR #171's pinned observer ending with
`STOP NETWORK_READBACK_UNAVAILABLE` and
`RESULT H3_NETWORK_OBSERVATION_INCOMPLETE_NO_MUTATION`. No facts were printed.
The readback did not succeed; the screenshot alone does not identify the stage.

A parser defect was independently reproduced: `[fe80::1234]%fixture0:546`
leaves `fe80::1234]` after the original bracket/scope stripping, causing ValueError.
The [iproute2 v6.1.0 ss source](https://github.com/iproute2/iproute2/blob/v6.1.0/misc/ss.c)
shows `inet_addr_print` bracketing the address before `sock_addr_print` appends the
scope. The initial CI tested real unscoped loopback sockets; its synthetic scoped
sample only placed the scope inside brackets. That coverage missed this format.
This defect is confirmed; its responsibility for the live failure remains a
hypothesis until the changed observer completes or supplies a more specific STOP.

The correction parses both `[address]%zone` and `[address%zone]`, as well as
scoped wildcards, and still rejects malformed brackets/zones and invalid addresses.
Fixed STAGE records now distinguish command reads from parsing for nft, IPv4/IPv6
listeners and services, plus host/proc reads. Unexpected exceptions map to fixed
categories (JSON_SYNTAX, TEXT_ENCODING, OS_READ_ERROR, INVALID_VALUE, INVALID_TYPE,
UNEXPECTED_EXCEPTION), never raw exception messages. Successful facts remain
buffered; failure does not skip a read or become empty-policy success.

Mandatory real-kernel CI adds a scope-bearing IPv6 UDP socket on a synthetic
link-local address assigned only to loopback inside its disposable namespace.
It requires a zone-bearing actual ss row and the expected redacted classification.
No host interface, cloud policy or external endpoint is changed. Local regression
reproduced the old failure and the corrected offline tests pass; exact-head CI and
the separate corrected live result must be evaluated independently.

The unchanged failed command must not be repeated. The next phone run uses the
corrected immutable script/hash: success supplies the missing host summary;
failure supplies the fixed STOP/STAGE pair to resolve the remaining branch.
This does not claim full firewall qualification or authorize any mutation.

## Fixed reads and output

The observer requires root read access, systemd as PID 1 and the same network
namespace as PID 1. It runs only these fixed command tuples:

| Read | Reported information |
| --- | --- |
| `nft -j list ruleset` | Table/chain/rule/other-object counts; base-chain family, type, hook, priority and policy |
| `ss -H -n -l -t -u -4` and `-6` | Separate IPv4/IPv6 TCP/UDP listener counts, bind-scope category and numeric port |
| `systemctl show` for nftables/ufw | Load, active and unit-file states only |
| Fixed `/proc` files | Legacy IPv4/IPv6 table counts and forwarding/IPv6-disable flags |

No raw IP address, interface name, table/chain/set name, rule content, comment,
packet counter, process command line, environment value or command diagnostic is
printed. Bind scope is wildcard, loopback, link-local or specific; a wildcard
listener does not establish public reachability. Numeric port and aggregate counts
are retained because they determine what requires review.

Each command has a five-second wait bound, a real output-byte cap and fixed clean
environment. Failures terminate/reap only the observer's own reader subprocess.
The observer buffers all summarized evidence until every required read succeeds;
an error emits a fixed STOP code, not partial success or raw exception text.
Input shape errors, duplicate JSON keys and unknown base-chain formats are not
silently converted into an empty/allowed policy. Missing optional `/proc` files
are explicitly `not_exposed`, distinct from an empty table list or a zero flag.

Successful observation ends with:

```text
FACT cloud_firewall=not_observed
FACT effective_packet_policy=not_qualified
RESULT H3_HOST_NETWORK_OBSERVED_NO_MUTATION
```

This result means the listed host reads succeeded. It is deliberately not named
a firewall PASS. No rule is added/deleted/flushed, no service is started/stopped,
no SSH session is terminated, and no settings, packages or accounts are changed.

## Interpretation and remaining decisions

These are observations at nearby times, not an atomic packet-policy snapshot.
Chain policy alone does not determine effective traffic handling: rule verdicts,
sets/maps, dormant tables, chain ordering, other hooks and other filtering systems
can matter. This limited summary does not evaluate them or claim to inventory
every network enforcement mechanism. Active legacy tables require separate
review; an absent legacy proc entry is not proof that all filtering is absent.
Service enabled/active flags are not proof of effective rules or reboot persistence.

The Lightsail firewall applies to public inbound traffic; it does not restrict
outbound traffic or replace host inspection. Its IPv4 and IPv6 settings must be
read back separately from the instance's Networking view. Work still has no
independent AWS/SSH session, and this change does not expand IAM or dispatch an
additional previously bounded inventory workflow.

The original pre-execution sequence below is historical; steps 1 and 2 are now observed in the limited scopes above. Step 3 continues in the transition review:

1. Obtain one successful phone host-readback result. Retain sanitized facts only
   in public evidence. On STOP, diagnose the fixed code; do not retry unchanged.
2. Read the current Lightsail IPv4 and IPv6 firewall entries using the existing
   phone session. The earlier saved SSH edit screenshot did not expose the full
   rules; do not infer them or overwrite that administration access.
3. Reconcile both observations. If existing rules are nonempty/unknown, inspect
   their private details before proposing a policy. Define exact required runtime
   destinations and a connection-preserving rollback path before any H4 change.
   No blanket egress allow, rule flush, reboot or SSH-source change is implied.

H3/H4 qualification, exact local IPC/syscall/application capacity and full recovery
remain open. All runtime/provider/credential/prediction/data-fetch/scheduler/report
gates remain OFF. The host remains **untrusted / no-secret**; this readback does
not authorize actual application runtime, provider credentials or database use.

## Validation

Sixteen offline tests cover output redaction, empty versus malformed state,
duplicate JSON keys, IPv4/IPv6 bind parsing, unknown service states, absent legacy
proc files, fixed command/path allowlists, wrong namespace, partial-read failure,
real subprocess byte-cap cleanup, timeout, nonzero-exit redaction, both scoped
IPv6 formats, malformed zones and per-stage failure attribution.

Mandatory Ubuntu 24.04 CI also runs a real-kernel fixture inside a disposable
`unshare --net` namespace. It observes an empty ruleset, adds fixture-only nft
chains/rules there, and reads actual TCP/UDP IPv4/IPv6 loopback listeners. The
fixture refuses to run in PID 1's network namespace. Namespace destruction removes
its rules and sockets; no host firewall is edited and no external packet is sent.
Finally the exact production observer runs read-only against the disposable CI
host to cover command paths, full snapshot composition and service output formats.
Exact-head CI must pass before merge/read-back and the phone command. Live host
observation subsequently succeeded at 02:07, separately from CI. The remaining
policy/recovery qualification must not be inferred from either observation.

Primary references: [Lightsail firewall scope](https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-firewall-and-port-mappings-in-amazon-lightsail.html),
[nftables command reference](https://netfilter.org/projects/nftables/manpage.html),
[Ubuntu 24.04 libnftables JSON schema](https://manpages.ubuntu.com/manpages/noble/man5/libnftables-json.5.html).


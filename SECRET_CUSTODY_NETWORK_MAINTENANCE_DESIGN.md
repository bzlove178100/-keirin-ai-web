# Maintenance network dependencies and initial-anchor decision

Prepared 2026-10-02 08:40 JST. Design and accepted observation evidence only.
No executable live policy, host mutation, credential use or new authorization.

## Accepted live evidence

The user's terminal images IMG_8937–IMG_8946 (08:17–08:32 JST) complete the
requested private observation. Reader commit:
`e0ae01e3d92d84e4f127e997cd36bcd9b54a3864`;
path: `review/secret_custody_network_dependencies.py`;
SHA-256: `9c5f8b2bcfedda0cb32b3512efb6ba59da289d66fb5b010066be4501337fddae`.

The report returned to the prompt with
`LOCAL_DEPENDENCIES_OBSERVED_WITH_UNRESOLVED_ITEMS_NO_MUTATION`.
Its schema is `LOCAL_NETWORK_DEPENDENCIES_V1`, mutation and qualification
are false. The unresolved list is a fixed scope reminder, not eight newly
detected command failures. Highlighted/overlapping terminal paste fragments
are not evidence of another failed execution.

| Section | Observed fact | What remains unproved |
| --- | --- | --- |
| Addresses | Two interfaces: loopback and one routable external interface; both IP families | Address stability through renewal/reboot |
| DNS | One endpoint; networkd DHCPv4 source agrees with resolved; no fallback entries | Transport policy, future DHCP changes, encrypted DNS configuration |
| Chrony | Nine server entries; one selected source and eight unselected entries | Port/NTS settings, source-name resolution, failover and other time services |
| networkd | External interface configured/routable; DHCPv4 and DHCPv6 address sources; NDisc route source | Provider identity/lease authentication and full lifecycle |
| IPv4 routes | Nine; default via DHCP; no marked complex route in supplied entries | Renewal/rebind/expiry behavior |
| IPv6 routes | Seven; RA-derived default and prefix route, local/link-local/multicast routes | RA lifetime, ND, DAD and PMTU under filtering |
| SSH | One syntactically validated tuple | Independently authenticated peer identity; future phone IP or browser source ranges |

Exact addresses, account identifiers, private allowlists and raw screenshots
are deliberately absent here. The current selected time source does not
authorize removal of the eight other sources. DNS port zero in the report
means default, not packet port zero. Observed networkd configuration providers
are dependencies to review, not automatically trusted firewall peers.

The reader request is complete. Do not repeat it on resumption. A future
targeted observation needs a specific unresolved question, changed condition
or additional field, bounded output and an explicit stop condition.

## Concrete policy decisions from this evidence

The current CI renderer uses fixed addresses and permanent neighbors. It cannot
establish that the live dynamic configuration will survive restrictive rules.
Maintenance must preserve administration AND the dependencies that keep
administration working over time. Qualification must add only separately
reviewed destinations; fallback must remove those additions, including
established application flows.

No current endpoint snapshot will be turned directly into a live allowlist.
No blanket established/related accept, all-UDP allowance, world-open SSH,
unrestricted egress or automatic discovery-to-allowlist conversion is proposed.
An unexpected provider, address or route change must not silently widen policy.

The following is an implementation/acceptance matrix, **not passed tests**:

| Case | Isolated positive test | Required negative or failure test |
| --- | --- | --- |
| DHCPv4 | Real client obtains lease, renews by unicast, rebinds with the first server unavailable; administration survives | Wrong interface/port/server handling; lease expiry is explicit; no unrelated UDP access |
| DHCPv6 | Actual client/server exchange, Renew and Rebind on the fixture link; address state read back | Reject unrelated UDP and unsupported peer changes; multicast path tested separately from unicast |
| IPv6 RA | Router advertisement creates/refreshes the expected fixture route | Wrong interface, invalid hop limit, unexpected source and expired route; no forwarding role added |
| ND and DAD | Remove permanent neighbors; resolve peer, perform duplicate-address detection and recover neighbor state | Invalid hop limit/code; duplicate address must not become usable; arbitrary ICMPv6 is not admitted |
| PMTU/errors | Constrained-MTU intermediate router causes genuine IPv4 fragmentation-needed / IPv6 Packet Too Big; allowed transfer recovers | Unrelated/forged error cases; error allowance must not restore forbidden qualification data traffic |
| DNS | UDP plus TCP behavior to approved fixture resolver survives transition/fallback | Wrong destination, unsolicited response and stale endpoint do not widen policy |
| Time | Selected and explicitly approved alternate synthetic sources work | Unapproved source/transport denied; nine observed entries do not imply nine approved entries |
| Administration | Existing and new connections through separate synthetic sources survive renewal and fallback | Wrong source/port denied; TCP echo remains transport evidence, not SSH authentication |
| Recovery | Controller death restores already-qualified restricted maintenance | Unknown table drift stops without overwrite; worker death and readiness race separately covered |

Implementation order: first a new disposable-network fixture for dynamic
configuration, leaving existing static transition tests intact. Use local
synthetic servers and short bounded lease/router timers; never the live host.
Require actual client state/route/packet evidence, cleanup and existing
negative reachability checks. A UDP echo on ports 67/68 or 546/547 is not
a lease-renewal test. Fake JSON is parser evidence only.
Then compose the qualified control-packet fixture with the transition and
independent recovery tests. Do not mark this matrix complete before those
tests exist and pass in CI.

## Initial-anchor decision

PR #174 qualifies a synthetic transition from an **existing known restricted
maintenance policy** to a temporary qualification policy. The live baseline
has no qualified maintenance anchor. A timer restoring the same wrong shared
SSH/DNS/renewal allowance would preserve the lockout.

| Proposed shortcut | Decision |
| --- | --- |
| Leave current Termius session open | Useful observation channel, not independently usable recovery |
| Use Lightsail browser SSH as out-of-band access | Rejected as a claim: it also uses SSH/network access |
| Timer restores the observed unfiltered ruleset | Conflicts with existing no-automatic-relaxation contract |
| Reuse the CI watchdog directly on the host | Rejected: fixture-only; ownership, races, persistence and initial anchor unqualified |
| Snapshot/replacement/new host/expanded IAM | Not performed or authorized; changes operational/cost scope |
| Implement and test a restricted initial recovery design | Next required design before any live apply proposal |

Decision: no live apply command is issued by this change. Preserve the one
existing host, existing administration and inactive H2a. The initial-anchor
problem is not solved by collecting the same network report again or by
passing more static-address tests. A concrete first-install proposal must name
the independently supervised recovery behavior, what happens when shared
allowances are wrong, ownership/concurrency checks and boot behavior. It must
satisfy the existing contract or explicitly present any proposed contract
change for separate authorization; never quietly weaken it.

## Protocol references and limits

- [AWS Lightsail firewall scope](https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-firewall-and-port-mappings-in-amazon-lightsail.html):
  public inbound control is separate from host outbound filtering.
- [AWS CLI guide](https://docs.aws.amazon.com/lightsail/latest/userguide/getstarted-awscli.html):
  closing SSH port 22 also prevents console-initiated SSH. This supports the
  shared-network limitation, not a claim that all recovery products were surveyed.
- [RFC 2131](https://www.rfc-editor.org/rfc/rfc2131.html), sections 4.1 and 4.4.5:
  DHCPv4 client/server ports and renewal/rebinding differ; pinning only a current
  unicast server does not prove rebinding works.
- [RFC 9915](https://www.rfc-editor.org/info/rfc9915/):
  current DHCPv6 specification. Test client/server and multicast behavior,
  not just an open UDP port. It does not establish this host's implementation version.
- [RFC 4861](https://www.rfc-editor.org/rfc/rfc4861.html), sections 6.1 and 7.1:
  RA/ND validation includes hop limit and message validity; link-local scope
  alone is not authentication.
- [RFC 4890](https://www.rfc-editor.org/rfc/rfc4890.html):
  required ICMPv6 error/control functions must be considered when filtering.
  Packet Too Big can originate at an intermediate router, so restricting its
  source to the application endpoint is insufficient.

These references guide synthetic acceptance cases; none supplies private
Lightsail browser ranges, verifies live packets or grants apply permission.
All runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report
gates remain OFF; host remains untrusted/no-secret.

## Follow-up design, 2026-10-04

The [DNS reconciliation and first-install review](SECRET_CUSTODY_DNS_RECONCILIATION_REVIEW.md) now defines a pure selected-fact comparator and concrete stop/recovery evidence for initial installation. It does not solve or authorize the initial anchor. Real resolver/cache/discovery integration and an independently usable restricted rescue path remain unqualified. The original accepted observation above remains complete; do not repeat it.

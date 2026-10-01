# Connection-preserving network transition: proposal and isolated rehearsal

Prepared: 2026-10-02 (Asia/Tokyo), after the 02:07–02:16 live observations.
Scope: synthetic repository/CI work only. No live apply implementation or phone
firewall command is supplied. The real host remains untrusted / no-secret.

## Completed baseline, separate from qualification

User terminal IMG_8930 at 02:07 JST completed PR #172's corrected observer at
`78bbea96eec8d9c8228fe07c4e9ed71dbc1a3e2f`, SHA-256
`92a2f6a135c73d6ed972b61f203ee035e28c5ff7a473934b809041dac8aeb712`.
It returned `H3_HOST_NETWORK_OBSERVED_NO_MUTATION`: zero nft objects/base chains,
zero exposed legacy IPv4 tables, IPv6 legacy tables not exposed; IPv4/IPv6 TCP 22
wildcard listeners; loopback DNS/time-sync ports and IPv4 UDP 68 / IPv6 UDP 546;
forwarding disabled in both families, IPv6 enabled. nftables service was
loaded/inactive/disabled; ufw service loaded/active/enabled.

IMG_8933–IMG_8935 at 02:12–02:13 show one SSH/TCP rule in the displayed saved
Lightsail list, one Custom IPv4 /32 and browser SSH IPv4 checked / IPv6 unchecked.
Exact private addresses are not retained here. These screenshots do not re-show
the port field; earlier configuration and successful Termius used TCP 22. The
browser option does not disable the host IPv6 stack. A /32 is a public source
address, not proof of one physical device. Preserve the known manual difference
from the original browser-only CloudFormation template.

IMG_8936 at 02:16 shows `sudo -n /usr/sbin/ufw status verbose` returning
`Status: inactive`. This resolves UFW's own status, independently of its unit's
ActiveState. No live rule was changed. These limited observations do not prove
effective reachability, all possible filters, persistence or H3/H4 qualification.
Full sanitized facts and chronology are also in [PR #172](https://github.com/bzlove178100/-keirin-ai-web/pull/172).
Do not repeat completed probes/status checks merely to resume.

## Proposed state transitions

The proposed maintenance profile has input/output/forward default deny, explicit
administration SSH paths and verified essential maintenance dependencies. The
qualification profile adds only exact reviewed temporary test destinations.
Both profiles retain the same administration rules. Runtime gates remain OFF.

1. **Prepare privately:** resolve the missing values below, validate both profiles
   against the current host and saved cloud policy, prove the fallback permits
   independent new management sessions, and identify all other rule owners.
2. **Prepare recovery:** an independently supervised, bounded local watchdog must
   have the immutable maintenance fallback and exact expected candidate identity
   before a later live transition can be considered. It must not depend on DNS,
   GitHub, an existing SSH socket, or the applying shell to restore that profile.
3. **Apply once, if separately authorized:** check ownership/drift; submit the
   candidate as one nft transaction. Do not flush the whole ruleset or UFW state.
   A rejected transaction must leave the existing table intact. A lost reply is
   an ambiguous outcome requiring readback, never automatic write replay.
4. **Verify:** new phone and independent recovery sessions must work, alongside
   exact allowed and blocked traffic for both IP families. An old SSH connection
   surviving is insufficient. Keep the original session open while proving new
   sessions. Do not cancel the watchdog based only on a successful nft command.
5. **Fallback on timeout/failure:** only if the owned candidate is still exact,
   replace it atomically with the reviewed maintenance profile, keeping default
   deny and administration access. Remove qualification allowances, including
   already-established flows. Unknown edits/owners stop automatic replacement.
   Keep the host no-secret and runtime disabled; preserve sanitized evidence.

The fallback is **not** the currently unfiltered baseline. Restoring empty rules,
deleting all owned protection, opening SSH to everyone, or allowing all egress
would require a different explicit decision and is not this proposal. Initial
installation of the maintenance anchor is itself a separate unresolved transition:
the existing browser SSH path uses the same host network and is not out-of-band
recovery. No claimed fallback can rescue an incorrectly defined shared management
allowlist. The initial anchor, watchdog, concurrency control and independent
recovery method must be implemented/reviewed before any live apply approval.

This extends the existing [recovery review](SECRET_CUSTODY_HOST_RECOVERY_ROLLBACK_REVIEW.md)
without changing its no-automatic-network-relaxation invariant.

## Inputs still required for a real host profile

| Dependency | Evidence needed before live generation | Current state |
| --- | --- | --- |
| Phone administration | Current SSH peer/interface/port, privately compared with approved cloud source; address change/reconnect behavior | Prior /32 and working login observed; exact fresh host path not captured |
| Independent recovery | Verified independent access/recovery method; if browser SSH is retained, authoritative source range and change lifecycle | Browser IPv4 option enabled; actual source range and independent recovery unproven |
| DNS | Effective upstream resolver addresses, interfaces, UDP and TCP 53, resolver ownership/change lifecycle | Loopback listener only; no upstream destination established |
| Time sync | Configured/selected time service and exact transport endpoints/change lifecycle | Loopback UDP 323 is not evidence of upstream NTP destination |
| DHCP/IPv6 control | Interface/address manager, renewal server/scope, IPv6 RA/ND and required ICMP error/PMTU behavior | Listener ports/flags observed; necessary policy not determined |
| Bootstrap/update | Exact bounded approved endpoints or reviewed proxy, expiration and provenance | Not defined; no broad HTTPS exception |
| Runtime qualification | Exact endpoint/address lifecycle, port, DNS/proxy boundary and identity isolation | Not defined; no real endpoint inferred from old project records |
| Other policy owners | Fresh conflict/ownership evidence at any later mutation boundary | Prior empty nft and UFW inactive; not a concurrency guarantee |

An AWS `lightsail-connect` alias is a cloud-managed range reference, not a numeric
host nft address list. Do not substitute EC2 Instance Connect ranges or assume a
single observed browser source remains complete. Collect needed private host
values in one bounded read-only phase once its reader is reviewed; do not ask for
credentials or repeat the already-completed general readback.

## Executable isolated rehearsal

`review/secret_custody_network_rehearsal.py` only renders two fixed **synthetic**
profiles. It has no address input, host reads, subprocess, persistent write or live
apply mode; direct execution stops. All addresses are documentation fixtures.
`tests/test_secret_custody_network_transition.py --kernel` is CI-only and requires
an already-isolated, initially empty network namespace. It creates one second
namespace and one veth pair, with static synthetic neighbours and no external
routes. All mutation and packets stay in those namespaces. Tests never edit the
runner's host firewall, cloud policy, SSH configuration or real service state.

Actual packets, with reachable positive controls before filtering, verify:

- existing and new TCP-22 administration flows from two allowed sources in IPv4
  and IPv6; another source and HTTP port 80 blocked;
- exact synthetic DNS TCP/UDP and NTP UDP transports remain usable;
- default-deny egress, wrong address/port rejected, and preexisting unapproved
  flows blocked (no blanket `ct state established,related accept` escape);
- invalid kernel transaction preserves the previous profile and administration;
- qualification adds only the exact synthetic TCP-443 destination;
- ownership-checked fallback preserves maintenance traffic and the unrelated
  table, while blocking both new and established qualification flows;
- an unexpected owned-table edit stops the transition without overwriting it.

The fixture checks the actual kernel table structure, ignoring only assigned
handles. That is an isolated single-controller check, **not** a race-free live CAS
or permission to overwrite another writer. Namespace exit cleans up rules and
sockets. Mandatory Ubuntu 24.04 CI runs this test without skipped-success fallback;
Work cannot run unshare in its environment, so local unit checks alone do not
prove the real-kernel behavior.

Limitations: TCP echo on port 22 is transport evidence, not SSH authentication;
DNS/NTP echo is transport evidence, not real protocol validation. Static neighbours
do not qualify DHCP, RA/ND, ICMP/PMTU, DNS drift or cloud behavior. No concurrent
writer/race safety, watchdog/controller death, boot persistence, reboot, real host
apply, runtime-identity egress isolation, TLS or workload capacity is qualified.
The pure profiles are not deployable to the current host.

## Next implementation and stop conditions

Complete the bounded private dependency reader and initial-anchor recovery design,
then generate the actual private profiles and implement/test the independent
watchdog and ownership/concurrency guard. Missing/ambiguous dependencies must stop
live generation; do not use empty fields or internet-wide exceptions as defaults.
Only after those concrete artifacts are reviewable is a narrowly scoped live
approval meaningful. H2a's existing approval does not authorize firewall changes.

All runtime/provider/credential/prediction/data-fetch/scheduler/report gates remain
OFF. No AWS resources, charges, IAM changes or additional inventory runs are added.

Primary references (checked 2026-10-02 JST):

- [nftables atomic replacement](https://wiki.nftables.org/wiki-nftables/index.php/Atomic_rule_replacement)
- [nftables verdict and chain semantics](https://netfilter.org/projects/nftables/manpage.html)
- [Lightsail firewall scope](https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-firewall-and-port-mappings-in-amazon-lightsail.html)
- [Lightsail port information and browser alias](https://docs.aws.amazon.com/lightsail/2016-11-28/api-reference/API_InstancePortInfo.html)

# Real resolver cache and source switching through restricted recovery

CI-only fixture using installed systemd-resolved, a private D-Bus daemon and
synthetic DNS peers. No live host action, DNS discovery approval or DHCP claim.

## Isolation and acceptance

A transient unit enters the already private test network. Its mount namespace
has a generated read-only /etc, private /run and /var, a fresh read-only sysfs,
masked vendor resolver drop-ins and ProtectSystem=strict. The generated passwd,
group, nsswitch and machine-id are fixture data; no host configuration directory
is copied. Private D-Bus permits only root and the resolver user and loads no
activation/service configuration. Queries use the actual 127.0.0.53 stub in the
test network. Controls enter the exact private mount/network namespace and use
an explicit private Unix bus address with auto-start disabled. Host resolver
configuration is fingerprinted before/after; no host resolver is stopped or changed.
Binary hashes/version, actual namespace identities, private runtime/config/sysfs,
private socket identity and child executables are read back. Services are bounded
by PID 1 deadlines and stopped as an owned cgroup, including failure paths.

For each upstream family, use a fresh resolver process and fixed numeric peers:

1. Read back the configured per-link DNSEx through private IPC.
2. Query A/AAAA through the real stub. Change upstream answers; require warm-cache
   responses with no new upstream events. After the real eight-second TTL expires,
   require new upstream requests and new answers without a cache-flush command.
3. Flush only the private cache for a separate transport case. Require upstream
   UDP truncation followed by TCP for A/AAAA. Also require TCP stub queries to
   return warm-cache answers without additional upstream requests.
4. Apply the already reviewed qualification fixture and kill its controller.
   Require a fresh resolver query while qualification is still active. PID 1
   must restore both owned tables, then the same resolver must make fresh A/AAAA
   queries while existing/new administration survives and qualification is denied.
5. Change the private resolver to an unapproved fixed peer, read back that state
   and flush its private cache. A lookup must fail within its bounded client wait;
   output-drop counters must advance, the unapproved server must receive nothing,
   and rules must stay exact. Require a pending transaction after the one-second UDP client timeout; restore the approved source, observe zero active transactions within fifteen seconds, flush the private cache, and require fresh same-name A/AAAA upstream events.
6. Reap resolver/bus/wrapper, remove owned cgroup/config/runtime and preserve host
   resolv.conf identity/content. Remove peer, links and owned rules; namespace empty.

Both sources must answer direct pre-restriction control queries. Eighteen PASS
records are required: baseline, eight per family and final network cleanup.
Six local packet/result/isolation/runtime tests pass. Actual CI acceptance is pending;
all five workflows and eighteen regression jobs on the final head are mandatory.
Exact tested head, run/job IDs and merge receipt belong in the PR.

## Initial failure and correction

Initial head `51bcca67c3d792ff0666580ff1d3ab91a4178654`, regression `37174153597`, resolver job `111353154685`, passed direct upstream baseline then stopped before daemon startup: `/run/systemd` already existed in the private runtime and exclusive mkdir raised FileExistsError. The private mount/runtime/config guards had passed. The fixture now accepts an existing real directory after lstat, but rejects symlinks/files; a real temporary-filesystem regression covers these cases. Six resolver plus eleven reused tests pass (17 total). No isolation guard, deadline or network assertion was relaxed. Corrected real-resolver CI is pending.

## Pending-query recovery measurement

Second head `c5f7197dc1b626614471137e24e8de7fde7ab4d5`, regression `37174244369`, resolver job `111353435221`, passed isolation plus IPv4 cache/TTL, truncation/TCP, controller-death and restored fresh queries, and unapproved-source denial. It failed the immediate same-name query after restoring the approved source. The log shows the denied UDP attempt falling back to TCP and the subsequent query remaining in processing; upstream v255 uses a ten-second TCP transaction timeout. A pending old transaction is the hypothesis to measure, not an assertion that configuration readback guarantees immediate recovery. The changed test requires actual positive TransactionStatistics after client timeout, restores the approved source, waits at most fifteen seconds for actual zero active transactions, then flushes only the private cache and requires fresh A/AAAA upstream events. Existing one-second client queries, isolation, policy shape and deny assertions are unchanged. If transactions do not drain, the test fails; no daemon restart or blind retry is used. Corrected CI is pending.

## Scope and remaining work

This exercises explicit private SetLinkDNS changes, not DHCP-to-resolved delivery,
networkd/resolved combined lifetimes, NSS/getaddrinfo, DNSSEC, DoT, search-domain
routing, negative caching or a live provider. Static routes/neighbors and fixed
synthetic names are intentional. DNSSEC and DoT are disabled only in the private
fixture. Cache hits do not count as transport evidence. A successful private
readback is not authenticated discovery or a production approval gate.

Next: feed DNS changes from an actual isolated DHCP client and bind observations
to process/interface/generation evidence, including interrupted collection.
Initial restricted installation, independent rescue for wrong shared allowances,
reboot, non-cooperating writers and worker death after readiness remain blocked.
All runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report
gates remain OFF; H2a inactive. No phone/AWS/SSH/live host/credential request.

## Primary implementation references inspected

- [systemd v255 resolved configuration](https://github.com/systemd/systemd/blob/v255/man/resolved.conf.xml): private configuration, cache and stub settings.
- [systemd v255 resolver startup](https://github.com/systemd/systemd/blob/v255/src/resolve/resolved.c): runtime directory and privilege drop.
- [systemd v255 resolver D-Bus implementation](https://github.com/systemd/systemd/blob/v255/src/resolve/resolved-bus.c): private bus use and SetLinkDNS/DNSEx.
- [systemd v255 stub implementation](https://github.com/systemd/systemd/blob/v255/src/resolve/resolved-dns-stub.c): stub request and reply path.

The actual Ubuntu CI version and behavior must be measured; upstream inspection
alone does not qualify Ubuntu's packaged implementation.

- [systemd v255 transaction implementation](https://github.com/systemd/systemd/blob/v255/src/resolve/resolved-dns-transaction.c): ten-second TCP transaction timeout.

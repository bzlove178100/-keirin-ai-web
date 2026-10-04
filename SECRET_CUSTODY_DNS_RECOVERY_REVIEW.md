# Fixed DNS transport and independent restricted recovery

## Scope

Only disposable CI namespaces and fixed documentation addresses. The installed BIND `dig` executable is the real DNS client; a small bounded synthetic DNS server returns only `fixture.invalid.` IN A/AAAA records. It serves real DNS messages with transaction IDs, question sections, answer records and TCP length framing. No UDP echo is counted as DNS evidence. `dig -v` and the kernel release are recorded. No host resolver file, daemon, clock or private endpoint is changed.

`dig -r` suppresses user configuration; numeric server addresses, absolute fixed name, disabled search/recursion/EDNS, one attempt and one-second DNS timeout bound each query. A subprocess also has the existing five-second outer limit. All answers use TTL zero and each query is a fresh process. This is not cache-expiry or systemd-resolved evidence.

## Mandatory acceptance

- First demonstrate both candidate DNS endpoint addresses and UDP/TCP answer before filtering; also prove administration/qualification services work.
- Under restricted maintenance, obtain exact A/AAAA data through UDP, explicit TCP and UDP truncation→TCP fallback for both IP families. Server event sequences independently verify actual transports and query types.
- Compile owned maintenance/qualification shapes before opening management connections. Arm PID 1's existing worker. The controller applies qualification and SIGKILLs itself. Require actual TCP/443 qualification exchange and all DNS transport cases while the controller is dead and qualification is still active.
- Require worker result `RESTORE_MAINTENANCE`, atomic inet/netdev readback, old qualification denial and surviving management sockets. Repeat every DNS transport case after restoration; new management works and new qualification fails.
- Silence only the approved server. Require an actual recorded UDP query and client failure. Query an unapproved changed endpoint over both transports: require client failure, output drop-counter increase and no server events. Rule shape must not widen. Re-enable the original server with changed A/AAAA data, then require new exact answers for all three transport paths.
- Bind an unused UDP port outside the verified ephemeral source-port range. Send a real unsolicited DNS answer from the approved resolver: netdev acceptance counter and inet denial counter must each advance by one and the socket must time out. A reply from the wrong resolver must advance the netdev denial counter without reaching the socket.
- Require final shape, existing management and old/new qualification denial. Stop/reap peer process, close sockets/pipes, remove owned links/tables and read back an empty outer namespace. Existing worker unit/directory cleanup is reused.

Sixteen acceptance records are required: six per family plus baseline, independent restoration, final denial/shape and cleanup. No skipped success is allowed. The original protocol/PMTU jobs remain mandatory; this is a new sixteenth regression job.

## Evidence

Four local DNS parser/framing/guard tests and ten recovery/helper tests pass. Kernel/protocol CI is pending. All five workflows for the final head must succeed before integration. Final exact-head evidence and merge receipt belong in the PR.

## Limits and next work

This does not qualify systemd-resolved/NSS, resolver cache/TTL expiry, automatic resolver configuration/discovery/failover, DNSSEC/authentication, encrypted DNS or an actual live resolver. Static neighbors/routes are intentional; DHCP/RA/PMTU simultaneous behavior is not claimed. Firewall conntrack is flow evidence, not DNS transaction authenticity. The unsolicited response case has no matching outbound flow; in-flow forged DNS responses are not qualified. TCP echo on 22 is transport continuity, not SSH authentication.

Next: synthetic time sources, resolver integration/discovery and initial restricted maintenance recovery. The observed nine time peers are not an approved allowlist. First-install anchor, wrong shared allowances, reboot, non-cooperating root writers and worker death after readiness remain unresolved. All live/runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF; H2a inactive.

## References

- [BIND dig manual](https://bind9.readthedocs.io/en/latest/manpages.html#dig-dns-lookup-utility): explicit server, `-r`, transport, truncation, timeout and tries options. CI records the installed version rather than assuming the documentation version.
- [RFC 7766](https://www.rfc-editor.org/rfc/rfc7766.html): DNS over TCP and clients falling back after TC=1. The fixture tests one query per TCP connection; it does not claim complete RFC conformance, pipelining or connection reuse.

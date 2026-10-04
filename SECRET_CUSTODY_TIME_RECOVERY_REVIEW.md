# Chrony source selection through restricted recovery

## Scope and clock boundary

CI only, fixed documentation peers in two private network namespaces. Extract the Ubuntu chrony package with dpkg-deb; do not install the package or run its service scripts. Record package version, client version and executable SHA-256 values. Only this run's marked extraction directory may be deleted.

Each real chronyd runs in the test network as uid/gid 65534 with `-x -U -d`, no supplementary groups, all capability sets including bounding/ambient empty, and NoNewPrivs. Read back its identity, capabilities and namespace repeatedly. `-x` disables clock control; absence of CAP_SYS_TIME independently prevents clock-setting operations. No `-q`, RTC, makestep or host time-service operation. The private explicit configuration contains only fixed numeric peers and paths in its owned directory; NTP server and UDP command ports are disabled. chronyc accesses only the private Unix socket. Terminate/reap each client and remove its owned files.

Synthetic servers read the same host clock for timestamps. This measures NTP client protocol/selection behavior, not clock correction, independent accuracy or UTC traceability. No external NTP packets leave the network. One-second polling is confined to these fixtures.

## Required evidence

1. Before restriction, receive actual 48-byte NTP replies with matching originate timestamps from both approved peers and the unapproved control. Prove TCP/123 and management/qualification controls reachable.
2. Compile maintenance/qualification shapes and restore maintenance. Start a fresh real client separately for IPv4 and IPv6 with a preferred primary and one approved alternate. Require actual primary selection from chronyc and nonzero reach.
3. Arm PID 1 recovery, apply qualification and SIGKILL the controller. Require actual qualification traffic plus a new `Total good RX` measurement on the same chronyd while qualification remains active.
4. Require atomic restoration of inet/netdev, exact shape, old/new qualification denial, existing/new management and further accepted measurements on that same client.
5. Silence the primary. Wait for its actual eight-bit reach register to become zero and the approved alternate to become selected; server receives requests but sends no new responses. Restore primary and require its selection again.
6. Send wrong originate timestamps from the primary. Require alternate selection and primary reach zero, then further `Total RX` increments with no `Total valid RX` or `Total good RX` increments. Restore valid replies and require primary selection again.
7. A real request to the unapproved source and TCP/123 must fail after restriction, with output drops and unchanged unapproved-server counters. Final shape, management and old qualification denial remain intact.
8. Reap both clients and the peer process; remove private files, worker unit/directory, owned links/tables and require an empty namespace.

Fifteen acceptance records are required: six per family plus baseline, client cleanup and peer/network cleanup. This is the seventeenth mandatory regression job. A failed assertion cannot be skipped or reported as success.

## Evidence and limits

Five local packet/report/isolation tests and six reused recovery tests pass. Corrected code head `f13291df52c550ed5ae19d46282e3ba91eaf9ef5`, regression `37167200665`, time job `111332494299`, passed all fifteen acceptance records and `SYNTHETIC_TIME_RECOVERY_OK_NO_CLOCK_OR_LIVE_APPLY` at 01:11:47 UTC on October 4 (10:11 JST). Ubuntu package `4.5-1ubuntu4.2`, chronyd 4.5, kernel `6.17.0-1022-azure`; chronyd SHA-256 `7a834e478d8a904c39a348606a5d0ac58fd1ccbca24f333a8170c786af8ca508`, chronyc SHA-256 `271ea54c67206559437bd299d0e08c9e3d42ee6be322b1722e76311cd5d9df8d`. Both families selected the preferred primary without clock capabilities, accepted fresh measurements after controller death and independent restoration, selected the approved alternate for silence and wrong-origin replies, returned to primary, denied the unapproved source/TCP transport, preserved administration and qualification denial, and cleaned up clients, files, links and rules. Other code-head jobs were still running when this targeted evidence was recorded. All five workflows and seventeen regression jobs for the final head remain mandatory; exact final evidence and merge receipt belong in PR #186.

No installed/live time source is approved by this test. It does not qualify NTS, cryptographic authenticity, a malicious-but-plausible time source, clock correction, long-term drift, leap handling, RTC, suspend/reboot, DNS-resolved pools, dynamic source discovery, systemd-resolved, or simultaneous DHCP/RA/DNS/PMTU changes. Source preference is explicit, not discovered from the nine live entries. Initial restricted maintenance installation and independent recovery from a wrong shared allowlist remain unsolved. All activation gates OFF; H2a inactive.

## Initial failure and changed condition

Initial head `dd847428974c748d5472f3b2dd47b865b30e6e0e`, regression `37166897486`, time job `111331572656`, passed baseline and five IPv4 records, including accepted measurements after restoration and alternate selection for silent/wrong-origin replies. It stopped at the unapproved UDP probe: `sendto` returned `EPERM` immediately, but the helper handled only receive timeout. The helper now accepts only EPERM or timeout for an expected denial; positive probes, unrelated errors and any received reply still fail. A local regression covers these distinctions. The actual output-drop increment and unchanged peer counters remain mandatory. Five time tests plus six recovery tests pass. Corrected CI subsequently passed both families and complete cleanup as recorded above; the final complete CI gate remains required.

## References

- [chronyd 4.5 manual](https://chrony-project.org/doc/4.5/chronyd.html): `-x` disables clock control; `-U` supports constrained unprivileged operation with a known configuration.
- [chrony configuration](https://chrony-project.org/doc/4.5/chrony.conf.html): numeric servers, prefer, bounded local polling, private Unix command socket and disabled service ports.
- [chronyc reports](https://chrony-project.org/doc/4.5/chronyc.html): sources selection/reach and ntpdata received/valid/accepted counters.
- [RFC 5905](https://www.rfc-editor.org/rfc/rfc5905.html): NTP timestamp fields and response validation. The fixture does not claim full RFC conformance.

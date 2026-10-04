"""Unactivated, fixed synthetic qualification lease; pure nft renderer only.

Install independently BEFORE arming a controller. Candidate/restore transactions
must never own these tables. Replaying installation while tables exist fails.
This is not a live host installer, permission grant or general firewall policy.
"""

TABLES = (("inet", "kc_lease_guard"), ("netdev", "kc_lease_link_guard"))
SECONDS = 8
SET = "qualification"


def install(ifindex):
    if type(ifindex) is not int or not 0 < ifindex < 2 ** 31:
        raise ValueError("POSITIVE_INTERFACE_INDEX_REQUIRED")
    text = ""
    for family, table in TABLES:
        # create, not add: existing ownership cannot reset the lease by replay.
        text += f"create table {family} {table}\n"
        text += (f"add set {family} {table} {SET} {{ type inet_service; flags timeout; "
                 f"timeout {SECONDS}s; gc-interval 1m; elements = {{ 443 }}; }}\n")
        for incoming in (True, False):
            chain = ("input" if incoming else "output") if family == "inet" else ("ingress" if incoming else "egress")
            device = ' device "host0"' if family == "netdev" else ""
            text += f"add chain {family} {table} {chain} {{ type filter hook {chain}{device} priority -10; policy accept; }}\n"
            index = f"meta {'iif' if incoming else 'oif'} {ifindex} " if family == "inet" else ""
            port = "sport" if incoming else "dport"
            for ip, prefix in (("ip", "192.0.2."), ("ip6", "2001:db8:1::")):
                source, dest = (prefix + "2", prefix + "1") if incoming else (prefix + "1", prefix + "2")
                protocol = f"meta protocol {ip} " if family == "netdev" else ""
                text += (f"add rule {family} {table} {chain} {protocol}{index}{ip} saddr {source} "
                         f"{ip} daddr {dest} tcp {port} @{SET} return\n")
            # The lease is checked on every packet, including established TCP.
            # No update/add from packet path, ct bypass, flowtable or userspace timer.
            text += f"add rule {family} {table} {chain} tcp {port} 443 counter drop\n"
    return text

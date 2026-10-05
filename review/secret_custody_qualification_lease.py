"""Unactivated, fixed synthetic qualification lease; pure nft renderer only.

Install independently BEFORE arming a controller. Candidate/restore transactions
must never own these tables. Replaying installation while tables exist fails.
This is not a live host installer, permission grant or general firewall policy.
"""

TABLES = (("inet", "kc_lease_guard"), ("netdev", "kc_lease_link_guard"))
SECONDS = 8
SET = "qualification"
# Fixed synthetic tuples only. No caller-supplied address or live profile.
PROFILES = {
    "time": (("ip", "192.0.2.1", "192.0.2.2"), ("ip6", "2001:db8:1::1", "2001:db8:1::2")),
    "dhcp4": (("ip", "192.0.2.10", "192.0.2.2"),),
    "ra6": (("ip6", "2001:db8:6::10", "2001:db8:7::2"),),
}


def tuples(profile):
    if not isinstance(profile, str) or profile not in PROFILES:
        raise ValueError("FIXED_LEASE_PROFILE_REQUIRED")
    return PROFILES[profile]


def install(ifindex, profile="time"):
    peers = tuples(profile)
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
            for ip, host, peer in peers:
                source, dest = (peer, host) if incoming else (host, peer)
                protocol = f"meta protocol {ip} " if family == "netdev" else ""
                text += (f"add rule {family} {table} {chain} {protocol}{index}{ip} saddr {source} "
                         f"{ip} daddr {dest} tcp {port} @{SET} return\n")
            # The lease is checked on every packet, including established TCP.
            # No update/add from packet path, ct bypass, flowtable or userspace timer.
            text += f"add rule {family} {table} {chain} tcp {port} 443 counter drop\n"
    return text


def snapshot(reports, profile="time"):
    """Seal fixed-installer readback; retain handles and every policy field.

    Only live counters and the member's decreasing expiry are measurements.
    Expiry is checked for presence/positivity, not converted between nft versions.
    The independent conservative deadline starts BEFORE installation.
    """
    import copy
    import math
    if not isinstance(reports, list) or len(reports) != len(TABLES):
        raise ValueError("LEASE_TABLE_REPORTS_REQUIRED")
    rule_count = 2 * (len(tuples(profile)) + 1)
    result = []
    for report, (family, table) in zip(reports, TABLES):
        rows = copy.deepcopy(report["nftables"])
        rows = [row for row in rows if "metainfo" not in row]
        kinds = [next(iter(row)) for row in rows if len(row) == 1]
        if sorted(kinds) != sorted(["table", "set", "chain", "chain"] + ["rule"] * rule_count):
            raise ValueError("LEASE_OBJECTS_REQUIRED")
        for row in rows:
            kind, item = next(iter(row.items()))
            if (item["family"] != family or type(item["handle"]) is not int
                    or item["handle"] <= 0
                    or (item["name"] if kind == "table" else item["table"]) != table):
                raise ValueError("LEASE_OBJECT_IDENTITY_REQUIRED")
            if kind == "set":
                if item["name"] != SET or item["type"] != "inet_service" or item["flags"] != ["timeout"]:
                    raise ValueError("LEASE_TIMED_SERVICE_SET_REQUIRED")
                elements = item["elem"]
                if len(elements) != 1 or set(elements[0]) != {"elem"}:
                    raise ValueError("LEASE_SINGLE_MEMBER_REQUIRED")
                member = elements[0]["elem"]
                expiry = member.pop("expires")
                if (member["val"] != 443 or type(member["val"]) is not int
                        or type(expiry) not in (int, float) or not math.isfinite(expiry) or expiry <= 0):
                    raise ValueError("LEASE_LIVE_MEMBER_REQUIRED")
            if kind == "rule":
                for expression in item["expr"]:
                    if "counter" in expression:
                        counter = expression["counter"]
                        counter.pop("packets", None)
                        counter.pop("bytes", None)
        result.append(rows)
    return result


def require(receipt, binding, reports, now, profile="time"):
    """Pure fail-closed check. Receipts originate only from fixed installation.

    Not an attestation against another privileged writer. A point read cannot
    eliminate the final-check/commit race; intact kernel guards bound that race.
    """
    import math
    try:
        deadline = receipt["deadline"]
        if (type(now) not in (int, float) or not math.isfinite(now)
                or type(deadline) not in (int, float) or not math.isfinite(deadline)
                or not 2 <= deadline - now <= SECONDS
                or receipt["binding"] != binding or receipt["snapshot"] != snapshot(reports, profile)):
            raise ValueError("LEASE_MISMATCH")
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        raise RuntimeError("QUALIFICATION_GUARD_REQUIRED") from exc

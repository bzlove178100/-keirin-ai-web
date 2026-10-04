"""Pure comparison of selected private reader facts. Never an apply gate.

No host reads, queries, mutation, persistence, address output or executable mode.
Caller-supplied observations are unauthenticated and have no freshness proof.
"""
import ipaddress
import re


class Stop(Exception):
    pass


def need(ok, reason="INVALID_OBSERVATION"):
    if not ok:
        raise Stop(reason)


def integer(value, minimum, maximum):
    need(type(value) is int and minimum <= value <= maximum)
    return value


def token(value):
    need(type(value) is str and re.fullmatch(r"[A-Za-z0-9_.:@+-]{1,64}", value) is not None)
    return value


def address(value):
    need(type(value) is str and len(value) <= 45 and "%" not in value)
    ip = ipaddress.ip_address(value)
    need(not (ip.is_loopback or ip.is_unspecified or ip.is_multicast), "UNSUPPORTED_ENDPOINT_SCOPE")
    return str(ip)


def values(report, name, limit):
    section = report["sections"][name]
    need(type(section) is dict and section.get("status") == "observed", "INCOMPLETE_OBSERVATION")
    need("private_values" in section, "PRIVATE_FACTS_REQUIRED")
    result = section["private_values"]
    need(type(result) is list and len(result) <= limit)
    need(type(section.get("count")) is int and section["count"] == len(result))
    return result


def snapshot(report):
    need(type(report) is dict and report.get("schema") == "LOCAL_NETWORK_DEPENDENCIES_V1")
    need(report.get("qualification") is False and report.get("mutation") is False)
    need(type(report.get("sections")) is dict)
    links = {}
    for item in values(report, "addresses", 32):
        index = integer(item["index"], 1, 2**31 - 1)
        name = token(item["interface"])
        need(index not in links and name not in links.values())
        links[index] = name
    need(links, "INCOMPLETE_OBSERVATION")
    fallback = values(report, "dns_fallback", 64)
    need(not fallback, "FALLBACK_REQUIRES_SEPARATE_REVIEW")
    resolved = set()
    for item in values(report, "dns", 64):
        need(type(item) is dict and set(item) == {"index", "address", "port_zero_means_default", "server_name"}, "DNS_EX_FIELDS_REQUIRED")
        index = integer(item["index"], 0, 2**31 - 1)
        need(index != 0 and index in links, "LINK_SCOPE_REQUIRED")
        ip = address(item["address"])
        port = integer(item["port_zero_means_default"], 0, 65535)
        need(type(item["server_name"]) is str and len(item["server_name"]) <= 253)
        # Zero is an observed default token, never a permission for UDP/TCP 53.
        need(port in (0, 53) and item["server_name"] == "", "TRANSPORT_REQUIRES_SEPARATE_REVIEW")
        key = (index, ip, port)
        need(not any(x[:2] == key[:2] for x in resolved))
        resolved.add(key)
    need(resolved, "EMPTY_RESOLVER_SET")
    managed, seen, records = set(), set(), set()
    for item in values(report, "networkd", 32):
        index = integer(item["index"], 1, 2**31 - 1)
        name = token(item["interface"])
        need(index not in seen and links.get(index) == name, "LINK_IDENTITY_MISMATCH")
        seen.add(index)
        observations = item["observations"]
        need(type(observations) is list and len(observations) <= 256)
        dns = []
        for fact in observations:
            need(type(fact) is dict and fact.get("kind") in ("Addresses", "Routes", "DNS", "NTP"))
            if fact["kind"] != "DNS":
                continue
            need(set(fact) in ({"kind", "Address", "source", "ConfigProvider"},
                               {"kind", "Address", "source", "ConfigProvider", "port"}), "DNS_ORIGIN_FIELDS_REQUIRED")
            ip, provider = address(fact["Address"]), address(fact["ConfigProvider"])
            source = token(fact["source"])
            need(source in ("DHCPv4", "DHCPv6"), "UNSUPPORTED_CONFIGURATION_SOURCE")
            need((":" in provider) == (source == "DHCPv6"), "PROVIDER_FAMILY_MISMATCH")
            port = None if "port" not in fact else integer(fact["port"], 0, 65535)
            need(port in (None, 0, 53), "TRANSPORT_REQUIRES_SEPARATE_REVIEW")
            key = (index, ip)
            need(key not in managed)
            managed.add(key)
            need(len(managed) <= 64)
            dns.append((ip, source, provider, -1 if port is None else port))
        if dns:
            admin, operational = token(item["AdministrativeState"]), token(item["OperationalState"])
            need(admin == "configured" and operational == "routable", "LINK_NOT_READY")
            records.add((index, name, admin, operational, tuple(sorted(dns))))
    need({x[:2] for x in resolved} == managed, "RESOLVED_NETWORKD_DISAGREE")
    return frozenset(resolved), frozenset(records)


def compare(before, after):
    """Return codes only; matching facts neither approve peers nor prove freshness."""
    result = {"schema": "DNS_RECONCILIATION_REVIEW_V1", "qualification": False,
              "mutation": False, "apply_allowed": False, "freshness_verified": False}
    try:
        old, new = snapshot(before), snapshot(after)
        result["decision"] = "OBSERVATIONS_MATCH_REVIEW_ONLY" if old == new else "CHANGE_REVIEW_REQUIRED"
        result["reason"] = "SELECTED_FACTS_EQUAL" if old == new else "SELECTED_FACTS_CHANGED"
    except Stop as exc:
        result.update(decision="BLOCKED", reason=exc.args[0])
    except (KeyError, TypeError, ValueError, AttributeError):
        result.update(decision="BLOCKED", reason="INVALID_OBSERVATION")
    return result


if __name__ == "__main__":
    print("STOP REVIEW_ONLY_NO_HOST_READ_OR_APPLY")
    raise SystemExit(1)

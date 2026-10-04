"""Observation comparison only; no resolver or live-policy qualification."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


ROOT = Path(__file__).resolve().parents[1]
c = module("reconciliation", ROOT / "review/secret_custody_dns_reconciliation.py")
d = module("dependencies", ROOT / "review/secret_custody_network_dependencies.py")


def report():
    # Real existing parsers; documentation addresses and synthetic bus replies.
    dns = {"type": "v", "data": [{"type": "a(iiayqs)", "data": [
        [2, 2, [192, 0, 2, 53], 0, ""],
        [2, 10, list(bytes.fromhex("20010db8000000000000000000000053")), 0, ""]]}]}
    net = {"Interfaces": [{"Index": 2, "Name": "eth0", "AdministrativeState": "configured",
        "OperationalState": "routable", "DNS": [
        {"Family": 2, "Address": [192, 0, 2, 53], "ConfigSource": "DHCPv4", "ConfigProvider": [192, 0, 2, 254]},
        {"Family": 10, "Address": list(bytes.fromhex("20010db8000000000000000000000053")),
         "ConfigSource": "DHCPv6", "ConfigProvider": list(bytes.fromhex("fe800000000000000000000000000001"))}]}]}
    parts = {"addresses": d.addresses(json.dumps([{"ifindex": 2, "ifname": "eth0", "addr_info": []}]).encode()),
             "dns": d.dns(json.dumps(dns).encode()), "dns_fallback": [],
             "networkd": d.networkd(json.dumps({"type": "s", "data": [json.dumps(net)]}).encode())}
    return {"schema": "LOCAL_NETWORK_DEPENDENCIES_V1", "qualification": False, "mutation": False,
            "sections": {name: {"status": "observed", "count": len(value), "private_values": value}
                         for name, value in parts.items()}}


def entries(value, section):
    return value["sections"][section]["private_values"]


class Tests(unittest.TestCase):
    def decision(self, value, expected):
        result = c.compare(report(), value)
        self.assertEqual(result["decision"], expected, result)
        for gate in ("qualification", "mutation", "apply_allowed", "freshness_verified"):
            self.assertIs(result[gate], False)
        return result

    def test_matching_parser_facts_do_not_authorize_or_prove_freshness(self):
        self.decision(report(), "OBSERVATIONS_MATCH_REVIEW_ONLY")

    def test_reordered_and_canonical_ipv6_facts_match(self):
        value = report()
        entries(value, "dns").reverse()
        entries(value, "dns")[0]["address"] = "2001:0db8:0000:0000:0000:0000:0000:0053"
        entries(value, "networkd")[0]["observations"].reverse()
        self.decision(value, "OBSERVATIONS_MATCH_REVIEW_ONLY")

    def test_changed_endpoint_in_both_managers_requires_review(self):
        value = report()
        entries(value, "dns")[0]["address"] = "192.0.2.54"
        entries(value, "networkd")[0]["observations"][0]["Address"] = "192.0.2.54"
        self.decision(value, "CHANGE_REVIEW_REQUIRED")

    def test_added_and_removed_consistent_endpoints_require_review(self):
        for add in (True, False):
            value = report()
            dns, facts = entries(value, "dns"), entries(value, "networkd")[0]["observations"]
            if add:
                dns.append(dict(dns[0], address="192.0.2.54"))
                facts.append(dict(facts[0], Address="192.0.2.54"))
            else:
                dns.pop()
                facts.pop()
            value["sections"]["dns"]["count"] = len(dns)
            self.decision(value, "CHANGE_REVIEW_REQUIRED")

    def test_provider_change_with_same_resolver_requires_review(self):
        value = report()
        entries(value, "networkd")[0]["observations"][0]["ConfigProvider"] = "192.0.2.253"
        self.decision(value, "CHANGE_REVIEW_REQUIRED")

    def test_consistent_interface_rename_or_reindex_requires_review(self):
        for field, new in (("interface", "eth1"), ("index", 3)):
            value = report()
            entries(value, "addresses")[0][field] = new
            entries(value, "networkd")[0][field] = new
            if field == "index":
                for item in entries(value, "dns"):
                    item[field] = new
            self.decision(value, "CHANGE_REVIEW_REQUIRED")

    def test_disagreement_unknown_and_counts_only_block(self):
        value = report()
        entries(value, "dns")[0]["address"] = "192.0.2.54"
        self.assertEqual(self.decision(value, "BLOCKED")["reason"], "RESOLVED_NETWORKD_DISAGREE")
        for section in ("addresses", "dns", "dns_fallback", "networkd"):
            for mode in ("unknown", "counts"):
                value = report()
                if mode == "unknown":
                    value["sections"][section] = {"status": "unknown", "reason": "PRIVATE-ERROR"}
                else:
                    del value["sections"][section]["private_values"]
                self.decision(value, "BLOCKED")

    def test_fallback_global_stub_and_named_or_encrypted_modes_block(self):
        for field, bad in (("index", 0), ("index", 9), ("address", "127.0.0.53"),
                           ("address", "::"), ("address", "ff02::1"), ("address", "fe80::1%eth0"),
                           ("server_name", "dns.example.invalid"), ("port_zero_means_default", 853)):
            value = report()
            entries(value, "dns")[0][field] = bad
            self.decision(value, "BLOCKED")
        value = report()
        entries(value, "dns_fallback").append(entries(value, "dns")[0])
        value["sections"]["dns_fallback"]["count"] = 1
        self.decision(value, "BLOCKED")

    def test_default_token_is_not_silently_normalized_to_53(self):
        value = report()
        entries(value, "dns")[0]["port_zero_means_default"] = 53
        self.decision(value, "CHANGE_REVIEW_REQUIRED")
        value = report()
        entries(value, "networkd")[0]["observations"][0]["port"] = 0
        self.decision(value, "CHANGE_REVIEW_REQUIRED")

    def test_ambiguous_duplicate_or_missing_origin_blocks(self):
        for mode in ("duplicate", "missing", "wrong_family", "hostname", "old_dns"):
            value = report()
            facts = entries(value, "networkd")[0]["observations"]
            if mode == "duplicate":
                facts.append(copy.deepcopy(facts[0]))
            elif mode == "missing":
                del facts[0]["ConfigProvider"]
            elif mode == "wrong_family":
                facts[0]["ConfigProvider"] = "fe80::1"
            elif mode == "hostname":
                facts[0]["server_name_unresolved"] = "secret.invalid"
            else:
                del entries(value, "dns")[0]["server_name"]
            self.decision(value, "BLOCKED")

    def test_not_ready_mismatch_duplicate_and_empty_links_block(self):
        for mode in ("state", "name", "duplicate", "empty"):
            value = report()
            links = entries(value, "networkd")
            if mode == "state":
                links[0]["OperationalState"] = "degraded"
            elif mode == "name":
                links[0]["interface"] = "eth1"
            elif mode == "duplicate":
                links.append(copy.deepcopy(links[0]))
            else:
                links.clear()
            value["sections"]["networkd"]["count"] = len(links)
            self.decision(value, "BLOCKED")

    def test_malformed_types_bounds_and_invalid_baseline_block(self):
        for bad in (None, [], {}, {"schema": "wrong"}):
            self.decision(bad, "BLOCKED")
            self.assertEqual(c.compare(bad, report())["decision"], "BLOCKED")
        for field, bad in (("index", True), ("address", "x" * 1000), ("port_zero_means_default", False)):
            value = report()
            entries(value, "dns")[0][field] = bad
            self.decision(value, "BLOCKED")
        value = report()
        value["sections"]["dns"]["count"] = 9
        self.decision(value, "BLOCKED")
        value = report()
        value["sections"]["dns"]["private_values"] *= 33
        value["sections"]["dns"]["count"] = 66
        self.decision(value, "BLOCKED")

    def test_output_redacts_inputs_and_inputs_unchanged(self):
        before, after = report(), report()
        entries(after, "dns")[0]["address"] = "PRIVATE-SENTINEL"
        saved = copy.deepcopy((before, after))
        result = c.compare(before, after)
        self.assertEqual((before, after), saved)
        for private in ("PRIVATE-SENTINEL", "192.0.2.", "2001:db8", "eth0", "fe80"):
            self.assertNotIn(private, json.dumps(result))

    def test_claimed_authorization_and_empty_resolvers_never_pass(self):
        for gate in ("qualification", "mutation"):
            value = report()
            value[gate] = True
            self.decision(value, "BLOCKED")
        value = report()
        entries(value, "dns").clear()
        value["sections"]["dns"]["count"] = 0
        entries(value, "networkd")[0]["observations"].clear()
        self.decision(value, "BLOCKED")


if __name__ == "__main__":
    unittest.main(verbosity=2)

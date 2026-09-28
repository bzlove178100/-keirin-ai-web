"""Unit guards for synthetic exclusive-network egress qualification."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import host_egress_contract as contract
from support import egress_allowlist_probe as probe

A = "a" * 64
B = "b" * 64
C = "c" * 64


def network():
    return {
        "Driver": "bridge",
        "Internal": True,
        "Attachable": False,
        "Ingress": False,
        "Options": {contract.NETWORK_OPTION: "false"},
        "IPAM": {"Config": [{"Subnet": "172.30.0.0/16", "Gateway": "172.30.0.1"}]},
        "Containers": {
            A: {"Name": "approved", "IPv4Address": "172.30.0.2/16"},
            B: {"Name": "client", "IPv4Address": "172.30.0.3/16"},
        },
    }


class EgressAllowlistContractTests(unittest.TestCase):
    def test_internal_nonmasqueraded_bridge_is_required(self):
        contract.verify_network(network())
        changes = [
            ("Driver", "host"), ("Internal", False), ("Attachable", True), ("Ingress", True),
        ]
        for key, value in changes:
            candidate = deepcopy(network())
            candidate[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "synthetic_egress_network_invalid"):
                contract.verify_network(candidate)
        candidate = deepcopy(network())
        candidate["Options"][contract.NETWORK_OPTION] = "true"
        with self.assertRaisesRegex(RuntimeError, "synthetic_egress_network_invalid"):
            contract.verify_network(candidate)

    def test_exact_membership_rejects_extra_missing_or_renamed_peer(self):
        expected = {A: "approved", B: "client"}
        contract.verify_members(network(), expected)
        extra = deepcopy(network())
        extra["Containers"][C] = {"Name": "unapproved", "IPv4Address": "172.30.0.4/16"}
        with self.assertRaisesRegex(RuntimeError, "synthetic_egress_members_invalid"):
            contract.verify_members(extra, expected)
        missing = deepcopy(network())
        del missing["Containers"][B]
        with self.assertRaisesRegex(RuntimeError, "synthetic_egress_members_invalid"):
            contract.verify_members(missing, expected)
        renamed = deepcopy(network())
        renamed["Containers"][A]["Name"] = "wrong"
        with self.assertRaisesRegex(RuntimeError, "synthetic_egress_member_identity_invalid"):
            contract.verify_members(renamed, expected)

    def test_allowed_ip_is_numeric_ipv4_only(self):
        self.assertEqual(probe.require_allowed_ip("172.30.0.2"), "172.30.0.2")
        for value in ("", "localhost", "127.0.0.1", "0.0.0.0", "224.0.0.1", "2001:db8::1"):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                probe.require_allowed_ip(value)

    def test_nonloopback_default_route_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            route = Path(temporary) / "route"
            route.write_text("Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\neth0 00001EAC 00000000 0001 0 0 0 0000FFFF 0 0 0\n")
            original = Path
            def fake_path(value):
                if value == "/proc/net/route":
                    return route
                return original(value)
            with patch.object(probe, "Path", side_effect=fake_path):
                probe.require_no_default_route()
            route.write_text("Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\neth0 00000000 01001EAC 0003 0 0 0 00000000 0 0 0\n")
            with patch.object(probe, "Path", side_effect=fake_path), self.assertRaisesRegex(
                    RuntimeError, "synthetic_egress_default_route_present"):
                probe.require_no_default_route()


if __name__ == "__main__":
    unittest.main()

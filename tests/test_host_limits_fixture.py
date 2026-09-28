"""Fail-closed fixture gates/cleanup; actual enforcement requires Docker CI."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_host_limits_contract as fixture

IMAGE_ID = "sha256:" + "a" * 64


def configuration():
    return {"Image": IMAGE_ID, "Config": {"User": "65534:65534"}, "HostConfig": {
        "Memory": 134217728, "MemorySwap": 134217728, "PidsLimit": 24,
        "CpuPeriod": 100000, "CpuQuota": 50000, "ReadonlyRootfs": True,
        "NetworkMode": "none", "CgroupnsMode": "private", "Privileged": False,
        "LogConfig": {"Type": "none"}, "RestartPolicy": {"Name": "no"},
        "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges=true"],
    }}


class HostLimitsFixtureTests(unittest.TestCase):
    def test_gate_before_docker_and_unsupported_cgroup_no_pull(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(fixture, "command") as command:
            with self.assertRaisesRegex(RuntimeError, "synthetic_host_gate_required"):
                fixture.main()
            command.assert_not_called()
        with patch.dict(os.environ, {"AGENT_EPHEMERAL_HOST_TEST": "1"}), \
                patch.object(fixture, "command", return_value="1") as command:
            with self.assertRaisesRegex(RuntimeError, "synthetic_host_cgroup_v2_required"):
                fixture.main()
            self.assertEqual(command.call_count, 1)

    def test_weakened_configuration_rejected(self):
        good = configuration()
        fixture.verify_config(good, IMAGE_ID)
        for key, value in {"Memory": 0, "MemorySwap": -1, "PidsLimit": 0,
                           "CpuQuota": 0, "CpuPeriod": 50000, "Privileged": True,
                           "ReadonlyRootfs": False, "NetworkMode": "host",
                           "CgroupnsMode": "host", "CapDrop": [], "SecurityOpt": [],
                           "LogConfig": {"Type": "json-file"},
                           "RestartPolicy": {"Name": "always"}}.items():
            candidate = deepcopy(good)
            candidate["HostConfig"][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "synthetic_host_config_mismatch"):
                fixture.verify_config(candidate, IMAGE_ID)
        good["Config"]["User"] = "0"
        with self.assertRaisesRegex(RuntimeError, "synthetic_host_config_mismatch"):
            fixture.verify_config(good, IMAGE_ID)

    def test_timeout_removes_only_fixture_and_checks_absence(self):
        calls = []

        def command(args, timeout=45):
            calls.append(args)
            if args[1] == "inspect":
                return json.dumps([configuration()])
            if args[1] == "start":
                raise subprocess.TimeoutExpired("synthetic", timeout)
            return ""

        with patch.object(fixture, "command", side_effect=command):
            with self.assertRaises(subprocess.TimeoutExpired):
                fixture.run_probe(IMAGE_ID, "cpu")
        name = calls[0][3]
        self.assertTrue(name.startswith("synthetic-host-limits-"))
        self.assertEqual(calls[-2], ["docker", "rm", "--force", name])
        self.assertEqual(calls[-1][-1], "name=^/" + name + "$")


if __name__ == "__main__":
    unittest.main()

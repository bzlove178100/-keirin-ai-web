"""Fail-closed launcher/image provenance checks without Docker or network access."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_host_limits_contract as fixture


IMAGE_ID = "sha256:" + "a" * 64


def approved_image():
    return {
        "Id": IMAGE_ID,
        "Os": "linux",
        "Architecture": "amd64",
        "RepoDigests": [fixture.APPROVED_REPO_DIGEST],
    }


def launched(mode="cpu"):
    return {
        "Config": {
            "Entrypoint": [fixture.LAUNCHER],
            "Cmd": [fixture.PROBE, mode],
        }
    }


class LauncherImageContractTests(unittest.TestCase):
    def test_only_exact_approved_linux_amd64_manifest_is_accepted(self):
        self.assertEqual(fixture.verify_image_provenance(approved_image()), IMAGE_ID)
        mutations = [
            ("Os", "windows"),
            ("Architecture", "arm64"),
            ("Id", "sha256:not-a-digest"),
            ("RepoDigests", ["python@sha256:" + "b" * 64]),
            ("RepoDigests", []),
        ]
        for key, value in mutations:
            candidate = deepcopy(approved_image())
            candidate[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(
                    RuntimeError, "synthetic_host_image_provenance_invalid"):
                fixture.verify_image_provenance(candidate)

    def test_explicit_python_launcher_and_exact_probe_command_are_required(self):
        good = launched()
        fixture.verify_launcher(good, [fixture.PROBE, "cpu"])
        for config in (
            {"Entrypoint": None, "Cmd": [fixture.PROBE, "cpu"]},
            {"Entrypoint": ["/bin/sh"], "Cmd": [fixture.PROBE, "cpu"]},
            {"Entrypoint": [fixture.LAUNCHER], "Cmd": ["-c", "print('unexpected')"]},
            {"Entrypoint": [fixture.LAUNCHER], "Cmd": [fixture.PROBE, "memory"]},
        ):
            with self.subTest(config=config), self.assertRaisesRegex(
                    RuntimeError, "synthetic_host_launcher_mismatch"):
                fixture.verify_launcher({"Config": config}, [fixture.PROBE, "cpu"])

    def test_create_command_uses_digest_resolved_image_id_and_no_shell(self):
        args = fixture.create_args("synthetic-name", IMAGE_ID, "cpu")
        entry = args.index("--entrypoint")
        self.assertEqual(args[entry + 1], fixture.LAUNCHER)
        self.assertEqual(args[-3:], [IMAGE_ID, fixture.PROBE, "cpu"])
        self.assertNotIn("/bin/sh", args)
        self.assertNotIn("-c", args)
        self.assertNotIn(fixture.IMAGE, args)


if __name__ == "__main__":
    unittest.main()

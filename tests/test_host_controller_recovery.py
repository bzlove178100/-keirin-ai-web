"""Synthetic recovery identity, no-replay and persistence rejection tests."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import host_controller_recovery as recovery
from test_host_limits_fixture import configuration, IMAGE_ID

CONTAINER_ID = "b" * 64


def intent():
    return {"version": 1, "run_id": "c" * 32, "image_id": IMAGE_ID, "container_id": CONTAINER_ID}


def container():
    data = configuration()
    data.update(Id=CONTAINER_ID, Name="/" + recovery.name_for(intent()))
    data["Config"]["Labels"] = {recovery.LABEL: intent()["run_id"]}
    return data


class ControllerRecoveryTests(unittest.TestCase):
    def test_invalid_intent_never_reaches_docker(self):
        for key, value in (("version", True), ("run_id", ""), ("run_id", "x;all"),
                           ("image_id", "python:latest"), ("container_id", "short")):
            data = intent()
            data[key] = value
            with self.subTest(key=key, value=value), patch.object(recovery, "command") as command:
                with self.assertRaisesRegex(RuntimeError, "synthetic_recovery_intent_invalid"):
                    recovery.reconcile(data)
                command.assert_not_called()

    def test_duplicate_and_mismatched_candidates_are_never_removed(self):
        variants = []
        for key, value in (("Id", "d" * 64), ("Name", "/unrelated"), ("Image", "sha256:" + "e" * 64)):
            data = container()
            data[key] = value
            variants.append(data)
        data = container()
        data["Config"]["Labels"] = {recovery.LABEL: "d" * 32}
        variants.append(data)
        data = container()
        data["HostConfig"]["Privileged"] = True
        variants.append(data)
        for data in variants:
            with self.subTest(data=data), patch.object(recovery, "command", side_effect=[CONTAINER_ID, json.dumps([data])]) as command:
                with self.assertRaises(RuntimeError):
                    recovery.reconcile(intent())
                self.assertFalse(any(call.args[0][1] == "rm" for call in command.call_args_list))
        with patch.object(recovery, "command", return_value=CONTAINER_ID + "\n" + "d" * 64) as command:
            with self.assertRaisesRegex(RuntimeError, "synthetic_recovery_ambiguous_identity"):
                recovery.reconcile(intent())
            self.assertEqual(command.call_count, 1)
        wrong_receipt = intent()
        wrong_receipt["container_id"] = "d" * 64
        with patch.object(recovery, "command", side_effect=[CONTAINER_ID, json.dumps([container()])]) as command:
            with self.assertRaisesRegex(RuntimeError, "synthetic_recovery_identity_mismatch"):
                recovery.reconcile(wrong_receipt)
            self.assertEqual(command.call_count, 2)

    def test_full_id_removal_then_idempotent_absence_with_or_without_receipt(self):
        for receipt in (None, CONTAINER_ID):
            data = intent()
            data["container_id"] = receipt
            with patch.object(recovery, "command", side_effect=[CONTAINER_ID, json.dumps([container()]), "", "", ""]) as command:
                self.assertEqual(recovery.reconcile(data), "removed")
                self.assertEqual(recovery.reconcile(data), "absent")
                removals = [call.args[0] for call in command.call_args_list if call.args[0][1] == "rm"]
                self.assertEqual(removals, [["docker", "rm", "--force", CONTAINER_ID]])

    def test_failed_removal_has_no_blind_retry_and_readback_is_required(self):
        for tail in ([RuntimeError("synthetic_failure")], ["", CONTAINER_ID, json.dumps([container()])]):
            with patch.object(recovery, "command", side_effect=[CONTAINER_ID, json.dumps([container()]), *tail]) as command:
                with self.assertRaises(RuntimeError):
                    recovery.reconcile(intent())
                self.assertEqual(sum(call.args[0][1] == "rm" for call in command.call_args_list), 1)

    def test_intent_roundtrip_and_invalid_persisted_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent.json"
            data = intent()
            data["container_id"] = None
            recovery.save_intent(path, data)
            self.assertEqual(recovery.read_intent(path), data)
            data["container_id"] = CONTAINER_ID
            recovery.save_intent(path, data)
            self.assertEqual(recovery.read_intent(path), data)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.write_text("x" * 1025)
            with self.assertRaisesRegex(RuntimeError, "synthetic_recovery_intent_invalid"):
                recovery.read_intent(path)


if __name__ == "__main__":
    unittest.main()

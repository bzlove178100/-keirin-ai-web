from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core.activation import TRUSTED_TASK_FINGERPRINT, TRUSTED_TASK_ID  # noqa: E402
from agent_core.model import TaskSpec  # noqa: E402
from agent_core.trusted_run_instance import (  # noqa: E402
    TRUSTED_RUN_ID_PREFIX,
    build_trusted_status_run_spec,
    is_trusted_status_run_spec,
    trusted_status_template_spec,
    validate_trusted_status_run_spec,
)

TOKEN = "0123456789abcdef"


class TrustedRunInstanceTest(unittest.TestCase):
    def test_instance_changes_only_task_identity(self):
        template = trusted_status_template_spec(repo_root=ROOT)
        instance = build_trusted_status_run_spec(TOKEN, repo_root=ROOT)
        self.assertEqual(instance.task_id, TRUSTED_RUN_ID_PREFIX + TOKEN)
        self.assertNotEqual(instance.fingerprint(), template.fingerprint())

        normalized = instance.to_dict()
        normalized["task_id"] = TRUSTED_TASK_ID
        self.assertEqual(normalized, template.to_dict())

        identity = validate_trusted_status_run_spec(instance, repo_root=ROOT)
        self.assertEqual(identity.instance_token, TOKEN)
        self.assertEqual(identity.instance_fingerprint, instance.fingerprint())
        self.assertEqual(identity.template_fingerprint, TRUSTED_TASK_FINGERPRINT)

    def test_instance_tokens_are_narrow_and_caller_supplied(self):
        invalid = [
            "short",
            "0123456789ABCDEf",
            "0123456789abcdeg",
            "0123456789abcdef-",
            "0" * 15,
            "0" * 33,
            "../0123456789abcdef",
        ]
        for token in invalid:
            with self.subTest(token=token), self.assertRaises(ValueError):
                build_trusted_status_run_spec(token, repo_root=ROOT)

    def test_template_task_is_not_misclassified_as_fresh_instance(self):
        template = trusted_status_template_spec(repo_root=ROOT)
        self.assertFalse(is_trusted_status_run_spec(template, repo_root=ROOT))
        with self.assertRaisesRegex(ValueError, "trusted_run_instance_id_required"):
            validate_trusted_status_run_spec(template, repo_root=ROOT)

    def test_any_scope_change_is_rejected_even_with_valid_instance_id(self):
        base = build_trusted_status_run_spec(TOKEN, repo_root=ROOT).to_dict()
        mutations = []

        value = deepcopy(base)
        value["inputs"]["repository"] = "other/repository"
        mutations.append(value)

        value = deepcopy(base)
        value["inputs"]["db_write_enabled"] = True
        mutations.append(value)

        value = deepcopy(base)
        value["allowed_actions"].append("github.write_file")
        mutations.append(value)

        value = deepcopy(base)
        value["steps"][0]["action"] = "github.verify_ci"
        mutations.append(value)

        value = deepcopy(base)
        value["steps"][0]["args"]["required_files"] = ["WORK_STATUS.md"]
        mutations.append(value)

        value = deepcopy(base)
        value["completion_conditions"] = ["different"]
        mutations.append(value)

        for payload in mutations:
            with self.subTest(payload=payload):
                try:
                    candidate = TaskSpec.from_dict(payload)
                except ValueError:
                    continue
                self.assertFalse(is_trusted_status_run_spec(candidate, repo_root=ROOT))
                with self.assertRaises(ValueError):
                    validate_trusted_status_run_spec(candidate, repo_root=ROOT)

    def test_different_instances_have_distinct_full_fingerprints_same_template(self):
        first = build_trusted_status_run_spec("0" * 16, repo_root=ROOT)
        second = build_trusted_status_run_spec("1" * 16, repo_root=ROOT)
        first_id = validate_trusted_status_run_spec(first, repo_root=ROOT)
        second_id = validate_trusted_status_run_spec(second, repo_root=ROOT)
        self.assertNotEqual(first_id.instance_fingerprint, second_id.instance_fingerprint)
        self.assertEqual(first_id.template_fingerprint, second_id.template_fingerprint)
        self.assertEqual(first_id.template_fingerprint, TRUSTED_TASK_FINGERPRINT)


if __name__ == "__main__":
    unittest.main()

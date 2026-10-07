import copy
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent_core.adapters import ToolRegistry
from agent_core.model import StepSpec, TaskSpec
from agent_core.note_drafts import NoteDraftAdapter, content_digest
from agent_core.runner import AgentRunner, BlockedAction
from agent_core.store import FileStateStore

URL = "https://editor.note.com/synthetic-existing-draft/edit"


class Backend:
    def __init__(self):
        self.value = dict(url=URL, account_id="synthetic_owner", status="draft",
                          persisted=True, title="old", body="old body")
        self.writes = 0
        self.mode = "normal"

    def read_persisted_draft(self, url):
        return copy.deepcopy(self.value)

    def update_existing_draft(self, *, url, title, body, expected_content_sha256):
        assert expected_content_sha256 == content_digest(self.value["title"], self.value["body"])
        self.writes += 1
        if self.mode != "not_saved":
            self.value.update(title=title, body=body)
        if self.mode == "lost_response":
            raise RuntimeError("untrusted-provider-error-private-fixture")


class NoteDraftTests(unittest.TestCase):
    def setUp(self):
        self.backend = Backend()
        self.adapter = NoteDraftAdapter(account_id="synthetic_owner", backend=self.backend)
        self.args = dict(draft_url=URL, title="new", body="new body",
                         expected_content_sha256=content_digest("old", "old body"))

    def test_unbound_adapter_is_blocked_and_exposes_no_publication_or_message_action(self):
        adapter = NoteDraftAdapter(account_id="synthetic_owner")
        with self.assertRaisesRegex(BlockedAction, "backend_unbound"):
            adapter.update(self.args, {})
        registry = ToolRegistry()
        registry.register(adapter)
        self.assertEqual(set(registry.actions()), {"note.read_draft", "note.update_draft"})
        with self.assertRaisesRegex(ValueError, "non_read_action"):
            registry.require_read_only(["note.update_draft"])

    def test_save_requires_persisted_readback_and_repeated_content_does_not_write(self):
        result = self.adapter.update(self.args, {})
        self.assertTrue(result.artifacts[0].persistent_saved)
        self.assertTrue(result.data["verified"])
        self.assertFalse(self.adapter.update(self.args, {}).data["write_performed"])
        self.assertEqual(self.backend.writes, 1)

    def test_successful_click_without_saved_content_is_not_success(self):
        self.backend.mode = "not_saved"
        with self.assertRaisesRegex(BlockedAction, "saved_content_not_verified"):
            self.adapter.update(self.args, {})

    def test_different_account_public_article_and_unsaved_editor_block_before_write(self):
        for field, value in (("account_id", "other"), ("status", "published"),
                             ("persisted", False), ("url", URL + "/other"), ("title", None)):
            with self.subTest(field=field):
                self.setUp()
                self.backend.value[field] = value
                with self.assertRaises(BlockedAction): self.adapter.update(self.args, {})
                self.assertEqual(self.backend.writes, 0)

    def test_intervening_edit_is_not_overwritten(self):
        self.backend.value["body"] = "edited by user"
        with self.assertRaisesRegex(BlockedAction, "changed_since_read"):
            self.adapter.update(self.args, {})
        self.assertEqual(self.backend.writes, 0)

    def test_dry_run_extra_arguments_and_auth_or_foreign_urls_cannot_write(self):
        with self.assertRaises(BlockedAction): self.adapter.update(self.args, {"dry_run": True})
        with self.assertRaises(BlockedAction): self.adapter.update({**self.args, "publish": True}, {})
        for url in ("https://editor.note.com/new", "https://note.com/login",
                    URL + "?token=secret", "https://editor.note.com.evil.test/x",
                    "https://user:password@editor.note.com/x", URL + "#secret"):
            with self.assertRaises(BlockedAction): self.adapter.update({**self.args, "draft_url": url}, {})
        self.assertEqual(self.backend.writes, 0)

    def test_lost_response_blocks_resume_without_duplicate_write_or_error_leak(self):
        self.backend.mode = "lost_response"
        spec = TaskSpec(task_id="note-fixture", title="Synthetic draft", goal="Verify draft save",
                        allowed_actions=("note.update_draft",),
                        steps=(StepSpec("save", "note.update_draft", args=self.args,
                                        retry_safe=True, max_attempts=3),))
        with TemporaryDirectory() as tmp:
            store = FileStateStore(tmp)
            runner = AgentRunner(store, self.adapter.actions())
            first = runner.run(spec)
            second = runner.run(spec)
            self.assertEqual(first.status, "blocked")
            self.assertEqual(second.status, "blocked")
            self.assertIn("note_save_outcome_unknown", first.blocked_reason)
            self.assertEqual(self.backend.writes, 1)
            self.assertNotIn("untrusted-provider-error-private-fixture", str(store.load_state(spec.task_id)))

    def test_read_receipt_does_not_persist_provider_extra_fields_or_content(self):
        self.backend.value["cookie"] = "private-fixture"
        result = self.adapter.read({"draft_url": URL}, {})
        self.assertEqual(set(result.data), {"draft_url", "status", "content_sha256"})
        self.assertNotIn("private-fixture", str(result))


if __name__ == "__main__":
    unittest.main()

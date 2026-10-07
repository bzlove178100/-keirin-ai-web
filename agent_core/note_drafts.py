"""Existing-draft actions for an explicitly injected, authorized browser host.

No note API, browser transport, authentication, account creation, publication or
messaging is supplied here. A save click is not proof: the host must reopen the
draft and read persisted content. The default is unbound and cannot call note.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Protocol
from urllib.parse import urlsplit

from .adapters import Capability
from .model import ActionResult, ArtifactUpdate
from .runner import BlockedAction


def content_digest(title: str, body: str) -> str:
    return hashlib.sha256(json.dumps([title, body], ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


class NoteDraftBackend(Protocol):
    def read_persisted_draft(self, url: str) -> dict: ...

    def update_existing_draft(self, *, url: str, title: str, body: str,
                              expected_content_sha256: str) -> None: ...


class NoteDraftAdapter:
    """Host must enforce the expected hash immediately before UI editing.

    Reads must identify the signed-in account and private draft, never merely an
    unsaved editor buffer. Use single-attempt, non-retry-safe runner steps for
    writes; ambiguous outcomes require reconciliation, not another save.
    """
    name = "note-existing-drafts"

    def __init__(self, *, account_id: str, backend: NoteDraftBackend | None = None):
        if not isinstance(account_id, str) or not account_id.strip():
            raise ValueError("note_account_id_required")
        self.account_id, self.backend = account_id, backend

    def capabilities(self):
        return (
            Capability("note.read_draft", "read", ("note:drafts:read",), True),
            Capability("note.update_draft", "write", ("note:drafts:read", "note:drafts:write"), False),
        )

    def actions(self):
        return {"note.read_draft": self.read, "note.update_draft": self.update}

    @staticmethod
    def _url(value):
        if not isinstance(value, str):
            raise BlockedAction("note_existing_draft_url_required")
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or parsed.netloc != "editor.note.com"
                or parsed.query or parsed.fragment or parsed.path in ("/", "/new", "/new/")
                or not re.fullmatch(r"/[A-Za-z0-9/_-]+", parsed.path)):
            raise BlockedAction("note_existing_draft_url_required")
        return value

    def _snapshot(self, url):
        if self.backend is None:
            raise BlockedAction("note_browser_backend_unbound")
        try:
            value = self.backend.read_persisted_draft(url)
        except Exception:
            raise BlockedAction("note_readback_unavailable") from None
        if not isinstance(value, dict) or value.get("account_id") != self.account_id:
            raise BlockedAction("note_account_unverified")
        if (value.get("url") != url or value.get("status") != "draft"
                or value.get("persisted") is not True
                or not all(isinstance(value.get(k), str) for k in ("title", "body"))):
            raise BlockedAction("note_persisted_private_draft_unverified")
        return content_digest(value["title"], value["body"])

    def read(self, args, context):
        if set(args) != {"draft_url"}:
            raise BlockedAction("note_read_arguments_invalid")
        url = self._url(args["draft_url"])
        return ActionResult(data={"draft_url": url, "status": "draft",
                                  "content_sha256": self._snapshot(url)})

    def update(self, args, context):
        if context.get("dry_run") is True:
            raise BlockedAction("note_write_not_available_in_dry_run")
        if (set(args) != {"draft_url", "title", "body", "expected_content_sha256"}
                or not all(isinstance(args.get(k), str) for k in ("title", "body"))
                or not re.fullmatch(r"[0-9a-f]{64}", str(args.get("expected_content_sha256", "")))):
            raise BlockedAction("note_update_arguments_invalid")
        url = self._url(args["draft_url"])
        desired = content_digest(args["title"], args["body"])
        before = self._snapshot(url)
        if before != desired:
            if before != args["expected_content_sha256"]:
                raise BlockedAction("note_draft_changed_since_read")
            try:
                self.backend.update_existing_draft(url=url, title=args["title"], body=args["body"],
                                                  expected_content_sha256=before)
            except Exception:
                # Stop even if a caller mistakenly marks its runner step retry-safe.
                raise BlockedAction("note_save_outcome_unknown") from None
            if self._snapshot(url) != desired:
                raise BlockedAction("note_saved_content_not_verified")
        return ActionResult(message="private note draft content verified",
                            data={"verified": True, "write_performed": before != desired},
                            artifacts=(ArtifactUpdate(artifact_id="note-draft:" + url,
                                kind="note-draft", locator=url, verified=True,
                                persistent_saved=True, metadata={"content_sha256": desired}),))

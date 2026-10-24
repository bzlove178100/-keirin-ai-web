"""One private document task with host-selected input/output, no network access."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Callable

from .adapters import Capability, ToolRegistry
from .decision_loop import DecisionLoop, Goal
from .model import ActionResult
from .store import FileStateStore

LIMIT = 16000


def _read(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("regular_private_file_required")
        data = handle.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError("document_too_large")
    data.decode("utf-8")
    return data


class DocumentTools:
    """Trusted private directory only; not a sandbox for hostile local processes.

    The model receives named actions, never arbitrary paths or shell commands.
    Verification checks nonempty required sections and source identity, not the
    semantic accuracy of generated prose. The host must choose nonsecret input.
    """

    name = "private-document-task"

    def __init__(self, source: Path, output: Path, required_sections: tuple[str, ...]):
        self.source, self.output = Path(source).absolute(), Path(output).absolute()
        if (self.source == self.output or self.source.resolve() == self.output.resolve()
                or not required_sections or len(set(required_sections)) != len(required_sections)
                or any(type(x) is not str or not x.strip() or "\n" in x or x.startswith("#")
                       for x in required_sections)):
            raise ValueError("invalid_document_scope")
        self.sections = required_sections
        self.source_hash = hashlib.sha256(_read(self.source)).hexdigest()
        self.parent = self.output.parent.resolve(strict=True)
        if self.output.parent != self.parent:
            raise ValueError("output_parent_must_be_canonical")
        if self.output.exists() or self.output.is_symlink():
            _read(self.output)

    def binding(self) -> str:
        # Paths stay in private goal state as a digest; model sees only selected text.
        scope = repr((str(self.source), str(self.output), self.source_hash, self.sections))
        return "document-v1:" + hashlib.sha256(scope.encode()).hexdigest()

    def capabilities(self):
        return (
            Capability("document.read_source", "read", description="Read the fixed source; args must be {}."),
            Capability("document.write_report", "write", description="Write the fixed private report; args: {content: UTF-8 text}. "
                       "Use these Markdown headings, each with nonempty content: " + ", ".join("## " + x for x in self.sections)),
            Capability("document.inspect_report", "read", description="Check source identity and required report sections; args {}."),
        )

    def actions(self):
        return {"document.read_source": self.read_source,
                "document.write_report": self.write_report,
                "document.inspect_report": self.inspect_report}

    def _source(self):
        data = _read(self.source)
        if hashlib.sha256(data).hexdigest() != self.source_hash:
            raise ValueError("source_changed")
        return data

    def read_source(self, args, context):
        if args != {}:
            raise ValueError("unexpected_arguments")
        return ActionResult(data={"text": self._source().decode(), "sha256": self.source_hash})

    def write_report(self, args, context):
        if (set(args) != {"content"} or type(args["content"]) is not str
                or not args["content"].strip() or len(args["content"].encode()) > LIMIT):
            raise ValueError("invalid_report")
        self._source()
        if self.output.parent.resolve(strict=True) != self.parent:
            raise ValueError("output_parent_changed")
        if self.output.exists() or self.output.is_symlink():
            _read(self.output)
        data = args["content"].encode("utf-8")
        fd, temp = tempfile.mkstemp(prefix=".jarvis-report-", dir=self.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self.output)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        return ActionResult(data={"written": True, "sha256": hashlib.sha256(data).hexdigest()})

    def inspect_report(self, args, context):
        if args != {}:
            raise ValueError("unexpected_arguments")
        self._source()
        if not self.output.exists() and not self.output.is_symlink():
            return ActionResult(data={"verified": False, "missing": list(self.sections)})
        data = _read(self.output)
        sections: dict[str, list[str]] = {}
        current = None
        for line in data.decode().splitlines():
            if line.startswith("#"):
                current = line[3:].strip() if line.startswith("## ") else None
                if current in sections:
                    return ActionResult(data={"verified": False, "reason": "duplicate_sections"})
                if current is not None:
                    sections[current] = []
            elif current is not None:
                sections[current].append(line)
        missing = [x for x in self.sections if not "\n".join(sections.get(x, [])).strip()]
        return ActionResult(data={"verified": not missing, "missing": missing,
                                  "sha256": hashlib.sha256(data).hexdigest(),
                                  "source_sha256": self.source_hash})


def run_document_task(*, task_id: str, source: Path, output: Path, state_dir: Path,
                      model: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
                      model_binding: str = "unconfigured",
                      pause_after: int | None = None) -> dict[str, Any]:
    adapter = DocumentTools(source, output, ("Summary", "Next action"))
    registry = ToolRegistry()
    registry.register(adapter)
    goal = Goal(task_id, "Read the supplied source, summarize its facts without invention, "
                "write a private report with Summary and Next action sections, inspect it, "
                "correct omissions when necessary, then report completion.",
                tuple(registry.actions()), "document.inspect_report", {},
                adapter.binding() + ":" + model_binding,
                required_actions=("document.read_source", "document.write_report"))
    return DecisionLoop(store=FileStateStore(state_dir), registry=registry, model=model).run(
        goal, pause_after=pause_after)

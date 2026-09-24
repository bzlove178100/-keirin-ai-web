from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .adapters import ToolRegistry
from .model import TaskSpec
from .runner import AgentRunner, RunOutcome
from .store import FileStateStore


@dataclass(frozen=True)
class PreflightReport:
    ready: bool
    missing_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    registered_capabilities: tuple[dict[str, Any], ...]


class AgentOrchestrator:
    """Preflight a TaskSpec before delegating execution to ``AgentRunner``."""

    def __init__(self, *, registry: ToolRegistry, store: FileStateStore):
        self.registry = registry
        self.store = store

    def preflight(self, spec: TaskSpec, *, allowed_access: Iterable[str] | None = None) -> PreflightReport:
        spec.validate()
        used = {
            action
            for step in spec.steps
            for action in (step.action, step.verify_action)
            if action
        }
        registered = self.registry.actions()
        missing = tuple(sorted(used - set(registered)))
        allowed = set(allowed_access) if allowed_access is not None else None
        forbidden: list[str] = []
        if allowed is not None:
            for action in sorted(used & set(registered)):
                capability = self.registry.capability(action)
                if capability is None or capability.access not in allowed:
                    forbidden.append(action)
        return PreflightReport(
            ready=not missing and not forbidden,
            missing_actions=missing,
            forbidden_actions=tuple(forbidden),
            registered_capabilities=tuple(self.registry.describe()),
        )

    def run(
        self,
        spec: TaskSpec,
        *,
        context: dict[str, Any] | None = None,
        allowed_access: Iterable[str] | None = None,
    ) -> RunOutcome:
        report = self.preflight(spec, allowed_access=allowed_access)
        if report.missing_actions:
            raise ValueError(f"preflight_missing_actions:{','.join(report.missing_actions)}")
        if report.forbidden_actions:
            raise ValueError(f"preflight_forbidden_actions:{','.join(report.forbidden_actions)}")
        return AgentRunner(self.store, self.registry.actions()).run(spec, context=context)

    def run_task_file(
        self,
        task_path: str | Path,
        *,
        context: dict[str, Any] | None = None,
        allowed_access: Iterable[str] | None = None,
    ) -> RunOutcome:
        payload = json.loads(Path(task_path).read_text(encoding="utf-8"))
        return self.run(TaskSpec.from_dict(payload), context=context, allowed_access=allowed_access)

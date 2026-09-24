from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Literal, Mapping, Protocol

from .model import ActionResult
from .runner import Action

AccessMode = Literal["read", "write", "execute"]


@dataclass(frozen=True)
class Capability:
    action: str
    access: AccessMode
    required_permissions: tuple[str, ...] = ()
    supports_dry_run: bool = False
    description: str = ""


class ToolAdapter(Protocol):
    name: str

    def capabilities(self) -> tuple[Capability, ...]: ...

    def actions(self) -> Mapping[str, Action]: ...


class ToolRegistry:
    """Registry that keeps action implementation and permission metadata together."""

    def __init__(self) -> None:
        self._actions: dict[str, Action] = {}
        self._capabilities: dict[str, Capability] = {}
        self._adapter_for_action: dict[str, str] = {}

    def register(self, adapter: ToolAdapter) -> None:
        capabilities = {cap.action: cap for cap in adapter.capabilities()}
        actions = dict(adapter.actions())
        if set(capabilities) != set(actions):
            raise ValueError(f"adapter_capability_action_mismatch:{adapter.name}")
        collisions = sorted(set(actions) & set(self._actions))
        if collisions:
            raise ValueError(f"duplicate_registered_action:{','.join(collisions)}")
        for action, implementation in actions.items():
            self._actions[action] = implementation
            self._capabilities[action] = capabilities[action]
            self._adapter_for_action[action] = adapter.name

    def actions(self) -> dict[str, Action]:
        return dict(self._actions)

    def capability(self, action: str) -> Capability | None:
        return self._capabilities.get(action)

    def describe(self) -> list[dict[str, Any]]:
        return [
            {**asdict(self._capabilities[action]), "adapter": self._adapter_for_action[action]}
            for action in sorted(self._actions)
        ]

    def require_read_only(self, actions: tuple[str, ...] | list[str]) -> None:
        for action in actions:
            capability = self._capabilities.get(action)
            if capability is None:
                raise ValueError(f"action_not_registered:{action}")
            if capability.access != "read":
                raise ValueError(f"non_read_action_forbidden:{action}")


class CallableReadOnlyGitHubAdapter:
    """Read-only GitHub adapter around injected provider callables.

    The core deliberately does not own a GitHub token or HTTP client. The hosting
    runtime injects two read-only functions, which can be backed by a connector,
    GitHub App, test double or another authorized transport.
    """

    name = "github-readonly"

    def __init__(
        self,
        *,
        file_reader: Callable[[str, str, str], Any],
        ci_reader: Callable[[str, str], Any],
    ) -> None:
        self.file_reader = file_reader
        self.ci_reader = ci_reader

    def capabilities(self) -> tuple[Capability, ...]:
        return (
            Capability(
                action="github.read_main",
                access="read",
                required_permissions=("contents:read",),
                supports_dry_run=True,
                description="Read required files from an explicit repository ref.",
            ),
            Capability(
                action="github.verify_ci",
                access="read",
                required_permissions=("actions:read",),
                supports_dry_run=True,
                description="Verify an existing CI state without starting or mutating a run.",
            ),
        )

    def actions(self) -> Mapping[str, Action]:
        return {
            "github.read_main": self._read_main,
            "github.verify_ci": self._verify_ci,
        }

    @staticmethod
    def _repository(context: dict[str, Any]) -> str:
        repository = str((context.get("task_inputs") or {}).get("repository") or "").strip()
        if not repository or "/" not in repository:
            raise ValueError("repository_input_required")
        return repository

    def _read_main(self, args: dict[str, Any], context: dict[str, Any]) -> ActionResult:
        repository = self._repository(context)
        ref = str(args.get("ref") or "main")
        files = [str(path) for path in args.get("required_files") or ()]
        if not files:
            raise ValueError("required_files_missing")
        results: dict[str, Any] = {}
        for path in files:
            results[path] = self.file_reader(repository, path, ref)
        return ActionResult(
            message=f"read {len(results)} repository files",
            data={"repository": repository, "ref": ref, "files": results},
        )

    def _verify_ci(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        repository = self._repository(context)
        ref = str(args.get("ref") or "main")
        status = self.ci_reader(repository, ref)
        verified = False
        if isinstance(status, bool):
            verified = status
        elif isinstance(status, dict):
            conclusion = str(status.get("conclusion") or "").lower()
            state = str(status.get("status") or "").lower()
            verified = conclusion == "success" or (state == "completed" and conclusion == "success")
        return {"verified": verified, "status": status}

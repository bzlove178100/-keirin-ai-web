from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters import Capability, ToolRegistry
from .orchestrator import AgentOrchestrator, PreflightReport
from .runtime_bridge import BridgeToolAdapter, RuntimeBridge
from .store import FileStateStore

_FORBIDDEN_BINDING_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "service_role",
    "api_key",
    "apikey",
    "authorization",
}


@dataclass(frozen=True)
class RuntimeBinding:
    provider: str
    action: str
    access: str
    required_permissions: tuple[str, ...] = ()
    supports_dry_run: bool = False
    description: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RuntimeBinding":
        forbidden = {str(key).lower() for key in payload} & _FORBIDDEN_BINDING_KEYS
        if forbidden:
            raise ValueError(f"credentials_forbidden_in_binding:{','.join(sorted(forbidden))}")
        provider = str(payload.get("provider") or "").strip()
        action = str(payload.get("action") or "").strip()
        access = str(payload.get("access") or "").strip()
        if not provider:
            raise ValueError("binding_provider_required")
        if not action:
            raise ValueError("binding_action_required")
        if access not in {"read", "write", "execute"}:
            raise ValueError("binding_access_invalid")
        return cls(
            provider=provider,
            action=action,
            access=access,
            required_permissions=tuple(str(value) for value in payload.get("required_permissions") or ()),
            supports_dry_run=bool(payload.get("supports_dry_run", False)),
            description=str(payload.get("description") or ""),
        )

    def capability(self) -> Capability:
        return Capability(
            action=self.action,
            access=self.access,  # type: ignore[arg-type]
            required_permissions=self.required_permissions,
            supports_dry_run=self.supports_dry_run,
            description=self.description,
        )


@dataclass(frozen=True)
class RuntimeManifest:
    schema_version: str
    bindings: tuple[RuntimeBinding, ...]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RuntimeManifest":
        forbidden = {str(key).lower() for key in payload} & _FORBIDDEN_BINDING_KEYS
        if forbidden:
            raise ValueError(f"credentials_forbidden_in_manifest:{','.join(sorted(forbidden))}")
        schema = str(payload.get("schema_version") or "")
        if schema != "agent-runtime-bindings-v1":
            raise ValueError("runtime_manifest_schema_mismatch")
        bindings = tuple(RuntimeBinding.from_dict(item) for item in payload.get("bindings") or ())
        if not bindings:
            raise ValueError("runtime_bindings_required")
        seen: set[str] = set()
        for binding in bindings:
            if binding.action in seen:
                raise ValueError(f"duplicate_runtime_binding:{binding.action}")
            seen.add(binding.action)
        return cls(schema_version=schema, bindings=bindings)

    @classmethod
    def load(cls, path: str | Path) -> "RuntimeManifest":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


class BoundRuntime:
    """Build a ToolRegistry from a credential-free manifest and host bridge."""

    def __init__(
        self,
        *,
        manifest: RuntimeManifest,
        bridge: RuntimeBridge,
        state_dir: str | Path,
    ) -> None:
        self.manifest = manifest
        self.bridge = bridge
        self.store = FileStateStore(state_dir)
        self.registry = ToolRegistry()
        grouped: dict[str, list[Capability]] = {}
        for binding in manifest.bindings:
            grouped.setdefault(binding.provider, []).append(binding.capability())
        for provider, capabilities in sorted(grouped.items()):
            self.registry.register(
                BridgeToolAdapter(
                    name=f"bridge:{provider}",
                    bridge=bridge,
                    capabilities=tuple(capabilities),
                )
            )
        self.orchestrator = AgentOrchestrator(registry=self.registry, store=self.store)

    def preflight_task_file(
        self,
        task_path: str | Path,
        *,
        allowed_access: set[str] | None = None,
    ) -> PreflightReport:
        from .model import TaskSpec

        payload = json.loads(Path(task_path).read_text(encoding="utf-8"))
        spec = TaskSpec.from_dict(payload)
        return self.orchestrator.preflight(spec, allowed_access=allowed_access)

    def run_task_file(
        self,
        task_path: str | Path,
        *,
        context: dict[str, Any] | None = None,
        allowed_access: set[str] | None = None,
    ):
        return self.orchestrator.run_task_file(
            task_path,
            context=context,
            allowed_access=allowed_access,
        )

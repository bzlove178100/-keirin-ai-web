from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from .adapters import Capability
from .model import ActionResult, ArtifactUpdate
from .runner import Action, BlockedAction


class RuntimeBridge(Protocol):
    """Host-supplied bridge for authorized external tool calls.

    The bridge owns provider authentication and transport. Task definitions and this
    repository only refer to capability names and structured arguments.
    """

    def invoke(
        self,
        *,
        capability: Capability,
        args: dict[str, Any],
        context: dict[str, Any],
    ) -> Any: ...


@dataclass(frozen=True)
class BridgeResponse:
    message: str = ""
    data: dict[str, Any] | None = None
    artifacts: tuple[ArtifactUpdate, ...] = ()
    blocked_reason: str | None = None


class BridgeToolAdapter:
    """Expose declared capabilities as AgentRunner actions through a host bridge.

    A provider-returned ``blocked_reason`` is untrusted transport data. It is converted
    to a fixed persistence-safe classification instead of being copied into task state.
    """

    def __init__(
        self,
        *,
        name: str,
        bridge: RuntimeBridge,
        capabilities: tuple[Capability, ...],
    ) -> None:
        if not name.strip():
            raise ValueError("adapter_name_required")
        if not capabilities:
            raise ValueError("capabilities_required")
        actions = [cap.action for cap in capabilities]
        if len(actions) != len(set(actions)):
            raise ValueError("duplicate_adapter_capability")
        self.name = name
        self.bridge = bridge
        self._capabilities = {cap.action: cap for cap in capabilities}

    def capabilities(self) -> tuple[Capability, ...]:
        return tuple(self._capabilities[action] for action in sorted(self._capabilities))

    def actions(self) -> Mapping[str, Action]:
        return {action: self._build_action(capability) for action, capability in self._capabilities.items()}

    def _build_action(self, capability: Capability) -> Action:
        def action(args: dict[str, Any], context: dict[str, Any]) -> ActionResult:
            response = self.bridge.invoke(
                capability=capability,
                args=dict(args),
                context=dict(context),
            )
            return self._normalise_response(response)

        return action

    @staticmethod
    def _normalise_response(value: Any) -> ActionResult:
        if isinstance(value, ActionResult):
            return value
        if isinstance(value, BridgeResponse):
            if value.blocked_reason:
                raise BlockedAction("runtime_bridge_blocked")
            return ActionResult(
                message=value.message,
                artifacts=tuple(value.artifacts),
                data=dict(value.data or {}),
            )
        if isinstance(value, dict):
            blocked_reason = value.get("blocked_reason")
            if blocked_reason:
                raise BlockedAction("runtime_bridge_blocked")
            artifacts = tuple(
                item if isinstance(item, ArtifactUpdate) else ArtifactUpdate(**item)
                for item in value.get("artifacts", ())
            )
            return ActionResult(
                message=str(value.get("message") or ""),
                artifacts=artifacts,
                data=dict(value.get("data") or {}),
            )
        if value is None:
            return ActionResult()
        raise TypeError("unsupported_bridge_response")

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .adapters import Capability, ToolAdapter
from .credential_provider import (
    CredentialProvider,
    CredentialProviderError,
    CredentialSnapshot,
    _capabilities,
    _seconds,
)
from .runner import Action, BlockedAction

CREDENTIAL_CONTEXT_KEY = "_agent_credential_snapshot_v1"


@dataclass(frozen=True, slots=True)
class CredentialRequirement:
    action: str
    capabilities: tuple[str, ...]
    minimum_ttl_seconds: int = 300
    require_known_expiry: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.action, str) or not self.action.strip() or self.action != self.action.strip():
            raise ValueError("credential_requirement_action_invalid")
        object.__setattr__(self, "capabilities", _capabilities(self.capabilities))
        _seconds(self.minimum_ttl_seconds, "credential_requirement_ttl_invalid")
        if type(self.require_known_expiry) is not bool:
            raise ValueError("credential_requirement_known_expiry_invalid")


def require_credential_snapshot(context: Mapping[str, Any]) -> CredentialSnapshot:
    """Return the in-memory snapshot injected by a credential-gated adapter action."""
    if not isinstance(context, Mapping):
        raise RuntimeError("credential_context_missing")
    value = context.get(CREDENTIAL_CONTEXT_KEY)
    if not isinstance(value, CredentialSnapshot):
        raise RuntimeError("credential_context_missing")
    return value


def _contains_snapshot(value: Any, *, seen: set[int] | None = None) -> bool:
    if isinstance(value, CredentialSnapshot):
        return True
    if seen is None:
        seen = set()
    if isinstance(value, Mapping):
        marker = id(value)
        if marker in seen:
            return False
        seen.add(marker)
        return any(_contains_snapshot(key, seen=seen) or _contains_snapshot(child, seen=seen)
                   for key, child in value.items())
    if isinstance(value, (list, tuple, set, frozenset)):
        marker = id(value)
        if marker in seen:
            return False
        seen.add(marker)
        return any(_contains_snapshot(child, seen=seen) for child in value)
    return False


class CredentialBoundToolAdapter:
    """Wrap every action of an adapter behind a credential snapshot gate.

    Credential acquisition occurs before the underlying provider action is invoked.
    Provider/source failures are converted to fixed ``BlockedAction`` reasons outside
    the credential exception handler, so secret-bearing provider exceptions are not
    persisted by ``AgentRunner``. The snapshot is added only to the local action
    context; it is never inserted into TaskSpec, step args or runner state.
    """

    def __init__(
        self,
        adapter: ToolAdapter,
        provider: CredentialProvider,
        requirements: Iterable[CredentialRequirement],
    ) -> None:
        if adapter is None:
            raise ValueError("credential_adapter_required")
        if provider is None:
            raise ValueError("credential_provider_required")

        capabilities = tuple(adapter.capabilities())
        actions = dict(adapter.actions())
        cap_names = {cap.action for cap in capabilities}
        if len(cap_names) != len(capabilities) or cap_names != set(actions):
            raise ValueError("credential_adapter_action_contract_mismatch")

        requirement_map: dict[str, CredentialRequirement] = {}
        for requirement in requirements:
            if type(requirement) is not CredentialRequirement:
                raise ValueError("credential_requirement_invalid")
            if requirement.action in requirement_map:
                raise ValueError("duplicate_credential_requirement")
            requirement_map[requirement.action] = requirement
        if set(requirement_map) != set(actions):
            raise ValueError("credential_requirements_must_cover_all_actions")

        self._adapter = adapter
        self._provider = provider
        self._capabilities = capabilities
        self._actions = actions
        self._requirements = requirement_map
        inner_name = getattr(adapter, "name", type(adapter).__name__)
        self.name = f"credential-gated:{inner_name}"

    def __repr__(self) -> str:
        return (
            f"CredentialBoundToolAdapter(name={self.name!r}, "
            f"provider={type(self._provider).__name__!r}, credentials='<redacted>')"
        )

    def capabilities(self) -> tuple[Capability, ...]:
        return self._capabilities

    def actions(self) -> Mapping[str, Action]:
        wrapped: dict[str, Action] = {}
        for action_name, implementation in self._actions.items():
            requirement = self._requirements[action_name]

            def invoke(
                args: dict[str, Any],
                context: dict[str, Any],
                *,
                _implementation=implementation,
                _requirement=requirement,
            ) -> Any:
                snapshot: CredentialSnapshot | None = None
                failure: str | None = None
                interrupted: type[BaseException] | None = None
                try:
                    snapshot = self._provider.snapshot(
                        _requirement.capabilities,
                        minimum_ttl_seconds=_requirement.minimum_ttl_seconds,
                        require_known_expiry=_requirement.require_known_expiry,
                    )
                except CredentialProviderError:
                    failure = "credential_unavailable"
                except BaseException as error:
                    failure = "credential_provider_failure"
                    if isinstance(error, KeyboardInterrupt):
                        interrupted = KeyboardInterrupt
                    elif isinstance(error, SystemExit):
                        interrupted = SystemExit

                # Raise only after leaving provider exception handling, so a provider
                # exception carrying token material cannot survive as __context__.
                if failure is not None:
                    if interrupted is KeyboardInterrupt:
                        raise KeyboardInterrupt("credential_provider_interrupted")
                    if interrupted is SystemExit:
                        raise SystemExit("credential_provider_interrupted")
                    raise BlockedAction(failure)

                if not isinstance(snapshot, CredentialSnapshot):
                    raise BlockedAction("credential_provider_invalid_snapshot")
                local_context = dict(context)
                local_context[CREDENTIAL_CONTEXT_KEY] = snapshot
                result = _implementation(args, local_context)
                if _contains_snapshot(result):
                    raise RuntimeError("credential_snapshot_return_forbidden")
                return result

            wrapped[action_name] = invoke
        return wrapped

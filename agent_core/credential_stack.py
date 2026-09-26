from __future__ import annotations

from typing import Callable, Iterable

from .adapters import ToolAdapter
from .credential_adapter import CredentialBoundToolAdapter, CredentialRequirement
from .durable_secret_store import DurableSecretBackend, DurableVersionedSecretStore
from .refresh_credentials import CredentialBinding, RefreshingCredentialProvider
from .versioned_secret_store import RefreshExchange, VersionedHostCredentialSource


def build_durable_credential_bound_adapter(
    *,
    adapter: ToolAdapter,
    binding: CredentialBinding,
    backend: DurableSecretBackend,
    exchange: RefreshExchange,
    requirements: Iterable[CredentialRequirement],
    clock: Callable[[], int] | None = None,
    attempt_id_factory: Callable[[], str] | None = None,
) -> CredentialBoundToolAdapter:
    """Compose the durable refresh boundary without activating any concrete service.

    This function is dependency injection only. ``backend`` and ``exchange`` are supplied
    by the host and may be test doubles. It performs no network I/O, migration, seeding,
    workflow dispatch or background execution by itself.

    The returned adapter exposes provider actions through ``CredentialBoundToolAdapter``.
    The runner/action layer receives only access-only ``CredentialSnapshot`` objects; the
    durable store and refresh exchange remain behind ``VersionedHostCredentialSource``.
    The function deliberately accepts no raw refresh secret, so refresh material cannot
    accidentally become TaskSpec/action input during composition.
    """
    if type(binding) is not CredentialBinding:
        raise ValueError("credential_binding_required")
    if backend is None:
        raise ValueError("durable_secret_backend_required")
    if exchange is None:
        raise ValueError("refresh_exchange_required")

    store = DurableVersionedSecretStore(backend)
    source = VersionedHostCredentialSource(
        binding,
        store,
        exchange,
        attempt_id_factory=attempt_id_factory,
    )
    provider = RefreshingCredentialProvider(binding, source, clock=clock)
    return CredentialBoundToolAdapter(adapter, provider, tuple(requirements))

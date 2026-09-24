from __future__ import annotations

from .adapters import Capability
from .runtime_bridge import BridgeToolAdapter, RuntimeBridge


class ReadOnlySupabaseStatusAdapter(BridgeToolAdapter):
    """Read-only Supabase/status adapter contract for an authorized external host."""

    def __init__(self, bridge: RuntimeBridge) -> None:
        super().__init__(
            name="supabase-readonly-status",
            bridge=bridge,
            capabilities=(
                Capability(
                    action="supabase.project_status",
                    access="read",
                    required_permissions=("supabase:project:read",),
                    supports_dry_run=True,
                    description="Read project health/status without changing configuration.",
                ),
                Capability(
                    action="supabase.function_status",
                    access="read",
                    required_permissions=("supabase:functions:read",),
                    supports_dry_run=True,
                    description="Read deployed function metadata/status without deployment.",
                ),
                Capability(
                    action="supabase.table_count",
                    access="read",
                    required_permissions=("supabase:database:read",),
                    supports_dry_run=True,
                    description="Read a table row count through an authorized read-only query path.",
                ),
            ),
        )


class FileArtifactAdapter(BridgeToolAdapter):
    """Generic file/artifact capability contract with explicit read/write separation."""

    def __init__(self, bridge: RuntimeBridge) -> None:
        super().__init__(
            name="file-artifacts",
            bridge=bridge,
            capabilities=(
                Capability(
                    action="files.read_artifact",
                    access="read",
                    required_permissions=("files:read",),
                    supports_dry_run=True,
                    description="Read an explicitly identified private artifact.",
                ),
                Capability(
                    action="files.verify_artifact",
                    access="read",
                    required_permissions=("files:read",),
                    supports_dry_run=True,
                    description="Verify artifact existence/metadata without modifying it.",
                ),
                Capability(
                    action="files.write_artifact",
                    access="write",
                    required_permissions=("files:write",),
                    supports_dry_run=False,
                    description="Persist a new artifact to an authorized destination.",
                ),
            ),
        )

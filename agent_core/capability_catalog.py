from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .adapters import Capability

CapabilityDomain = Literal[
    "research",
    "text",
    "image",
    "video",
    "code",
    "learning",
    "reporting",
]


@dataclass(frozen=True)
class CapabilityContract:
    domain: CapabilityDomain
    capability: Capability
    requires_external_provider: bool
    default_enabled: bool = False
    notes: str = ""


GENERAL_AGENT_CAPABILITIES: tuple[CapabilityContract, ...] = (
    CapabilityContract(
        domain="research",
        capability=Capability(
            action="research.read_public_sources",
            access="read",
            required_permissions=("research:read",),
            supports_dry_run=True,
            description="Read public sources through a host-authorized provider.",
        ),
        requires_external_provider=True,
        notes="Must not be used as automatic keirin race-data fetching while that feature remains disabled.",
    ),
    CapabilityContract(
        domain="text",
        capability=Capability(
            action="text.generate",
            access="execute",
            required_permissions=("text:generate",),
            supports_dry_run=False,
            description="Generate or transform text through a host-authorized model provider.",
        ),
        requires_external_provider=True,
    ),
    CapabilityContract(
        domain="image",
        capability=Capability(
            action="image.generate",
            access="execute",
            required_permissions=("image:generate",),
            supports_dry_run=False,
            description="Generate or edit images through a host-authorized image provider.",
        ),
        requires_external_provider=True,
    ),
    CapabilityContract(
        domain="video",
        capability=Capability(
            action="video.generate",
            access="execute",
            required_permissions=("video:generate",),
            supports_dry_run=False,
            description="Generate video through a host-authorized video provider.",
        ),
        requires_external_provider=True,
    ),
    CapabilityContract(
        domain="code",
        capability=Capability(
            action="code.generate",
            access="execute",
            required_permissions=("code:generate",),
            supports_dry_run=False,
            description="Generate or transform program text without applying repository writes by itself.",
        ),
        requires_external_provider=True,
    ),
    CapabilityContract(
        domain="learning",
        capability=Capability(
            action="learning.evaluate",
            access="execute",
            required_permissions=("learning:evaluate",),
            supports_dry_run=True,
            description="Run model or task evaluation using explicit inputs and verification criteria.",
        ),
        requires_external_provider=False,
    ),
    CapabilityContract(
        domain="reporting",
        capability=Capability(
            action="report.generate",
            access="execute",
            required_permissions=("report:generate",),
            supports_dry_run=True,
            description="Build a report from already-available task/activity and revenue inputs without delivering it.",
        ),
        requires_external_provider=False,
    ),
)


def capability_catalog() -> tuple[CapabilityContract, ...]:
    """Return the immutable broad-agent capability contract set.

    The catalog declares what the final agent must be able to do. It does not bind a
    provider, grant authorization, enable a scheduler, perform network access, or turn
    on any keirin production/data-fetch feature.
    """

    return GENERAL_AGENT_CAPABILITIES


def capability_by_action(action: str) -> CapabilityContract:
    for contract in GENERAL_AGENT_CAPABILITIES:
        if contract.capability.action == action:
            return contract
    raise KeyError(action)

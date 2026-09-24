from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .adapters import Capability
from .runtime_bridge import RuntimeBridge


class ReportDelivery(Protocol):
    """Delivery boundary for already-rendered reports."""

    def deliver(self, *, report_text: str, metadata: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class DeliveryResult:
    delivered: bool
    destination: str | None = None
    message_id: str | None = None
    detail: str = ""


class BridgeReportDelivery:
    """Send reports only through a host-bound delivery capability.

    Generation and delivery are intentionally separate. The adapter contains no
    destination or credentials; those belong to the authorized runtime binding.
    """

    def __init__(self, *, bridge: RuntimeBridge, action: str = "report.deliver") -> None:
        if not action.strip():
            raise ValueError("delivery_action_required")
        self.bridge = bridge
        self.capability = Capability(
            action=action,
            access="write",
            required_permissions=("report:deliver",),
            supports_dry_run=False,
            description="Deliver a rendered report to a host-configured destination.",
        )

    def deliver(self, *, report_text: str, metadata: dict[str, Any]) -> dict[str, Any]:
        if not report_text.strip():
            raise ValueError("report_text_required")
        response = self.bridge.invoke(
            capability=self.capability,
            args={"report_text": report_text, "metadata": dict(metadata)},
            context={"operation": "report_delivery"},
        )
        if isinstance(response, DeliveryResult):
            return {
                "delivered": response.delivered,
                "destination": response.destination,
                "message_id": response.message_id,
                "detail": response.detail,
            }
        if isinstance(response, dict):
            delivered = response.get("delivered")
            if delivered is not True:
                return {
                    "delivered": False,
                    "destination": response.get("destination"),
                    "message_id": response.get("message_id"),
                    "detail": str(response.get("detail") or response.get("error") or "delivery not confirmed"),
                }
            return {
                "delivered": True,
                "destination": response.get("destination"),
                "message_id": response.get("message_id"),
                "detail": str(response.get("detail") or ""),
            }
        raise TypeError("unsupported_delivery_response")

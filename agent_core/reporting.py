from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal
from zoneinfo import ZoneInfo

RevenueStatus = Literal["known", "unknown", "unavailable"]


@dataclass(frozen=True)
class RevenueMetric:
    status: RevenueStatus
    amount: Decimal | None = None
    currency: str = "JPY"
    source: str | None = None
    note: str | None = None

    def validate(self) -> None:
        if self.status not in {"known", "unknown", "unavailable"}:
            raise ValueError("invalid_revenue_status")
        if self.status == "known":
            if self.amount is None:
                raise ValueError("known_revenue_requires_amount")
            try:
                value = Decimal(self.amount)
            except (InvalidOperation, TypeError) as exc:
                raise ValueError("invalid_revenue_amount") from exc
            if not value.is_finite():
                raise ValueError("invalid_revenue_amount")
            if not (self.source or "").strip():
                raise ValueError("known_revenue_requires_source")
        elif self.amount is not None:
            raise ValueError("unknown_revenue_must_not_have_amount")

    @classmethod
    def known(cls, amount: str | int | Decimal, *, source: str, currency: str = "JPY") -> "RevenueMetric":
        metric = cls(status="known", amount=Decimal(str(amount)), currency=currency, source=source)
        metric.validate()
        return metric

    @classmethod
    def unknown(cls, note: str = "データ未取得", *, currency: str = "JPY") -> "RevenueMetric":
        return cls(status="unknown", amount=None, currency=currency, note=note)

    @classmethod
    def unavailable(cls, note: str, *, currency: str = "JPY") -> "RevenueMetric":
        return cls(status="unavailable", amount=None, currency=currency, note=note)

    def display(self) -> str:
        self.validate()
        if self.status == "known":
            amount = Decimal(self.amount or 0)
            if self.currency == "JPY":
                return f"¥{amount:,.0f}"
            return f"{amount} {self.currency}"
        label = "未取得" if self.status == "unknown" else "利用不可"
        return f"{label}（{self.note}）" if self.note else label


@dataclass(frozen=True)
class DailyActivityReport:
    report_date: date
    timezone: str
    daily_sales: RevenueMetric
    monthly_sales: RevenueMetric
    executed_work: tuple[str, ...]
    achievements: tuple[str, ...]
    failures_or_incomplete: tuple[str, ...]
    next_actions: tuple[str, ...]

    def render_japanese(self) -> str:
        self.daily_sales.validate()
        self.monthly_sales.validate()

        def block(title: str, values: tuple[str, ...]) -> list[str]:
            lines = [title]
            lines.extend(f"- {value}" for value in values) if values else lines.append("- なし")
            return lines

        lines = [
            f"{self.report_date.isoformat()} 21:00 日次報告（{self.timezone}）",
            f"当日の売上: {self.daily_sales.display()}",
            f"当月の売上: {self.monthly_sales.display()}",
            "",
        ]
        lines.extend(block("実行した仕事", self.executed_work))
        lines.append("")
        lines.extend(block("成果", self.achievements))
        lines.append("")
        lines.extend(block("失敗・未完了", self.failures_or_incomplete))
        lines.append("")
        lines.extend(block("次の作業", self.next_actions))
        return "\n".join(lines)


def _event_local_date(event: dict[str, Any], timezone: str) -> date | None:
    raw = event.get("timestamp")
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(ZoneInfo(timezone)).date()
    except (ValueError, TypeError):
        return None


def build_activity_report(
    *,
    report_date: date,
    events: list[dict[str, Any]],
    daily_sales: RevenueMetric,
    monthly_sales: RevenueMetric,
    next_actions: tuple[str, ...] = (),
    timezone: str = "Asia/Tokyo",
) -> DailyActivityReport:
    ZoneInfo(timezone)  # validate timezone name
    daily_sales.validate()
    monthly_sales.validate()
    selected = [event for event in events if _event_local_date(event, timezone) == report_date]

    executed: list[str] = []
    achievements: list[str] = []
    incomplete: list[str] = []
    seen_executed: set[str] = set()

    for event in selected:
        event_type = event.get("event_type")
        task_id = str(event.get("task_id") or "task")
        message = str(event.get("message") or "").strip()
        if event_type == "task_started" and task_id not in seen_executed:
            executed.append(message or task_id)
            seen_executed.add(task_id)
        elif event_type == "task_completed":
            achievements.append(f"{task_id}: {message or '完了'}")
        elif event_type in {"task_blocked", "task_failed"}:
            incomplete.append(f"{task_id}: {message or event_type}")

    return DailyActivityReport(
        report_date=report_date,
        timezone=timezone,
        daily_sales=daily_sales,
        monthly_sales=monthly_sales,
        executed_work=tuple(executed),
        achievements=tuple(achievements),
        failures_or_incomplete=tuple(incomplete),
        next_actions=tuple(next_actions),
    )

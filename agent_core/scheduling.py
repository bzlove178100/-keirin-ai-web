from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class DailySchedule:
    timezone: str
    local_time: time
    enabled: bool = False

    def validate(self) -> None:
        ZoneInfo(self.timezone)

    def is_due(self, now: datetime, *, last_run_date: str | None = None) -> bool:
        self.validate()
        if not self.enabled:
            return False
        if now.tzinfo is None:
            raise ValueError("timezone_aware_now_required")
        local = now.astimezone(ZoneInfo(self.timezone))
        if last_run_date == local.date().isoformat():
            return False
        return local.time().replace(tzinfo=None) >= self.local_time


DAILY_REPORT_2100_JST = DailySchedule(
    timezone="Asia/Tokyo",
    local_time=time(hour=21, minute=0),
    enabled=False,
)

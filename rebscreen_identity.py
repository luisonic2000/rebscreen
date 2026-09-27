"""Visible identity and deterministic header state for Rebscreen."""
from __future__ import annotations

from datetime import datetime


APP_NAME = "Rebscreen"


def header_state(now: datetime | None = None) -> tuple[str, str]:
    now = now or datetime.now()
    months = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
    return now.strftime("%H:%M"), f"{now.day:02d} {months[now.month - 1]}. {now.year}"

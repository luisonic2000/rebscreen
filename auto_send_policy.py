"""Safety rules for the optional USB auto-send loop."""
from __future__ import annotations


MINIMUM_SEND_INTERVAL = 1.0


def initial_auto_send(settings: dict, safe_start: bool = False) -> bool:
    """Restore only an explicitly approved choice; old implicit values stay off."""
    return bool(settings.get("auto_send") and settings.get("auto_send_approved") and not safe_start)


def send_interval(value: float | int | str) -> float:
    """Incremental frames may be scheduled every second after full synchronization."""
    return max(MINIMUM_SEND_INTERVAL, float(value))

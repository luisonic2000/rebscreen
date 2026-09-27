"""Page rotation policy, independent from media refreshes."""
from __future__ import annotations


def next_enabled_page(current: int, enabled: tuple[bool, bool]) -> int:
    available = [index for index, allowed in enumerate(enabled) if allowed]
    if not available:
        return current
    for candidate in available:
        if candidate > current:
            return candidate
    return available[0]


def rotation_due(enabled: bool, last_change: float, now: float, interval: float) -> bool:
    return enabled and now - last_change >= max(1.0, float(interval))

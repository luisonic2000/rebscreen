"""Pure formatting and aggregation for the dual telemetry graph."""
from __future__ import annotations


def rate_label(value: float) -> str:
    if value is None: return "Indisponível"
    value = max(0, float(value))
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if value < 1024 or unit == "GB/s": return f"{value:.0f} {unit}" if unit == "B/s" else f"{value:.1f} {unit}"
        value /= 1024


def aggregate_point(cpu: int, gpu: int, ram: int, temperatures: list[int | None], disk_temperatures: list[int | None] | None = None) -> dict:
    """Keep system and disk thermal averages separate; missing sensors stay missing."""
    available = [value for value in temperatures if isinstance(value, (int, float))]
    disk_available = [value for value in (disk_temperatures or []) if isinstance(value, (int, float))]
    return {
        "usage": round((cpu + gpu + ram) / 3),
        "temperature": round(sum(available) / len(available)) if available else None,
        "disk_temperature": round(sum(disk_available) / len(disk_available)) if disk_available else None,
    }

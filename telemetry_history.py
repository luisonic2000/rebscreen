"""Pure formatting and aggregation for the dual telemetry graph."""
from __future__ import annotations


def rate_label(value: float) -> str:
    if value is None: return "Indisponível"
    value = max(0, float(value))
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if value < 1024 or unit == "GB/s": return f"{value:.0f} {unit}" if unit == "B/s" else f"{value:.1f} {unit}"
        value /= 1024


def aggregate_point(cpu: int, gpu: int, ram: int, temperatures: list[int | None]) -> dict:
    available = [value for value in temperatures if isinstance(value, (int, float))]
    return {"usage": round((cpu + gpu + ram) / 3), "temperature": round(sum(available) / len(available)) if available else None}

"""Normalize storage telemetry without hiding drives with missing sensors."""
from __future__ import annotations


def normalize_disks(items: list[dict]) -> list[dict]:
    """One row per stable drive identity; unavailable readings stay explicit."""
    unique: dict[str, dict] = {}
    for item in items:
        name = str(item.get("name") or item.get("id") or "Unidade sem nome").strip()
        identity = str(item.get("id") or name).casefold()
        current = unique.get(identity)
        candidate = {"id": identity, "name": name,
                     "temperature": item.get("temperature"),
                     "health": item.get("health") or "Sensor de saúde indisponível"}
        if current is None or (current["temperature"] is None and candidate["temperature"] is not None):
            unique[identity] = candidate
    return list(unique.values())


def disk_label(item: dict) -> str:
    temperature = item.get("temperature")
    temp_label = f"{int(temperature)} °C" if isinstance(temperature, (int, float)) else "Temperatura indisponível"
    return f"{temp_label} / {item.get('health') or 'Sensor de saúde indisponível'}"

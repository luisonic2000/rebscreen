"""Internal one-shot adapter for the bundled Rebscreen SensorBridge helper."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def bridge_executable(root: Path | None = None) -> Path | None:
    root = root or Path(__file__).resolve().parent
    candidates = (
        root / "sensor_bridge" / "internal" / "Rebscreen.SensorBridge.exe",
        root / "sensor_bridge" / "publish" / "Rebscreen.SensorBridge.exe",
        root / "sensor_bridge" / "bin" / "Release" / "net8.0" / "Rebscreen.SensorBridge.exe",
    )
    return next((path for path in candidates if path.is_file()), None)


def parse_bridge_payload(payload: str) -> list[dict]:
    raw = json.loads(payload)
    if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("sensors"), list):
        raise ValueError("payload de sensores inválido")
    sensors = []
    for item in raw["sensors"]:
        if not isinstance(item, dict):
            continue
        sensor = {"name": item.get("name"), "type": item.get("type"), "value": item.get("value"), "parent": item.get("parent")}
        kind = item.get("hardware_kind") or item.get("hardwareType")
        if kind is not None:
            sensor["hardware_kind"] = kind
        sensors.append(sensor)
    return sensors


def query_sensor_bridge(runner=subprocess.run, executable: Path | None = None) -> tuple[list[dict], str]:
    executable = executable or bridge_executable()
    if executable is None:
        return [], "SensorBridge interno não empacotado"
    try:
        result = runner([str(executable)], capture_output=True, text=True, timeout=3, check=False)
        if result.returncode:
            return [], "SensorBridge interno indisponível"
        return parse_bridge_payload(result.stdout), "SensorBridge interno (LibreHardwareMonitorLib)"
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return [], "SensorBridge interno indisponível"

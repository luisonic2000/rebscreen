"""Optional Libre Hardware Monitor REST adapter, with legacy WMI fallback."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from urllib.request import urlopen


def disk_rows(sensor_snapshot: list[dict], volumes: list[str]) -> list[dict]:
    """Map LHM sensor snapshots to disks; fall back only to explicit unknown rows."""
    grouped: dict[str, dict] = {}
    for sensor in sensor_snapshot:
        parent = str(sensor.get("parent") or sensor.get("hardware") or "Disco desconhecido")
        row = grouped.setdefault(parent, {"name": parent, "temperature": None, "health": "Indisponível"})
        kind, name, value = str(sensor.get("type", "")).casefold(), str(sensor.get("name", "")).casefold(), sensor.get("value")
        if ("temperature" in kind or "temperature" in name) and isinstance(value, (int, float)):
            row["temperature"] = int(value)
        if "health" in kind or "life" in name or "health" in name:
            row["health"] = str(value) if value not in (None, "") else "Indisponível"
    if grouped:
        return list(grouped.values())
    return [{"name": volume, "temperature": None, "health": "Indisponível"} for volume in volumes]


def query_lhm_wmi() -> tuple[list[dict], str]:
    """Read exposed WMI objects through PowerShell when LHM has WMI enabled."""
    command = "Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Sensor | Select-Object Name,SensorType,Value,Parent | ConvertTo-Json -Compress"
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=3, check=False)
        if result.returncode or not result.stdout.strip(): return [], "Libre Hardware Monitor indisponível"
        raw = json.loads(result.stdout); raw = raw if isinstance(raw, list) else [raw]
        return [{"name": item.get("Name"), "type": item.get("SensorType"), "value": item.get("Value"), "parent": item.get("Parent")} for item in raw], "Libre Hardware Monitor (WMI)"
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return [], "Libre Hardware Monitor indisponível"


def parse_lhm_rest_tree(node: dict, parent: str = "") -> list[dict]:
    """Flatten LHM's data.json tree without assuming every node is a sensor."""
    name = str(node.get("Text") or node.get("Name") or "")
    sensor_type = str(node.get("SensorType") or node.get("Type") or "")
    value = node.get("Value")
    result = []
    if sensor_type or value not in (None, ""):
        numeric = value
        if isinstance(value, str):
            digits = "".join(char for char in value if char.isdigit() or char in ".-")
            try: numeric = float(digits) if digits else value
            except ValueError: numeric = value
        result.append({"name": name, "type": sensor_type, "value": numeric, "parent": parent})
    next_parent = name or parent
    for child in node.get("Children", []) or []:
        result.extend(parse_lhm_rest_tree(child, next_parent))
    return result


def query_lhm_rest(opener=urlopen) -> tuple[list[dict], str]:
    try:
        with opener("http://127.0.0.1:8085/data.json", timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return parse_lhm_rest_tree(payload), "Libre Hardware Monitor (REST local)"
    except Exception:
        return [], ""


def query_lhm() -> tuple[list[dict], str]:
    sensors, status = query_lhm_rest()
    if sensors: return sensors, status
    sensors, status = query_lhm_wmi()
    if sensors: return sensors, status
    if Path(r"C:\LibreHardwareMonitor\LibreHardwareMonitor.exe").exists():
        return [], "Libre Hardware Monitor aberto/instalado; ative Options > Web Server > Run web server (porta 8085)."
    return [], "Libre Hardware Monitor indisponível"

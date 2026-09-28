"""Optional Libre Hardware Monitor REST adapter, with legacy WMI fallback."""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

from sensor_bridge import query_sensor_bridge


def _has_storage_sensor(sensors: list[dict]) -> bool:
    return any("storage" in str(item.get("hardware_kind") or "").casefold() or
               any(token in str(item.get("parent") or "").casefold() for token in ("ssd", "hdd", "nvme", "disk", "wdc ", "xraydisk"))
               for item in sensors)


def disk_rows(sensor_snapshot: list[dict], volumes: list[str]) -> list[dict]:
    """Map only physical-storage sensors; never promote LHM category nodes to disks."""
    grouped: dict[str, dict] = {}
    for sensor in sensor_snapshot:
        hardware_kind = str(sensor.get("hardware_kind") or "").casefold()
        parent = str(sensor.get("parent") or sensor.get("hardware") or "")
        parent_key = parent.casefold()
        is_storage = ("hdd" in hardware_kind or "storage" in hardware_kind or
                      any(token in parent_key for token in ("ssd", "hdd", "nvme", "disk", "wdc ", "seagate", "samsung", "crucial", "xraydisk")))
        if not is_storage:
            continue
        row = grouped.setdefault(parent or "Disco desconhecido", {"name": parent or "Disco desconhecido", "temperature": None, "health": "Indisponível", "_temperatures": []})
        kind, name, value = str(sensor.get("type", "")).casefold(), str(sensor.get("name", "")).casefold(), sensor.get("value")
        if ("temperature" in kind or "temperature" in name) and isinstance(value, (int, float)):
            # Some drives publish more than one temperature. Average those
            # readings for that drive only; never add temperatures together.
            row["_temperatures"].append(float(value))
        if "health" in kind or "life" in name or "health" in name:
            row["health"] = str(value) if value not in (None, "") else "Indisponível"
    if grouped:
        result = []
        for row in grouped.values():
            readings = row.pop("_temperatures")
            row["temperature"] = round(sum(readings) / len(readings)) if readings else None
            result.append(row)
        return result
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


def parse_lhm_rest_tree(node: dict, parent: str = "", hardware_kind: str = "") -> list[dict]:
    """Flatten LHM's data.json tree without assuming every node is a sensor."""
    name = str(node.get("Text") or node.get("Name") or "")
    sensor_type = str(node.get("SensorType") or node.get("Type") or "")
    value = node.get("Value")
    result = []
    if sensor_type:
        numeric = value
        if isinstance(value, str):
            match = re.search(r"[-+]?\d+(?:[.,]\d+)?", value)
            try: numeric = float(match.group(0).replace(",", ".")) if match else value
            except ValueError: numeric = value
        result.append({"name": name, "type": sensor_type, "value": numeric, "parent": parent, "hardware_kind": hardware_kind})
    image = str(node.get("ImageURL") or "")
    is_hardware = bool(node.get("HardwareId"))
    next_parent = name if is_hardware else parent
    next_kind = image if is_hardware else hardware_kind
    for child in node.get("Children", []) or []:
        result.extend(parse_lhm_rest_tree(child, next_parent, next_kind))
    return result


def query_lhm_rest(opener=urlopen) -> tuple[list[dict], str]:
    try:
        with opener("http://127.0.0.1:8085/data.json", timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return parse_lhm_rest_tree(payload), "Libre Hardware Monitor (REST local)"
    except Exception:
        return [], ""


def query_lhm(bridge_query=query_sensor_bridge, rest_query=query_lhm_rest,
              wmi_query=query_lhm_wmi, lhm_installed=None) -> tuple[list[dict], str]:
    """Discover the best available source once.

    Injectable dependencies keep this discovery deterministic in the controlled
    test harness.  Production callers use the local bridge, REST, then legacy
    WMI fallback in that order.
    """
    sensors, status = bridge_query()
    if sensors and _has_storage_sensor(sensors):
        return sensors, status
    bridge_sensors, bridge_status = sensors, status
    sensors, status = rest_query()
    if sensors: return sensors, status
    sensors, status = wmi_query()
    if sensors: return sensors, status
    if bridge_sensors:
        return bridge_sensors, bridge_status
    installed = lhm_installed or (lambda: Path(r"C:\LibreHardwareMonitor\LibreHardwareMonitor.exe").exists())
    if installed():
        return [], "Libre Hardware Monitor aberto/instalado; ative Options > Web Server > Run web server (porta 8085)."
    return [], "Libre Hardware Monitor indisponível"


class LhmSession:
    """Keep one discovery result per Rebscreen run.

    WMI discovery starts PowerShell, so it is intentionally never repeated.
    A source discovered through the local REST server may be polled again,
    because it stays inside the local HTTP connection and runs in Rebscreen's
    existing telemetry worker.
    """

    def __init__(self, discover=query_lhm, rest_query=query_lhm_rest,
                 clock=time.monotonic, rest_interval: float = 5.0):
        self._discover = discover
        self._rest_query = rest_query
        self._clock = clock
        self._rest_interval = rest_interval
        self._discovered = False
        self._uses_rest = False
        self._last_rest_poll = 0.0
        self._sensors: list[dict] = []
        self._status = "Libre Hardware Monitor indisponível"

    def snapshot(self) -> tuple[list[dict], str]:
        now = self._clock()
        if not self._discovered:
            self._sensors, self._status = self._discover()
            self._discovered = True
            self._uses_rest = self._status == "Libre Hardware Monitor (REST local)"
            self._last_rest_poll = now
        elif self._uses_rest and now - self._last_rest_poll >= self._rest_interval:
            sensors, status = self._rest_query()
            self._last_rest_poll = now
            if sensors:
                self._sensors, self._status = sensors, status
            else:
                self._sensors = []
                self._status = "Libre Hardware Monitor (REST local) indisponível"
        return self._sensors, self._status

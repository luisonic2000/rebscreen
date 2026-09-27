"""Windows physical-disk inventory used by the Monitor page.

The inventory is intentionally separate from the optional temperature source:
Windows owns model, drive letters and capacity usage; Libre Hardware Monitor
only augments those records with sensor data.
"""
from __future__ import annotations

import json
import shutil
import subprocess


def _usage_percent(letter: str) -> int | None:
    try:
        usage = shutil.disk_usage(letter + "\\")
        return round((usage.used / usage.total) * 100) if usage.total else None
    except OSError:
        return None


def query_disk_inventory(runner=subprocess.run) -> list[dict]:
    """Return up to six physical disks with their mounted drive letters."""
    if __import__("os").name != "nt":
        return []
    script = """
    Get-CimInstance Win32_DiskDrive | ForEach-Object {
      $drive = $_
      $letters = @(Get-CimAssociatedInstance -InputObject $drive -Association Win32_DiskDriveToDiskPartition |
        ForEach-Object { Get-CimAssociatedInstance -InputObject $_ -Association Win32_LogicalDiskToPartition } |
        ForEach-Object { $_.DeviceID })
      [pscustomobject]@{ index = $drive.Index; name = $drive.Model; units = $letters }
    } | ConvertTo-Json -Compress
    """
    try:
        result = runner(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=5, check=False)
        if result.returncode or not result.stdout.strip():
            return []
        raw = json.loads(result.stdout)
        raw = raw if isinstance(raw, list) else [raw]
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []
    inventory = []
    for item in raw:
        units = [str(unit).rstrip("\\") for unit in item.get("units", []) if isinstance(unit, str) and len(unit) >= 2]
        usages = [value for value in (_usage_percent(unit) for unit in units) if value is not None]
        inventory.append({
            "name": str(item.get("name") or "Disco"),
            "units": units,
            "usage": round(sum(usages) / len(usages)) if usages else None,
        })
    return inventory[:6]

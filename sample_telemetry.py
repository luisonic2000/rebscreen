"""Clearly marked placeholder telemetry used until real CPU/GPU/RAM readers exist."""
from __future__ import annotations

import os
import random
import time

from disk_inventory import query_disk_inventory
from lhm_telemetry import disk_rows, query_lhm
from panel_models import Disk, Metrics


DEMO_COMPONENTS = frozenset({"CPU", "GPU", "RAM"})


def telemetry_source_label(metrics: Metrics) -> str:
    if not metrics.demo_components:
        return "Telemetria: leituras publicadas pelas fontes configuradas."
    components = ", ".join(sorted(metrics.demo_components))
    return f"{components}: demonstração; alertas desses componentes estão desligados."


def demo_screen_notice(metrics: Metrics) -> str:
    """Short enough for the physical 320×480 monitor header."""
    return "DEMO: " + "/".join(sorted(metrics.demo_components)) if metrics.demo_components else ""


class SampleMetricsProvider:
    """Temporary CPU/GPU/RAM samples plus optionally real disk inventory/SMART."""

    def __init__(self):
        self.sensor_status = "Sensores de disco: verificando Libre Hardware Monitor…"
        self._inventory: list[dict] = []
        self._disk_history: dict[str, dict[str, list]] = {}
        self._sensor_snapshot: list[dict] = []
        self._sensor_checked_at = 0.0

    def disks(self) -> list[Disk]:
        if os.name != "nt":
            return [Disk("Armazenamento local", None, "Sensor de saúde indisponível")]
        if not self._inventory:
            self._inventory = query_disk_inventory()
        volumes = [item["name"] for item in self._inventory]
        now = time.monotonic()
        if now - self._sensor_checked_at >= 5.0:
            self._sensor_snapshot, self.sensor_status = query_lhm()
            self._sensor_checked_at = now
        sensor_by_name = {item["name"].casefold(): item for item in disk_rows(self._sensor_snapshot, volumes)}
        disks = []
        for item in self._inventory[:6]:
            sensor = sensor_by_name.get(item["name"].casefold(), {})
            history = self._disk_history.setdefault(item["name"].casefold(), {"usage": [], "temperature": []})
            usage, temperature = item.get("usage"), sensor.get("temperature")
            history["usage"] = (history["usage"] + [usage if usage is not None else 0])[-30:]
            history["temperature"] = (history["temperature"] + [temperature])[-30:]
            disks.append(Disk(item["name"], temperature, sensor.get("health", "Indisponível"), item.get("units", []), usage, history["usage"], history["temperature"]))
        if disks:
            return disks
        return [Disk(item["name"], item["temperature"], item["health"]) for item in disk_rows(self._sensor_snapshot, volumes)[:6]]

    def read(self) -> Metrics:
        return Metrics(
            cpu_usage=random.randint(18, 76), cpu_temperature=random.randint(46, 89),
            gpu_usage=random.randint(8, 92), gpu_temperature=random.randint(42, 84),
            ram_usage=random.randint(42, 78), disks=self.disks(), demo_components=DEMO_COMPONENTS,
        )

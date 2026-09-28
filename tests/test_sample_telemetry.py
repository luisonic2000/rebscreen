from itertools import cycle
from types import SimpleNamespace

from app import Disk, Metrics, PanelApp
from lhm_telemetry import LhmSession
import sample_telemetry
from sample_telemetry import SampleMetricsProvider, demo_screen_notice, telemetry_source_label


def test_sample_provider_marks_cpu_gpu_and_ram_as_demonstration_data(monkeypatch):
    provider = SampleMetricsProvider()
    monkeypatch.setattr(provider, "disks", lambda: [])

    metrics = provider.read()

    assert metrics.demo_components == frozenset({"CPU", "GPU", "RAM"})
    assert "demonstração" in telemetry_source_label(metrics).casefold()
    assert demo_screen_notice(metrics) == "DEMO: CPU/GPU/RAM"


def test_demo_components_never_create_temperature_or_usage_alerts():
    metrics = Metrics(99, 99, 99, 99, 99, [Disk("SSD", 75, "Boa")], frozenset({"CPU", "GPU", "RAM"}))
    panel = SimpleNamespace(
        last_metrics=metrics,
        enabled={"CPU": True, "GPU": True, "Discos": True, "RAM": True},
        limits={"CPU": 85, "GPU": 82, "Discos": 60, "RAM": 90},
        alerts=[], alert_cycle=cycle([""]), current_alert="",
    )

    PanelApp.update_alerts(panel)

    assert panel.alerts == ["ALERTA SSD: 75 °C • limite 60 °C"]


def test_provider_reuses_one_unavailable_lhm_discovery_across_periodic_disk_reads(monkeypatch):
    discoveries = []
    session = LhmSession(discover=lambda: (discoveries.append("WMI") or [], "Libre Hardware Monitor indisponível"))
    monkeypatch.setattr(sample_telemetry.os, "name", "nt")
    monkeypatch.setattr(sample_telemetry, "query_disk_inventory", lambda: [{"name": "NVMe (C:)", "usage": 10, "units": ["C:"]}])

    provider = SampleMetricsProvider(sensor_session=session)
    provider.disks()
    provider.disks()

    assert discoveries == ["WMI"]
    assert provider.sensor_status == "Libre Hardware Monitor indisponível"

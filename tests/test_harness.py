"""Controlled tests for Rebscreen runtime paths; no Windows player or USB device."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from types import SimpleNamespace
import sys
import threading
import time
import types

from PIL import Image

import app


class _Label:
    def __init__(self):
        self.calls = []

    def configure(self, **kwargs):
        self.calls.append(kwargs)


@dataclass
class _FakeSensorProvider:
    snapshots: list[app.Metrics]
    index: int = 0

    def read(self) -> app.Metrics:
        value = self.snapshots[self.index]
        self.index += 1
        return value


class _BlockingMediaProvider:
    def __init__(self, result):
        self.result = result
        self.started = threading.Event()
        self.release = threading.Event()
        self.reason = "controlado"
        self.diagnostics = []

    def read(self):
        self.started.set()
        self.release.wait(timeout=2)
        return self.result


def _bare_media_app(provider):
    """Build a PanelApp-shaped object without starting Tk or a real player."""
    panel = object.__new__(app.PanelApp)
    panel.media_provider = provider
    panel.media_executor = ThreadPoolExecutor(max_workers=1)
    panel.media_future = None
    panel.media_query_started = 0.0
    panel.media_query_timed_out = False
    panel.last_media_key = None
    panel.media_label = "Nenhuma mídia ativa"
    panel.album_art = None
    panel.track = app.Track("Nenhuma mídia ativa", "", 0, 1)
    panel.page = 1
    panel.media_status = _Label()
    panel.media_diagnostics = _Label()
    return panel


def _bare_preview_app(metrics):
    panel = SimpleNamespace(
        theme=app.DARK, accent="#5b8cff", custom_fonts_enabled=False,
        font_scale=1.0, layout_store=SimpleNamespace(data=app.LayoutStore.default),
        monitor_style="cards", visual_theme=app.THEME_REBEL, page=0,
        last_metrics=metrics, track=app.Track("Faixa", "Artista", 10, 180),
        current_alert="", media_label="Spotify", album_art=None,
        telemetry_history=[], rx_rate=0.0, tx_rate=0.0, processes=[],
        preview_orientation="vertical", preview_brightness=100,
    )
    panel.render_live_frame = lambda: app.PanelApp.render_live_frame(panel)
    return panel


def test_slow_media_query_is_queued_without_blocking_the_ui(monkeypatch):
    snapshot = app.MediaSnapshot(app.Track("Faixa", "Artista", 1, 200), "Spotify", True)
    provider = _BlockingMediaProvider(snapshot)
    panel = _bare_media_app(provider)
    monkeypatch.setattr(app, "spotify_window_snapshot", lambda: None)
    monkeypatch.setattr(app, "vlc_window_snapshot", lambda: None)
    try:
        started_at = time.monotonic()
        assert app.PanelApp.poll_media(panel) is False
        assert time.monotonic() - started_at < 0.25
        assert provider.started.wait(timeout=0.5)
        assert panel.media_future is not None and not panel.media_future.done()
    finally:
        provider.release.set()
        panel.media_executor.shutdown(wait=True)


def test_completed_media_query_updates_the_real_player_state(monkeypatch):
    cover = Image.new("RGB", (8, 8), "#4ca6ff")
    snapshot = app.MediaSnapshot(app.Track("Faixa real", "Artista", 10, 200), "Spotify", True, cover)
    provider = _BlockingMediaProvider(snapshot)
    panel = _bare_media_app(provider)
    monkeypatch.setattr(app, "spotify_window_snapshot", lambda: None)
    monkeypatch.setattr(app, "vlc_window_snapshot", lambda: None)
    try:
        app.PanelApp.poll_media(panel)
        assert provider.started.wait(timeout=0.5)
        provider.release.set()
        panel.media_future.result(timeout=0.5)
        assert app.PanelApp.poll_media(panel) is True
        assert panel.track.title == "Faixa real"
        assert panel.media_label == "Spotify"
        assert panel.album_art is cover
        assert panel.page == 1
        assert panel.media_status.calls[-1]["text"].startswith("Mídia: Spotify")
    finally:
        provider.release.set()
        panel.media_executor.shutdown(wait=True)


def test_preview_renders_each_controlled_sensor_snapshot():
    first = app.Metrics(12, 41, 18, 48, 33, [app.Disk("SSD", 36, "Boa")])
    second = app.Metrics(78, 61, 82, 69, 71, [app.Disk("SSD", 44, "Boa")])
    sensors = _FakeSensorProvider([first, second])
    panel = _bare_preview_app(sensors.read())
    initial = app.PanelApp.render_preview_frame(panel)
    panel.last_metrics = sensors.read()
    refreshed = app.PanelApp.render_preview_frame(panel)
    assert initial.size == (320, 480)
    assert refreshed.size == (320, 480)
    assert initial.tobytes() != refreshed.tobytes()


def test_transport_encodes_a_complete_frame_to_a_fake_serial_port(monkeypatch):
    writes = []

    class _Device:
        def write(self, payload):
            writes.append(bytes(payload))

        def flush(self):
            writes.append(b"FLUSH")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    device = _Device()
    serial = types.ModuleType("serial")
    serial.Serial = lambda *args, **kwargs: device
    monkeypatch.setitem(sys.modules, "serial", serial)

    app.TuringScreenTransport("FAKE1").send_pil_image(Image.new("RGB", (320, 480), "#123456"))

    assert writes[0][5:11] == bytes((121, 100, 1, 64, 1, 224))
    assert len(writes[1]) == 6
    assert sum(len(chunk) for chunk in writes[2:-1]) == 320 * 480 * 2
    assert writes[-1] == b"FLUSH"

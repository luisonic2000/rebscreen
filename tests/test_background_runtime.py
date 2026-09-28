from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import threading
import time

import app
from background_runtime import LatestTask


def test_latest_task_returns_immediately_and_never_starts_a_second_slow_job():
    started = threading.Event()
    release = threading.Event()
    calls = []

    def slow_job():
        calls.append("started")
        started.set()
        release.wait(timeout=1)
        return "ready"

    with ThreadPoolExecutor(max_workers=1) as executor:
        task = LatestTask(executor)
        begun_at = time.monotonic()
        assert task.start(slow_job)
        assert time.monotonic() - begun_at < 0.1
        assert started.wait(timeout=0.5)
        assert not task.start(slow_job)
        assert calls == ["started"]
        release.set()
        assert task.future.result(timeout=0.5) == "ready"
        completed = task.take_completed()

    assert completed.result == "ready"
    assert completed.error is None
    assert not task.running


def test_latest_task_surfaces_errors_after_the_worker_finishes():
    with ThreadPoolExecutor(max_workers=1) as executor:
        task = LatestTask(executor)
        assert task.start(lambda: (_ for _ in ()).throw(RuntimeError("offline")))
        task.future.result(timeout=0.5) if False else None
        while task.running:
            time.sleep(0.005)
        completed = task.take_completed()

    assert completed.result is None
    assert isinstance(completed.error, RuntimeError)
    assert str(completed.error) == "offline"


def test_panel_does_not_repeat_a_slow_metrics_request():
    started = threading.Event()
    release = threading.Event()
    calls = []

    def slow_metrics():
        calls.append("metrics")
        started.set()
        release.wait(timeout=1)
        return app.Metrics(1, 1, 1, 1, 1, [])

    with ThreadPoolExecutor(max_workers=3) as executor:
        panel = SimpleNamespace(
            last_metrics_request=0.0,
            metrics_task=LatestTask(executor), process_task=LatestTask(executor), network_task=LatestTask(executor),
            metrics_provider=SimpleNamespace(read=slow_metrics),
            process_sampler=SimpleNamespace(read=lambda: []), network_rates=SimpleNamespace(read=lambda: (0.0, 0.0)),
        )
        begun_at = time.monotonic()
        app.PanelApp._request_background_telemetry(panel, 2.0)
        assert time.monotonic() - begun_at < 0.1
        assert started.wait(timeout=0.5)
        app.PanelApp._request_background_telemetry(panel, 5.0)
        assert calls == ["metrics"]
        release.set()


def test_panel_serial_queue_rejects_an_overlapping_send():
    started = threading.Event()
    release = threading.Event()
    calls = []

    class Label:
        def configure(self, **kwargs):
            self.latest = kwargs

    def slow_send(port):
        calls.append(port)
        started.set()
        release.wait(timeout=1)
        return "sent"

    with ThreadPoolExecutor(max_workers=1) as executor:
        panel = SimpleNamespace(serial_task=LatestTask(executor), hardware_status=Label(), theme=app.DARK)
        assert app.PanelApp._queue_serial_operation(panel, slow_send, "Enviando.", "FAKE1")
        assert started.wait(timeout=0.5)
        assert not app.PanelApp._queue_serial_operation(panel, slow_send, "Enviando.", "FAKE1")
        assert calls == ["FAKE1"]
        release.set()

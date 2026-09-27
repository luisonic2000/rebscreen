from types import SimpleNamespace

import pytest

from process_telemetry import ProcessRow, ProcessSampler


def test_process_row_keeps_network_honestly_unavailable_by_default():
    row = ProcessRow("player.exe", 12.0, 80.0, 4.0)
    assert row.network_kbps is None


def test_process_rows_support_a_real_network_rate_when_a_collector_is_added():
    row = ProcessRow("browser.exe", 8.0, 150.0, 0.0, 42.5)
    assert row.network_kbps == 42.5


def test_process_rows_are_ready_to_represent_grouped_task_manager_entries():
    rows = [ProcessRow("opera.exe", 0.1, 100.0, 0.0), ProcessRow("opera.exe", 0.2, 40.0, 0.0)]
    assert sum(row.memory_mb for row in rows) == 140.0


class _FakeProcess:
    def __init__(self, pid, name, cpu, rss):
        self.info = {"pid": pid, "name": name, "memory_info": SimpleNamespace(rss=rss)}
        self._cpu = cpu

    def cpu_percent(self, _interval):
        return self._cpu

    def io_counters(self):
        return SimpleNamespace(read_bytes=0, write_bytes=0)


class _FakePsutil:
    NoSuchProcess = RuntimeError
    AccessDenied = RuntimeError
    ZombieProcess = RuntimeError

    def cpu_count(self, logical=True):
        return 4

    def virtual_memory(self):
        return SimpleNamespace(total=1000 * 1024 * 1024)

    def process_iter(self, _fields):
        return [
            _FakeProcess(0, "System Idle Process", 400.0, 0),
            _FakeProcess(10, "opera.exe", 20.0, 100 * 1024 * 1024),
            _FakeProcess(11, "Opera.exe", 20.0, 40 * 1024 * 1024),
        ]


def test_sampler_excludes_idle_normalizes_cpu_and_groups_processes():
    rows = ProcessSampler(psutil_module=_FakePsutil(), clock=lambda: 10.0).read()

    assert len(rows) == 1
    assert rows[0].name == "opera.exe"
    assert rows[0].cpu == 10.0
    assert rows[0].memory_mb == 140.0
    assert rows[0].memory_percent == pytest.approx(14.0)
    assert rows[0].total_percent == pytest.approx(8.0)


def test_sampler_ranks_by_average_of_available_percentages():
    rows = ProcessSampler(psutil_module=_FakePsutil(), clock=lambda: 10.0).read()

    assert rows[0].total_percent == pytest.approx(8.0)
    assert rows[0].memory_percent == pytest.approx(14.0)

"""Low-cost process telemetry for the Rebscreen Processes page."""
from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass(frozen=True)
class ProcessRow:
    name: str
    cpu: float
    memory_mb: float
    disk_kbps: float
    network_kbps: float | None = None
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    network_percent: float | None = None
    total_percent: float = 0.0


class ProcessSampler:
    """Caches process objects so CPU and disk rates are deltas, not snapshots."""
    def __init__(self, psutil_module=None, clock=time.monotonic):
        self.psutil = psutil_module
        self.clock = clock
        self._last_io: dict[int, tuple[int, float]] = {}

    def read(self, limit: int = 10) -> list[ProcessRow]:
        if self.psutil is None:
            try:
                import psutil
                self.psutil = psutil
            except ImportError:
                return []
        now = self.clock()
        grouped: dict[str, ProcessRow] = {}
        cores = max(1, int(self.psutil.cpu_count(logical=True) or 1))
        try:
            total_memory = max(1, int(self.psutil.virtual_memory().total))
        except (AttributeError, TypeError):
            total_memory = 0
        for proc in self.psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                pid = int(proc.info["pid"])
                name = str(proc.info.get("name") or f"PID {pid}")
                # The Windows idle pseudo-process is not an application and reports
                # unused CPU time for every core, so it must never enter a top list.
                if pid == 0 or name.casefold() in {"idle", "system idle process", "idle process"}:
                    continue
                memory = proc.info.get("memory_info")
                memory_mb = (float(memory.rss) / 1024 / 1024) if memory else 0.0
                # psutil can exceed 100% for a multi-core process; Task Manager's
                # overall CPU column is normalised to the complete machine.
                cpu = max(0.0, float(proc.cpu_percent(None)) / cores)
                io = proc.io_counters()
                current = int(io.read_bytes + io.write_bytes) if io else 0
                previous, then = self._last_io.get(pid, (current, now))
                disk_kbps = max(0.0, (current - previous) / max(0.01, now - then) / 1024)
                self._last_io[pid] = (current, now)
                key = name.casefold()
                old = grouped.get(key)
                grouped[key] = ProcessRow(
                    old.name if old else name[:22],
                    cpu + (old.cpu if old else 0.0),
                    memory_mb + (old.memory_mb if old else 0.0),
                    disk_kbps + (old.disk_kbps if old else 0.0),
                )
            except (self.psutil.NoSuchProcess, self.psutil.AccessDenied, self.psutil.ZombieProcess):
                continue
        # RAM is a real share of installed memory.  Disk is a share of the
        # sampled process I/O during this interval (Windows only exposes the
        # Task Manager-style active-time percentage through a different API).
        total_disk_kbps = sum(row.disk_kbps for row in grouped.values())
        ranked: list[ProcessRow] = []
        for row in grouped.values():
            memory_percent = row.memory_mb * 1024 * 1024 / total_memory * 100 if total_memory else 0.0
            disk_percent = row.disk_kbps / total_disk_kbps * 100 if total_disk_kbps else 0.0
            available = [row.cpu, memory_percent, disk_percent]
            # Per-process network traffic is deliberately absent until the
            # ETW collector is available. Never turn a missing measure into 0.
            if row.network_percent is not None:
                available.append(row.network_percent)
            ranked.append(ProcessRow(
                row.name, row.cpu, row.memory_mb, row.disk_kbps, row.network_kbps,
                memory_percent, disk_percent, row.network_percent,
                sum(available) / len(available),
            ))
        return sorted(ranked, key=lambda row: (row.total_percent, row.cpu, row.memory_percent), reverse=True)[:limit]

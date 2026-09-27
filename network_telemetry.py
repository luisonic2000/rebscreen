"""Per-interface network rate collector, excluding virtual and loopback NICs."""
from __future__ import annotations
import time

def active_interface(counters: dict, stats: dict) -> str | None:
    blocked = ("loopback", "vethernet", "virtual", "vmware", "hyper-v", "bluetooth")
    eligible = [name for name in counters if name.casefold() and not any(word in name.casefold() for word in blocked) and getattr(stats.get(name), "isup", False)]
    return max(eligible, key=lambda name: counters[name].bytes_recv + counters[name].bytes_sent, default=None)


class NetworkRates:
    def __init__(self): self.last: dict[str, tuple[object, float]] = {}
    def read(self, counters=None, stats=None, now=None) -> tuple[float | None, float | None]:
        try:
            if counters is None or stats is None:
                import psutil
                counters = psutil.net_io_counters(pernic=True) if counters is None else counters
                stats = psutil.net_if_stats() if stats is None else stats
            now = time.monotonic() if now is None else now
            name = active_interface(counters, stats)
            if name is None: return None, None
            current = counters[name]; old = self.last.get(name); self.last[name] = (current, now)
            if old is None: return 0.0, 0.0
            previous, then = old; elapsed=max(.1, now-then)
            return max(0, (current.bytes_recv-previous.bytes_recv)/elapsed), max(0, (current.bytes_sent-previous.bytes_sent)/elapsed)
        except Exception: return None, None

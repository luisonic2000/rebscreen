"""Small, UI-safe coordination primitives for slow Rebscreen work."""
from __future__ import annotations

from concurrent.futures import Executor, Future
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class CompletedTask(Generic[T]):
    """A result is delivered only after a worker completed off the UI thread."""

    result: T | None
    error: BaseException | None


class LatestTask(Generic[T]):
    """Run at most one job and let the UI keep its last known good value.

    Unlike a queue, calls made while a job is pending are ignored. The caller
    consumes the completed value before scheduling a later replacement.
    """

    def __init__(self, executor: Executor) -> None:
        self._executor = executor
        self.future: Future[T] | None = None

    @property
    def running(self) -> bool:
        return self.future is not None and not self.future.done()

    def start(self, operation: Callable[..., T], *args, **kwargs) -> bool:
        """Schedule a job only when no pending or unconsumed result exists."""
        if self.future is not None:
            return False
        self.future = self._executor.submit(operation, *args, **kwargs)
        return True

    def take_completed(self) -> CompletedTask[T] | None:
        """Return a finished result once; never wait for a worker."""
        if self.future is None or not self.future.done():
            return None
        future, self.future = self.future, None
        try:
            return CompletedTask(result=future.result(), error=None)
        except BaseException as exc:
            return CompletedTask(result=None, error=exc)

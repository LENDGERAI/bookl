from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any


TaskFn = Callable[..., Any]


class QueueService:
    """Simple queue abstraction with inline and threadpool modes."""

    def __init__(self, mode: str = "inline", workers: int = 4) -> None:
        self.mode = mode
        self.workers = workers
        self._executor: ThreadPoolExecutor | None = None
        if self.mode == "threadpool":
            self._executor = ThreadPoolExecutor(max_workers=workers)

    def enqueue(self, fn: TaskFn, *args: object, **kwargs: object) -> Future[Any] | None:
        if self.mode == "threadpool" and self._executor:
            return self._executor.submit(fn, *args, **kwargs)
        fn(*args, **kwargs)
        return None

    def shutdown(self) -> None:
        if self._executor:
            self._executor.shutdown(wait=True)


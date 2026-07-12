from __future__ import annotations

from dataclasses import dataclass
from queue import Queue
import threading
import time
from typing import Callable
import uuid

_EXECUTORS: dict[tuple[int, int, float], "LibraryJobExecutor"] = {}
_EXECUTORS_LOCK = threading.Lock()


@dataclass
class _Job:
    deadline: float
    cancelled: Callable[[], bool]
    terminalize: Callable[[str], None]
    done: bool = False
    terminalized: bool = False


class LibraryJobExecutor:
    """Bounded ingest executor with one shared deadline/cancellation watchdog."""

    def __init__(
        self,
        *,
        max_workers: int = 2,
        max_queued: int = 8,
        terminalization_grace_seconds: float = 2.0,
        poll_seconds: float = 0.05,
    ) -> None:
        self.max_workers = max_workers
        self.max_queued = max_queued
        self.terminalization_grace_seconds = terminalization_grace_seconds
        self._capacity = threading.BoundedSemaphore(max_workers + max_queued)
        self._queue: Queue[tuple[str, Callable[[], None]]] = Queue()
        self._jobs: dict[str, _Job] = {}
        self._lock = threading.Lock()
        self._start_lock = threading.Lock()
        self._started = False
        self._poll_seconds = poll_seconds
        self._workers = [
            threading.Thread(
                target=self._run_worker,
                daemon=True,
                name=f"docatlas-library-{index + 1}",
            )
            for index in range(max_workers)
        ]
        self._watchdog = threading.Thread(target=self._watch, daemon=True, name="docatlas-library-watchdog")

    def submit(
        self,
        work: Callable[[], None],
        *,
        deadline_seconds: float,
        cancelled: Callable[[], bool],
        terminalize: Callable[[str], None],
    ) -> bool:
        if not self._capacity.acquire(blocking=False):
            return False
        self._ensure_started()
        token = uuid.uuid4().hex
        with self._lock:
            self._jobs[token] = _Job(
                deadline=time.monotonic() + deadline_seconds,
                cancelled=cancelled,
                terminalize=terminalize,
            )

        self._queue.put_nowait((token, work))
        return True

    def _ensure_started(self) -> None:
        if self._started:
            return
        with self._start_lock:
            if self._started:
                return
            for worker in self._workers:
                worker.start()
            self._watchdog.start()
            self._started = True

    def _run_worker(self) -> None:
        while True:
            token, work = self._queue.get()
            try:
                with self._lock:
                    job = self._jobs.get(token)
                    terminalized = job is None or job.terminalized
                if not terminalized:
                    work()
            finally:
                with self._lock:
                    job = self._jobs.get(token)
                    if job is not None:
                        job.done = True
                self._capacity.release()
                self._queue.task_done()

    def _watch(self) -> None:
        while True:
            callbacks: list[tuple[Callable[[str], None], str]] = []
            now = time.monotonic()
            with self._lock:
                for token, job in list(self._jobs.items()):
                    if job.done:
                        self._jobs.pop(token, None)
                        continue
                    if job.terminalized:
                        continue
                    reason = "cancelled" if job.cancelled() else ("deadline" if now >= job.deadline else None)
                    if reason is not None:
                        job.terminalized = True
                        callbacks.append((job.terminalize, reason))
            for callback, reason in callbacks:
                callback(reason)
            time.sleep(self._poll_seconds)


def shared_library_job_executor(
    *, max_workers: int = 2, max_queued: int = 8, terminalization_grace_seconds: float = 2.0
) -> LibraryJobExecutor:
    key = (max_workers, max_queued, terminalization_grace_seconds)
    with _EXECUTORS_LOCK:
        executor = _EXECUTORS.get(key)
        if executor is None:
            executor = LibraryJobExecutor(
                max_workers=max_workers,
                max_queued=max_queued,
                terminalization_grace_seconds=terminalization_grace_seconds,
            )
            _EXECUTORS[key] = executor
        return executor

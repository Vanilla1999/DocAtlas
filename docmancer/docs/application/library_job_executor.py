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
    on_capacity: Callable[[LibraryJobCapacity], None] | None = None
    done: bool = False
    terminalized: bool = False


@dataclass(frozen=True)
class LibraryJobCapacity:
    running: int
    queued: int
    max_running: int
    max_queued: int
    queue_position: int | None = None


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
        self._queue_order: list[str] = []
        self._running = 0
        self._queued = 0
        self._lock = threading.Lock()
        self._start_lock = threading.Lock()
        self._started = False
        self._poll_seconds = min(poll_seconds, terminalization_grace_seconds)
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
        on_capacity: Callable[[LibraryJobCapacity], None] | None = None,
    ) -> bool:
        if not self.try_reserve():
            return False
        try:
            self.submit_reserved(
                work,
                deadline_seconds=deadline_seconds,
                cancelled=cancelled,
                terminalize=terminalize,
                on_capacity=on_capacity,
            )
        except Exception:
            self.release_reservation()
            raise
        return True

    def try_reserve(self) -> bool:
        return self._capacity.acquire(blocking=False)

    def submit_reserved(
        self,
        work: Callable[[], None],
        *,
        deadline_seconds: float,
        cancelled: Callable[[], bool],
        terminalize: Callable[[str], None],
        on_capacity: Callable[[LibraryJobCapacity], None] | None = None,
    ) -> LibraryJobCapacity:
        self._ensure_started()
        token = uuid.uuid4().hex
        with self._lock:
            self._jobs[token] = _Job(
                deadline=time.monotonic() + deadline_seconds,
                cancelled=cancelled,
                terminalize=terminalize,
                on_capacity=on_capacity,
            )
            self._queued += 1
            self._queue_order.append(token)
            capacity = self._capacity_locked(queue_position=self._queued)

        self._queue.put_nowait((token, work))
        return capacity

    def release_reservation(self) -> None:
        self._capacity.release()

    def capacity(self) -> LibraryJobCapacity:
        with self._lock:
            return self._capacity_locked()

    def _capacity_locked(self, queue_position: int | None = None) -> LibraryJobCapacity:
        return LibraryJobCapacity(
            running=self._running,
            queued=self._queued,
            max_running=self.max_workers,
            max_queued=self.max_queued,
            queue_position=queue_position,
        )

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
                    self._queued -= 1
                    self._running += 1
                    if token in self._queue_order:
                        self._queue_order.remove(token)
                    job = self._jobs.get(token)
                    terminalized = job is None or job.terminalized
                    started_capacity = self._capacity_locked()
                    queued_notifications = [
                        (self._jobs.get(queued_token), self._capacity_locked(queue_position=position))
                        for position, queued_token in enumerate(self._queue_order, start=1)
                    ]
                self._notify_capacity(job, started_capacity)
                for queued_job, queued_capacity in queued_notifications:
                    self._notify_capacity(queued_job, queued_capacity)
                if not terminalized:
                    work()
            finally:
                with self._lock:
                    self._running -= 1
                    job = self._jobs.get(token)
                    if job is not None:
                        job.done = True
                    finished_capacity = self._capacity_locked()
                self._notify_capacity(job, finished_capacity)
                self._capacity.release()
                self._queue.task_done()

    @staticmethod
    def _notify_capacity(job: _Job | None, capacity: LibraryJobCapacity) -> None:
        if job is None or job.on_capacity is None:
            return
        try:
            job.on_capacity(capacity)
        except Exception:
            return

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
                try:
                    callback(reason)
                except Exception:
                    with self._lock:
                        for job in self._jobs.values():
                            if job.terminalize is callback and not job.done:
                                job.terminalized = False
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

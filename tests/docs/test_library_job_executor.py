from __future__ import annotations

from threading import Event
import time

from docmancer.docs.application.library_job_executor import LibraryJobExecutor


def test_executor_enforces_running_and_queued_capacity() -> None:
    release = Event()
    entered = Event()
    executor = LibraryJobExecutor(max_workers=1, max_queued=1, poll_seconds=0.005)

    def work() -> None:
        entered.set()
        release.wait(timeout=1)

    assert executor.submit(work, deadline_seconds=1, cancelled=lambda: False, terminalize=lambda _: None)
    assert entered.wait(timeout=1)
    assert executor.submit(work, deadline_seconds=1, cancelled=lambda: False, terminalize=lambda _: None)
    assert not executor.submit(work, deadline_seconds=1, cancelled=lambda: False, terminalize=lambda _: None)
    release.set()


def test_watchdog_terminalizes_a_worker_that_never_returns() -> None:
    release = Event()
    terminal = Event()
    reasons: list[str] = []
    executor = LibraryJobExecutor(max_workers=1, max_queued=0, poll_seconds=0.005)

    assert executor.submit(
        lambda: release.wait(timeout=1),
        deadline_seconds=0.02,
        cancelled=lambda: False,
        terminalize=lambda reason: (reasons.append(reason), terminal.set()),
    )
    started = time.monotonic()
    assert terminal.wait(timeout=0.2)
    assert time.monotonic() - started < 0.2
    assert reasons == ["deadline"]
    release.set()


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


def test_default_capacity_accepts_two_running_and_eight_queued() -> None:
    release = Event()
    entered = [Event(), Event()]
    executor = LibraryJobExecutor(max_workers=2, max_queued=8, poll_seconds=0.005)

    def work(index: int) -> None:
        if index < 2:
            entered[index].set()
        release.wait(timeout=1)

    accepted = [
        executor.submit(
            lambda index=index: work(index),
            deadline_seconds=1,
            cancelled=lambda: False,
            terminalize=lambda _: None,
        )
        for index in range(10)
    ]

    assert all(accepted)
    assert all(event.wait(timeout=1) for event in entered)
    assert not executor.submit(
        lambda: None,
        deadline_seconds=1,
        cancelled=lambda: False,
        terminalize=lambda _: None,
    )
    assert len(executor._workers) == 2
    assert sum(worker.is_alive() for worker in executor._workers) == 2
    release.set()


def test_watchdog_retries_after_terminal_callback_failure() -> None:
    release = Event()
    terminal = Event()
    attempts = 0
    executor = LibraryJobExecutor(max_workers=1, max_queued=0, poll_seconds=0.005)

    def terminalize(_: str) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary store failure")
        terminal.set()

    assert executor.submit(
        lambda: release.wait(timeout=1),
        deadline_seconds=0.01,
        cancelled=lambda: False,
        terminalize=terminalize,
    )
    assert terminal.wait(timeout=0.2)
    assert attempts >= 2
    release.set()

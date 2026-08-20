from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any


DEFAULT_JOB_WAIT_TIMEOUT_SECONDS = 5.0
DEFAULT_JOB_POLL_INTERVAL_SECONDS = 0.02


def wait_for_docs_job_status(
    service: Any,
    job_id: str,
    expected_statuses: str | Iterable[str],
    *,
    timeout_seconds: float = DEFAULT_JOB_WAIT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_JOB_POLL_INTERVAL_SECONDS,
) -> Any:
    """Wait for one of the expected job states using a monotonic deadline."""
    if isinstance(expected_statuses, str):
        expected = {expected_statuses}
    else:
        expected = {str(status) for status in expected_statuses}
    if not expected:
        raise ValueError("expected_statuses must not be empty")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be positive")

    deadline = time.monotonic() + timeout_seconds
    last_status = None
    while True:
        last_status = service.get_docs_job_status(job_id)
        if last_status is not None and last_status.status in expected:
            return last_status
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            observed = None if last_status is None else last_status.status
            raise AssertionError(
                f"docs job {job_id!r} did not reach {sorted(expected)!r} "
                f"within {timeout_seconds:.2f}s; last_status={observed!r}"
            )
        time.sleep(min(poll_interval_seconds, remaining))

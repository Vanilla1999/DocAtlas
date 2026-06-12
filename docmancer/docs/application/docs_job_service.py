from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
import threading
import uuid

from docmancer.docs.models import DocsJob, DocsJobCancelResult

MAX_DOCS_JOB_HISTORY = 100


class DocsJobTracker:
    def __init__(self, max_history: int = MAX_DOCS_JOB_HISTORY):
        self._jobs: dict[str, DocsJob] = {}
        self._cancel_requested: set[str] = set()
        self._job_order: dict[str, int] = {}
        self._next_order = 0
        self._lock = threading.Lock()
        self.max_history = max_history

    def _trim_locked(self) -> None:
        if len(self._jobs) <= self.max_history:
            return
        ordered = sorted(self._jobs.values(), key=lambda job: (job.updated_at or "", self._job_order.get(job.job_id, 0)), reverse=True)
        keep = {job.job_id for job in ordered[: self.max_history]}
        for job_id in list(self._jobs):
            if job_id not in keep:
                self._jobs.pop(job_id, None)
                self._cancel_requested.discard(job_id)
                self._job_order.pop(job_id, None)

    def create(self, kind: str) -> DocsJob:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        job = DocsJob(
            job_id=uuid.uuid4().hex,
            kind=kind,
            status="pending",
            phase="validating",
            message="Job created.",
            started_at=now,
            updated_at=now,
        )
        with self._lock:
            self._next_order += 1
            self._jobs[job.job_id] = job
            self._job_order[job.job_id] = self._next_order
            self._trim_locked()
        return job

    def update(self, job_id: str, **changes: Any) -> DocsJob | None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if changes.get("status") in {"succeeded", "partial", "failed", "cancelled"} and "finished_at" not in changes:
                changes["finished_at"] = now
            changes["updated_at"] = now
            job = replace(job, **changes)
            self._jobs[job_id] = job
            return job

    def append_warning(self, job_id: str, warning: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            warnings = list(job.warnings)
            warnings.append(warning)
        self.update(job_id, warnings=warnings)

    def append_error(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            errors = list(job.errors)
            errors.append(error)
        self.update(job_id, errors=errors)

    def append_event(self, job_id: str, event: dict[str, Any], max_events: int = 50) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        event = dict(event)
        event.setdefault("at", now)
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            events = [*job.events, event][-max_events:]
        self.update(job_id, events=events, last_event_at=now)

    def get(self, job_id: str) -> DocsJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, status: str | None = None, limit: int | None = None) -> list[DocsJob]:
        with self._lock:
            jobs = list(self._jobs.values())
        if status:
            jobs = [job for job in jobs if job.status == status]
        jobs.sort(key=lambda job: (job.updated_at or "", self._job_order.get(job.job_id, 0)), reverse=True)
        return jobs[:limit] if limit else jobs

    def cancel(self, job_id: str) -> DocsJobCancelResult:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return DocsJobCancelResult(job_id=job_id, status="not_found", message="Job not found.")
            self._cancel_requested.add(job_id)
            if job.status in {"succeeded", "partial", "failed", "cancelled"}:
                status = "cancelled" if job.status == "cancelled" else "cancelling"
                return DocsJobCancelResult(job_id=job_id, status=status, message="Job already finished.")
        self.update(job_id, status="cancelling", message="Cancellation requested.")
        self.append_warning(job_id, "Cancellation requested; job will stop between targets/pages.")
        return DocsJobCancelResult(job_id=job_id, status="cancelling", message="Cancellation requested.")

    def cancellation_requested(self, job_id: str | None) -> bool:
        if job_id is None:
            return False
        with self._lock:
            return job_id in self._cancel_requested


class DocsJobService:
    """Application boundary for docs job lifecycle operations."""

    def __init__(self, tracker: DocsJobTracker | None = None):
        self.tracker = tracker or DocsJobTracker()

    def get_docs_job_status(self, job_id: str) -> DocsJob | None:
        return self.tracker.get(job_id)

    def list_docs_jobs(self, status: str | None = None, limit: int | None = None) -> list[DocsJob]:
        return self.tracker.list(status=status, limit=limit)

    def cancel_docs_job(self, job_id: str) -> DocsJobCancelResult:
        return self.tracker.cancel(job_id)

    def create(self, kind: str) -> DocsJob:
        return self.tracker.create(kind)

    def update(self, job_id: str, **changes: Any) -> DocsJob | None:
        return self.tracker.update(job_id, **changes)

    def append_warning(self, job_id: str, warning: str) -> None:
        self.tracker.append_warning(job_id, warning)

    def append_error(self, job_id: str, error: str) -> None:
        self.tracker.append_error(job_id, error)

    def append_event(self, job_id: str, event: dict[str, Any], max_events: int = 50) -> None:
        self.tracker.append_event(job_id, event, max_events=max_events)

    def get(self, job_id: str) -> DocsJob | None:
        return self.tracker.get(job_id)

    def list(self, status: str | None = None, limit: int | None = None) -> list[DocsJob]:
        return self.tracker.list(status=status, limit=limit)

    def cancel(self, job_id: str) -> DocsJobCancelResult:
        return self.tracker.cancel(job_id)

    def cancellation_requested(self, job_id: str | None) -> bool:
        return self.tracker.cancellation_requested(job_id)


DOCS_JOB_TRACKER = DocsJobTracker()
DOCS_JOB_SERVICE = DocsJobService(DOCS_JOB_TRACKER)

from __future__ import annotations

from dataclasses import asdict, fields, replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Callable
import threading
import uuid

from docmancer.docs.models import DocsJob, DocsJobCancelResult
from docmancer.docs.fetch_policy import redact_url

MAX_DOCS_JOB_HISTORY = 1000
TERMINAL_DOCS_JOB_STATUSES = {"succeeded", "partial", "failed", "cancelled", "interrupted"}
_DOCS_JOB_SCHEMA_VERSION = 1
_DOCS_JOB_FIELD_NAMES = {item.name for item in fields(DocsJob)}
_PROCESS_LEASE_ID = uuid.uuid4().hex


def _safe_event_value(value: Any, key: str = "") -> Any:
    if isinstance(value, str):
        safe = redact_url(value) if "url" in key.lower() and "://" in value else value
        return safe[:1000]
    if isinstance(value, dict):
        return {str(item_key)[:100]: _safe_event_value(item_value, str(item_key)) for item_key, item_value in list(value.items())[:30]}
    if isinstance(value, list):
        return [_safe_event_value(item, key) for item in value[:30]]
    return value


def _safe_text(value: str) -> str:
    return re.sub(r"https?://[^\s]+", lambda match: redact_url(match.group(0)), value)[:1000]


def _safe_changes(changes: dict[str, Any]) -> dict[str, Any]:
    safe = dict(changes)
    for field_name in ("current_url", "failed_url"):
        value = safe.get(field_name)
        if isinstance(value, str):
            safe[field_name] = redact_url(value)
    for field_name in ("message", "error_context", "current_target"):
        value = safe.get(field_name)
        if isinstance(value, str):
            safe[field_name] = _safe_text(value)
    for field_name in ("warnings", "errors"):
        values = safe.get(field_name)
        if isinstance(values, list):
            safe[field_name] = [_safe_text(str(value)) for value in values[-50:]]
    events = safe.get("events")
    if isinstance(events, list):
        safe["events"] = [_safe_event_value(event) for event in events[-50:]]
    target_results = safe.get("target_results")
    if isinstance(target_results, list):
        safe["target_results"] = [_safe_event_value(result) for result in target_results[-200:]]
    return safe


class SQLiteDocsJobStore:
    """Versioned durable store for the observable Docs job state."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(Path(db_path).expanduser())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _migrate(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS docs_job_schema (singleton INTEGER PRIMARY KEY CHECK(singleton = 1), version INTEGER NOT NULL)"
            )
            version_row = connection.execute(
                "SELECT version FROM docs_job_schema WHERE singleton = 1"
            ).fetchone()
            if version_row is not None and int(version_row["version"]) > _DOCS_JOB_SCHEMA_VERSION:
                raise RuntimeError(f"Unsupported docs job schema version: {version_row['version']}")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS docs_jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finished_at TEXT,
                    generation_id TEXT NOT NULL,
                    predecessor_job_id TEXT,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_docs_jobs_status_updated ON docs_jobs(status, updated_at DESC)"
            )
            connection.execute(
                "INSERT INTO docs_job_schema(singleton, version) VALUES (1, ?) ON CONFLICT(singleton) DO UPDATE SET version=excluded.version",
                (_DOCS_JOB_SCHEMA_VERSION,),
            )

    def save(self, job: DocsJob) -> None:
        with self._connect() as connection:
            self._save(connection, job)

    @staticmethod
    def _save(connection: sqlite3.Connection, job: DocsJob) -> None:
        payload = json.dumps(asdict(job), ensure_ascii=True, separators=(",", ":"))
        connection.execute(
            """
                INSERT INTO docs_jobs(job_id, status, updated_at, finished_at, generation_id, predecessor_job_id, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    finished_at=excluded.finished_at,
                    generation_id=excluded.generation_id,
                    predecessor_job_id=excluded.predecessor_job_id,
                    payload_json=excluded.payload_json
            """,
            (
                job.job_id,
                job.status,
                job.updated_at or "",
                job.finished_at,
                job.generation_id or "",
                job.predecessor_job_id,
                payload,
            ),
        )

    def update(self, job_id: str, *, expected_lease_id: str, now: str, changes: dict[str, Any]) -> DocsJob | None:
        changes = _safe_changes(changes)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT payload_json FROM docs_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                return None
            job = self._decode(row["payload_json"])
            if job.lease_id != expected_lease_id:
                return None
            if changes.get("status") in TERMINAL_DOCS_JOB_STATUSES and "finished_at" not in changes:
                changes["finished_at"] = now
            if changes.get("status") == "running" and job.started_at is None and "started_at" not in changes:
                changes["started_at"] = now
            updated = replace(job, updated_at=now, **changes)
            self._save(connection, updated)
            return updated

    def append(
        self,
        job_id: str,
        *,
        expected_lease_id: str,
        field_name: str,
        value: Any,
        max_items: int,
        now: str,
    ) -> DocsJob | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT payload_json FROM docs_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                return None
            job = self._decode(row["payload_json"])
            if job.lease_id != expected_lease_id:
                return None
            values = [*getattr(job, field_name), value][-max_items:]
            changes: dict[str, Any] = {field_name: values, "updated_at": now}
            if field_name == "events":
                changes["last_event_at"] = now
            updated = replace(job, **changes)
            self._save(connection, updated)
            return updated

    @staticmethod
    def _decode(payload: str) -> DocsJob:
        values = json.loads(payload)
        return DocsJob(**{key: value for key, value in values.items() if key in _DOCS_JOB_FIELD_NAMES})

    def get(self, job_id: str) -> DocsJob | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload_json FROM docs_jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._decode(row["payload_json"]) if row else None

    def list(self, status: str | None = None, limit: int | None = None) -> list[DocsJob]:
        sql = "SELECT payload_json FROM docs_jobs"
        args: list[Any] = []
        if status:
            sql += " WHERE status = ?"
            args.append(status)
        sql += " ORDER BY updated_at DESC, rowid DESC"
        if limit is not None:
            sql += " LIMIT ?"
            args.append(limit)
        with self._connect() as connection:
            rows = connection.execute(sql, args).fetchall()
        return [self._decode(row["payload_json"]) for row in rows]

    def interrupt_active(self, now: str, current_lease_id: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("SELECT payload_json FROM docs_jobs").fetchall()
            for row in rows:
                job = self._decode(row["payload_json"])
                if job.status not in TERMINAL_DOCS_JOB_STATUSES and job.lease_id != current_lease_id:
                    self._save(
                        connection,
                        replace(
                        job,
                        lease_id=current_lease_id,
                        status="interrupted",
                        phase="done",
                        reason_code="job_interrupted",
                        retryable=True,
                        message="Job was interrupted by process restart.",
                        updated_at=now,
                        finished_at=now,
                        ),
                    )

    def prune(self, *, now: datetime, max_terminal_jobs: int, retention_days: int) -> None:
        cutoff = (now - timedelta(days=retention_days)).isoformat(timespec="seconds")
        terminal = tuple(sorted(TERMINAL_DOCS_JOB_STATUSES))
        placeholders = ",".join("?" for _ in terminal)
        with self._connect() as connection:
            connection.execute(
                f"DELETE FROM docs_jobs WHERE status IN ({placeholders}) AND finished_at IS NOT NULL AND finished_at < ?",
                (*terminal, cutoff),
            )
            rows = connection.execute(
                f"SELECT job_id FROM docs_jobs WHERE status IN ({placeholders}) ORDER BY updated_at DESC, rowid DESC",
                terminal,
            ).fetchall()
            stale_ids = [row["job_id"] for row in rows[max_terminal_jobs:]]
            if stale_ids:
                connection.executemany("DELETE FROM docs_jobs WHERE job_id = ?", ((job_id,) for job_id in stale_ids))


class DocsJobTracker:
    def __init__(
        self,
        max_history: int = MAX_DOCS_JOB_HISTORY,
        db_path: str | Path | None = None,
        retention_days: int = 30,
        max_events: int = 50,
        now: Callable[[], datetime] | None = None,
        lease_id: str = _PROCESS_LEASE_ID,
    ):
        self._jobs: dict[str, DocsJob] = {}
        self._cancel_requested: set[str] = set()
        self._job_order: dict[str, int] = {}
        self._next_order = 0
        self._lock = threading.Lock()
        self.max_history = max_history
        self.retention_days = retention_days
        self.max_events = max_events
        self._clock = now or (lambda: datetime.now(timezone.utc))
        self.lease_id = lease_id
        self._store = SQLiteDocsJobStore(db_path) if db_path is not None else None
        if self._store is not None:
            self._store.interrupt_active(self._now(), self.lease_id)
            self._store.prune(now=self._clock(), max_terminal_jobs=self.max_history, retention_days=self.retention_days)

    def _now(self) -> str:
        return self._clock().isoformat(timespec="seconds")

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

    def create(
        self,
        kind: str,
        *,
        request_identity: str | None = None,
        predecessor_job_id: str | None = None,
        with_generation: bool = True,
    ) -> DocsJob:
        now = self._now()
        request_identity = _safe_text(request_identity) if request_identity else None
        if predecessor_job_id is None and request_identity and self._store is not None:
            predecessor_job_id = next(
                (
                    item.job_id
                    for item in self._store.list()
                    if item.request_identity == request_identity
                    and item.kind == kind
                    and item.status == "interrupted"
                ),
                None,
            )
        job = DocsJob(
            job_id=uuid.uuid4().hex,
            kind=kind,
            generation_id=uuid.uuid4().hex if with_generation else None,
            lease_id=self.lease_id,
            predecessor_job_id=predecessor_job_id,
            request_identity=request_identity,
            status="pending",
            phase="validating",
            message="Job created.",
            queued_at=now,
            updated_at=now,
        )
        with self._lock:
            self._next_order += 1
            self._jobs[job.job_id] = job
            self._job_order[job.job_id] = self._next_order
            self._trim_locked()
            if self._store is not None:
                self._store.save(job)
                self._store.prune(
                    now=self._clock(), max_terminal_jobs=self.max_history, retention_days=self.retention_days
                )
        return job

    def update(self, job_id: str, **changes: Any) -> DocsJob | None:
        now = self._now()
        with self._lock:
            if self._store is not None:
                job = self._store.update(
                    job_id,
                    expected_lease_id=self.lease_id,
                    now=now,
                    changes=changes,
                )
                if job is not None:
                    self._jobs[job_id] = job
                    self._store.prune(
                        now=self._clock(), max_terminal_jobs=self.max_history, retention_days=self.retention_days
                    )
                return job
            job = self._store.get(job_id) if self._store is not None else self._jobs.get(job_id)
            if job is None:
                return None
            if changes.get("status") in TERMINAL_DOCS_JOB_STATUSES and "finished_at" not in changes:
                changes["finished_at"] = now
            if changes.get("status") == "running" and job.started_at is None and "started_at" not in changes:
                changes["started_at"] = now
            changes["updated_at"] = now
            job = replace(job, **changes)
            self._jobs[job_id] = job
            return job

    def append_warning(self, job_id: str, warning: str) -> None:
        warning = _safe_text(warning)
        if self._store is not None:
            with self._lock:
                self._store.append(
                    job_id,
                    expected_lease_id=self.lease_id,
                    field_name="warnings",
                    value=warning,
                    max_items=50,
                    now=self._now(),
                )
            return
        with self._lock:
            job = self._store.get(job_id) if self._store is not None else self._jobs.get(job_id)
            if job is None:
                return
            warnings = list(job.warnings)
            warnings.append(warning)
        self.update(job_id, warnings=warnings)

    def append_error(self, job_id: str, error: str) -> None:
        error = _safe_text(error)
        if self._store is not None:
            with self._lock:
                self._store.append(
                    job_id,
                    expected_lease_id=self.lease_id,
                    field_name="errors",
                    value=error,
                    max_items=50,
                    now=self._now(),
                )
            return
        with self._lock:
            job = self._store.get(job_id) if self._store is not None else self._jobs.get(job_id)
            if job is None:
                return
            errors = list(job.errors)
            errors.append(error)
        self.update(job_id, errors=errors)

    def append_event(self, job_id: str, event: dict[str, Any], max_events: int | None = None) -> None:
        now = self._now()
        max_events = max_events or self.max_events
        event = _safe_event_value(event)
        event.setdefault("at", now)
        if self._store is not None:
            with self._lock:
                self._store.append(
                    job_id,
                    expected_lease_id=self.lease_id,
                    field_name="events",
                    value=event,
                    max_items=max_events,
                    now=now,
                )
            return
        with self._lock:
            job = self._store.get(job_id) if self._store is not None else self._jobs.get(job_id)
            if job is None:
                return
            events = [*job.events, event][-max_events:]
        self.update(job_id, events=events, last_event_at=now)

    def get(self, job_id: str) -> DocsJob | None:
        with self._lock:
            if self._store is not None:
                return self._store.get(job_id)
            return self._jobs.get(job_id)

    def list(self, status: str | None = None, limit: int | None = None) -> list[DocsJob]:
        if self._store is not None:
            return self._store.list(status=status, limit=limit)
        with self._lock:
            jobs = list(self._jobs.values())
        if status:
            jobs = [job for job in jobs if job.status == status]
        jobs.sort(key=lambda job: (job.updated_at or "", self._job_order.get(job.job_id, 0)), reverse=True)
        return jobs[:limit] if limit else jobs

    def cancel(self, job_id: str) -> DocsJobCancelResult:
        with self._lock:
            job = self._store.get(job_id) if self._store is not None else self._jobs.get(job_id)
            if job is None:
                return DocsJobCancelResult(job_id=job_id, status="not_found", message="Job not found.")
            if job.phase == "committing" and job.kind != "prefetch_library_docs":
                return DocsJobCancelResult(
                    job_id=job_id,
                    status=job.status,
                    message="Job is committing and can no longer be cancelled safely.",
                )
            self._cancel_requested.add(job_id)
            if job.status in TERMINAL_DOCS_JOB_STATUSES:
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

    def generation_active(self, job_id: str, generation_id: str | None) -> bool:
        job = self.get(job_id)
        return bool(
            generation_id
            and job
            and job.generation_id == generation_id
            and job.status not in TERMINAL_DOCS_JOB_STATUSES
        )


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

    def create(self, kind: str, **metadata: Any) -> DocsJob:
        return self.tracker.create(kind, **metadata)

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

    def generation_active(self, job_id: str, generation_id: str | None) -> bool:
        return self.tracker.generation_active(job_id, generation_id)


DOCS_JOB_TRACKER = DocsJobTracker()
DOCS_JOB_SERVICE = DocsJobService(DOCS_JOB_TRACKER)

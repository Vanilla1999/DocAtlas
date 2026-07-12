from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import sqlite3
import time

from docmancer.docs.application.docs_job_service import DocsJobService, DocsJobTracker
from docmancer.docs.service import LibraryDocsService


def test_docs_job_service_create_status_and_cancel_shapes():
    service = DocsJobService(DocsJobTracker())

    job = service.create("prefetch_docs_targets")
    service.update(job.job_id, status="running")

    status = service.get_docs_job_status(job.job_id)
    cancel = service.cancel_docs_job(job.job_id)

    assert status is not None
    assert status.job_id == job.job_id
    assert status.kind == "prefetch_docs_targets"
    assert status.status == "running"
    assert asdict(cancel) == {
        "job_id": job.job_id,
        "status": "cancelling",
        "message": "Cancellation requested.",
    }
    assert service.cancellation_requested(job.job_id) is True


def test_docs_job_service_lists_jobs_by_status_newest_first_with_limit():
    service = DocsJobService(DocsJobTracker())
    first = service.create("prefetch_docs_targets")
    service.update(first.job_id, status="running")
    time.sleep(0.01)
    second = service.create("prefetch_docs_manifest")
    service.update(second.job_id, status="running")
    third = service.create("prefetch_project_docs")
    service.update(third.job_id, status="failed")

    running = service.list_docs_jobs(status="running", limit=1)

    assert [job.job_id for job in running] == [second.job_id]


def test_docs_job_service_missing_job_result_shape():
    service = DocsJobService(DocsJobTracker())

    assert service.get_docs_job_status("missing") is None
    assert asdict(service.cancel_docs_job("missing")) == {
        "job_id": "missing",
        "status": "not_found",
        "message": "Job not found.",
    }


def test_docs_job_cannot_be_cancelled_after_atomic_commit_phase_starts():
    service = DocsJobService(DocsJobTracker())
    job = service.create("prefetch_library_docs")
    service.update(job.job_id, status="running", phase="committing")

    result = service.cancel(job.job_id)

    assert result.status == "running"
    assert "committing" in result.message
    assert service.cancellation_requested(job.job_id) is False


def test_docs_job_service_event_history_is_capped():
    service = DocsJobService(DocsJobTracker())
    job = service.create("prefetch_docs_targets")

    for index in range(60):
        service.append_event(job.job_id, {"phase": "fetching", "message": f"event {index}"})

    status = service.get_docs_job_status(job.job_id)

    assert status is not None
    assert len(status.events) == 50
    assert status.events[0]["message"] == "event 10"


def test_library_docs_service_delegates_job_methods_to_docs_job_service():
    jobs = DocsJobService(DocsJobTracker())
    service = LibraryDocsService(job_tracker=jobs.tracker)
    job = service.jobs.create("prefetch_docs_targets")

    assert service.get_docs_job_status(job.job_id) == jobs.get_docs_job_status(job.job_id)
    assert service.list_docs_jobs() == jobs.list_docs_jobs()
    assert service.cancel_docs_job(job.job_id) == jobs.cancel_docs_job(job.job_id)


def test_sqlite_job_tracker_persists_terminal_status_and_counters_across_restart(tmp_path):
    db_path = tmp_path / "jobs.db"
    first = DocsJobTracker(db_path=db_path)
    job = first.create("prefetch_docs_targets", request_identity="https://example.com/docs")
    first.update(
        job.job_id,
        status="succeeded",
        phase="done",
        completed_targets=2,
        completed_pages=7,
        completed_chunks=11,
    )

    recovered = DocsJobTracker(db_path=db_path).get(job.job_id)

    assert recovered is not None
    assert recovered.status == "succeeded"
    assert recovered.completed_targets == 2
    assert recovered.completed_pages == 7
    assert recovered.completed_chunks == 11
    assert recovered.request_identity == "https://example.com/docs"
    assert recovered.generation_id


def test_sqlite_job_tracker_marks_nonterminal_jobs_interrupted_on_restart(tmp_path):
    db_path = tmp_path / "jobs.db"
    first = DocsJobTracker(db_path=db_path, lease_id="process-1")
    jobs = [first.create(f"job-{status}") for status in ("pending", "running", "cancelling")]
    first.update(jobs[1].job_id, status="running", phase="fetching")
    first.update(jobs[2].job_id, status="cancelling", phase="fetching")

    restarted = DocsJobTracker(db_path=db_path, lease_id="process-2")

    for job in jobs:
        recovered = restarted.get(job.job_id)
        assert recovered is not None
        assert recovered.status == "interrupted"
        assert recovered.phase == "done"
        assert recovered.reason_code == "job_interrupted"
        assert recovered.retryable is True
        assert recovered.finished_at is not None

    assert first.update(jobs[1].job_id, status="succeeded") is None
    still_interrupted = restarted.get(jobs[1].job_id)
    assert still_interrupted is not None
    assert still_interrupted.status == "interrupted"


def test_sqlite_job_migration_is_idempotent_for_existing_database(tmp_path):
    db_path = tmp_path / "jobs.db"
    sqlite3.connect(db_path).close()

    DocsJobTracker(db_path=db_path)
    DocsJobTracker(db_path=db_path)

    with sqlite3.connect(db_path) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'docs_jobs'"
        ).fetchall()
    assert tables == [("docs_jobs",)]


def test_sqlite_job_retention_prunes_oldest_terminal_jobs_but_keeps_active(tmp_path):
    current = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def now():
        return current

    tracker = DocsJobTracker(db_path=tmp_path / "jobs.db", max_history=2, retention_days=30, now=now)
    active = tracker.create("active")
    terminal_ids = []
    for index in range(3):
        current += timedelta(seconds=1)
        job = tracker.create(f"terminal-{index}")
        tracker.update(job.job_id, status="succeeded", phase="done")
        terminal_ids.append(job.job_id)

    retained = {job.job_id for job in tracker.list()}

    assert active.job_id in retained
    assert terminal_ids[0] not in retained
    assert set(terminal_ids[1:]) <= retained


def test_retry_after_restart_links_interrupted_predecessor_with_new_generation(tmp_path):
    db_path = tmp_path / "jobs.db"
    first = DocsJobTracker(db_path=db_path, lease_id="process-1")
    interrupted = first.create("prefetch_docs_targets", request_identity="https://example.com/docs")
    first.update(interrupted.job_id, status="running")

    restarted = DocsJobTracker(db_path=db_path, lease_id="process-2")
    retry = restarted.create("prefetch_docs_targets", request_identity="https://example.com/docs")

    assert retry.predecessor_job_id == interrupted.job_id
    assert retry.generation_id != interrupted.generation_id
    assert restarted.generation_active(interrupted.job_id, interrupted.generation_id) is False
    assert restarted.generation_active(retry.job_id, retry.generation_id) is True


def test_persisted_job_events_are_bounded_and_redact_url_credentials(tmp_path):
    tracker = DocsJobTracker(db_path=tmp_path / "jobs.db")
    job = tracker.create("prefetch_docs_targets")

    tracker.append_event(
        job.job_id,
        {
            "phase": "fetching",
            "url": "https://user:pass@example.com/docs?token=secret&ok=1",
            "message": "x" * 5000,
        },
    )

    recovered = DocsJobTracker(db_path=tmp_path / "jobs.db").get(job.job_id)
    assert recovered is not None
    assert recovered.events[0]["url"] == "https://example.com/docs"
    assert len(recovered.events[0]["message"]) == 1000
    assert "pass" not in str(recovered.events)
    assert "secret" not in str(recovered.events)

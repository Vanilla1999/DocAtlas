from __future__ import annotations

from dataclasses import asdict
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

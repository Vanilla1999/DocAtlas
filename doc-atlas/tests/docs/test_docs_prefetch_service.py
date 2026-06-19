from __future__ import annotations

from docmancer.docs.application.docs_prefetch_service import DocsPrefetchService


class FakeJobs:
    def __init__(self):
        self.calls = []
        self.job = type("Job", (), {"job_id": "job-1", "total_pages": 0, "failed_pages": 0, "total_chunks": 0})()

    def create(self, kind):
        self.calls.append(("create", kind))
        return self.job

    def update(self, job_id, **changes):
        self.calls.append(("update", job_id, changes))
        for key, value in changes.items():
            setattr(self.job, key, value)

    def get(self, job_id):
        return self.job

    def append_event(self, job_id, event, max_events=50):
        self.calls.append(("event", job_id, event, max_events))

    def append_error(self, job_id, error):
        self.calls.append(("error", job_id, error))

    def append_warning(self, job_id, warning):
        self.calls.append(("warning", job_id, warning))

    def cancellation_requested(self, job_id):
        return False


class FakePrefetchDeps:
    def __init__(self):
        self.jobs = FakeJobs()
        self.registry = None


def test_prefetch_service_starts_async_job_with_explicit_jobs_dependency():
    deps = FakePrefetchDeps()

    result = DocsPrefetchService(deps).prefetch_docs_targets([{"library": "x"}], force_refresh=True, continue_on_error=False, async_=True)

    assert result.job_id == "job-1"
    assert result.status == "running"
    assert deps.jobs.calls[:2] == [
        ("create", "prefetch_docs_targets"),
        ("update", "job-1", {"status": "running", "message": "Started docs prefetch job."}),
    ]


def test_prefetch_service_progress_callback_updates_job_state():
    deps = FakePrefetchDeps()
    service = DocsPrefetchService(deps)

    callback = service.progress_callback_for("job-1", "canonical")
    callback({"phase": "fetching", "url": "https://example.com", "total_pages": 2, "fetched_pages": 1})

    assert deps.jobs.job.current_target == "canonical"
    assert deps.jobs.job.current_url == "https://example.com"
    assert deps.jobs.job.total_pages == 2
    assert deps.jobs.job.fetched_pages == 1
    assert deps.jobs.job.completed_pages == 1
    assert deps.jobs.calls[-1][0] == "event"

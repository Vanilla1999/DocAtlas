from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from docmancer.docs.application.library_ingest_orchestrator import LibraryIngestOrchestrator
from docmancer.docs.application.library_ingest_ports import LibraryIngestPorts
from docmancer.docs.application.library_docs_service import LibraryDocsApplicationService
from docmancer.docs.models import RefreshResult


class FakeLibraryFacade:
    def __init__(self):
        self.calls = []

    def _library_resolve_library_impl(self, *args):
        self.calls.append(("resolve", args))
        return "resolved"

    def _library_get_docs_impl(self, *args, **kwargs):
        self.calls.append(("get", args, kwargs))
        return "docs"

    def _library_prune_library_docs_impl(self, **kwargs):
        self.calls.append(("prune", kwargs))
        return "pruned"


def test_library_application_service_delegates_resolve_library():
    facade = FakeLibraryFacade()
    service = LibraryDocsApplicationService(facade)

    assert service.resolve_library("pytest", ecosystem="python", version="8") == "resolved"
    assert facade.calls == [("resolve", ("pytest", "python", "8", None, None, None))]


def test_library_application_service_delegates_get_docs_with_arguments():
    facade = FakeLibraryFacade()
    service = LibraryDocsApplicationService(facade)

    assert service.get_docs("pytest", topic="fixtures", tokens=100, force_refresh=True) == "docs"
    name, args, kwargs = facade.calls[0]
    assert name == "get"
    assert args == ("pytest",)
    assert kwargs["topic"] == "fixtures"
    assert kwargs["tokens"] == 100
    assert kwargs["force_refresh"] is True


def test_library_application_service_delegates_prune_options():
    facade = FakeLibraryFacade()
    service = LibraryDocsApplicationService(facade)

    assert service.prune_library_docs(library="go_router", keep_versions=["1"], older_than_days=30, dry_run=False) == "pruned"
    assert facade.calls == [("prune", {"library": "go_router", "keep_versions": ["1"], "older_than_days": 30, "dry_run": False})]


def test_ingest_orchestrator_uses_injected_refresh_port_for_sync_requests():
    calls = []

    def prefetch(library, **kwargs):
        calls.append((library, kwargs))
        return RefreshResult(
            library_id="pytest",
            status="updated",
            docs_url=None,
            last_refreshed_at=None,
        )

    orchestrator = LibraryIngestOrchestrator(
        LibraryIngestPorts(
            jobs=object(),
            prefetch=prefetch,
            timeout_seconds=lambda: 1.0,
            executor=lambda: None,
        )
    )

    result = orchestrator.prefetch_docs("pytest", versions=["8"], force_refresh=True)

    assert result.status == "updated"
    assert calls == [("pytest", {
        "ecosystem": None,
        "versions": ["8"],
        "docs_url": None,
        "docs_url_template": None,
        "source_type": None,
        "force_refresh": True,
        "continue_on_error": True,
    })]


def test_ingest_orchestrator_uses_injected_clock_executor_and_job_store():
    class Jobs:
        def __init__(self):
            self.job = SimpleNamespace(job_id="job-1", generation_id="generation-1", status="pending")
            self.updates = []

        def create(self, *_args, **_kwargs):
            return self.job

        def get(self, _job_id):
            return self.job

        def update(self, _job_id, **values):
            self.updates.append(values)
            self.job.status = values.get("status", self.job.status)

        def append_error(self, *_args):
            raise AssertionError("the successful path must not append errors")

        def generation_active(self, *_args):
            return True

        def cancellation_requested(self, *_args):
            return False

    class Executor:
        def __init__(self):
            self.work = None

        def try_reserve(self):
            return True

        def release_reservation(self):
            raise AssertionError("the successful path must not release a reservation")

        def submit_reserved(self, work, **_kwargs):
            self.work = work
            return SimpleNamespace(queue_position=1, running=0, queued=1, max_running=1, max_queued=1)

    jobs = Jobs()
    executor = Executor()
    calls = []

    def prefetch(_library, **kwargs):
        calls.append(kwargs)
        assert kwargs["should_cancel"]() is False
        assert kwargs["begin_commit"]() is True
        return RefreshResult(
            library_id="pytest", status="updated", docs_url=None, last_refreshed_at=None,
            targets_completed=1,
        )

    orchestrator = LibraryIngestOrchestrator(
        LibraryIngestPorts(jobs=jobs, prefetch=prefetch, timeout_seconds=lambda: 30.0, executor=lambda: executor),
        monotonic=lambda: 100.0,
        utc_now=lambda: datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc),
    )

    result = orchestrator.prefetch_docs("pytest", async_=True)
    assert result.status == "pending"
    assert jobs.updates[0]["deadline_at"] == "2026-07-27T12:00:30+00:00"

    executor.work()

    assert calls and calls[0]["staging_owner"] == {"job_id": "job-1", "generation_id": "generation-1"}
    assert jobs.updates[-1]["status"] == "succeeded"


def test_flutter_prefetch_uses_one_internal_two_target_plan():
    class Orchestrator:
        def __init__(self):
            self.calls = []

        def prefetch_docs(self, library, **kwargs):
            self.calls.append((library, kwargs))
            return "queued"

    service = LibraryDocsApplicationService.__new__(LibraryDocsApplicationService)
    service._ingest_orchestrator = Orchestrator()

    result = service.prefetch_docs("Flutter", ecosystem="flutter", async_=True)

    assert result == "queued"
    library, kwargs = service._ingest_orchestrator.calls[0]
    assert library == "Flutter"
    assert kwargs["async_"] is True
    assert [(target.source_type, target.docs_url) for target in kwargs["target_plan"]] == [
        ("guides", "https://docs.flutter.dev/"),
        ("api", "https://api.flutter.dev/index.html"),
    ]
    assert kwargs["target_plan"][0].allowed_domains == ["docs.flutter.dev"]
    assert kwargs["target_plan"][1].path_prefixes == ["/"]
    assert all(target.max_pages == 40 for target in kwargs["target_plan"])


def test_custom_flutter_url_preserves_normal_library_ingest():
    class Orchestrator:
        def __init__(self):
            self.calls = []

        def prefetch_docs(self, library, **kwargs):
            self.calls.append((library, kwargs))
            return "queued"

    service = LibraryDocsApplicationService.__new__(LibraryDocsApplicationService)
    service._ingest_orchestrator = Orchestrator()

    service.prefetch_docs(
        "Flutter",
        ecosystem="flutter",
        docs_url="https://example.test/flutter/",
        async_=True,
    )

    assert "target_plan" not in service._ingest_orchestrator.calls[0][1]


def test_legacy_official_flutter_calls_are_normalized_to_bounded_targets():
    class Orchestrator:
        def __init__(self):
            self.calls = []

        def prefetch_docs(self, library, **kwargs):
            self.calls.append((library, kwargs))
            return "queued"

    service = LibraryDocsApplicationService.__new__(LibraryDocsApplicationService)
    service._ingest_orchestrator = Orchestrator()

    service.prefetch_docs(
        "Flutter",
        ecosystem="dart",
        docs_url="https://docs.flutter.dev/",
        async_=True,
    )
    service.prefetch_docs(
        "Flutter API",
        ecosystem="dart",
        docs_url="https://api.flutter.dev/",
        async_=True,
    )

    guides = service._ingest_orchestrator.calls[0][1]
    api = service._ingest_orchestrator.calls[1][1]
    assert guides["ecosystem"] == "flutter"
    assert [(target.source_type, target.docs_url) for target in guides["target_plan"]] == [
        ("guides", "https://docs.flutter.dev/"),
    ]
    assert [(target.source_type, target.docs_url) for target in api["target_plan"]] == [
        ("api", "https://api.flutter.dev/index.html"),
    ]

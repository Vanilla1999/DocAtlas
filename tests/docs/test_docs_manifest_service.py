from __future__ import annotations

from docmancer.docs.application.docs_manifest_service import DocsManifestService
from docmancer.docs.models import DocsTarget, DocsTargetsPrefetchResult, ProjectMetadata


class FakeJobs:
    def __init__(self):
        self.calls = []

    def create(self, kind):
        self.calls.append(("create", kind))
        return type("Job", (), {"job_id": "job-1"})()

    def update(self, job_id, **changes):
        self.calls.append(("update", job_id, changes))


class FakeManifestDeps:
    def __init__(self):
        self.jobs = FakeJobs()
        self.calls = []

    def read_project_metadata(self, project_path: str) -> ProjectMetadata:
        self.calls.append(("metadata", project_path))
        return ProjectMetadata(project_path=project_path, packages={"go_router": "14.8.1"})

    def _target_from_dict(self, value):
        self.calls.append(("target", value))
        return DocsTarget(library=value["library"], version=value.get("version") or "latest", docs_url=value.get("docs_url"), allowed_domains=value.get("allowed_domains") or [])

    def _target_urls(self, target):
        return ([target.docs_url], None) if target.docs_url else ([], "target must provide docs_url")

    def _dependency_docs_url_guidance(self, target):
        return []

    def prefetch_docs_targets(self, targets, *, force_refresh=False, continue_on_error=True):
        self.calls.append(("prefetch", targets, force_refresh, continue_on_error))
        return DocsTargetsPrefetchResult(status="ok")

    def _prefetch_docs_targets_sync(self, targets, *, force_refresh=False, continue_on_error=True, job_id=None):
        self.calls.append(("sync", targets, force_refresh, continue_on_error, job_id))
        return DocsTargetsPrefetchResult(status="ok")


def test_manifest_defaults_merge_target_overrides_defaults():
    assert DocsManifestService.merge_manifest_defaults({"ecosystem": "pub", "version": "1"}, {"version": "2", "library": "x"}) == {
        "ecosystem": "pub",
        "version": "2",
        "library": "x",
    }


def test_manifest_service_resolves_project_version_from_explicit_dependency():
    deps = FakeManifestDeps()
    warnings = []

    result = DocsManifestService(deps).resolve_manifest_project_version({"library": "go_router", "version": "project-version"}, "/repo", warnings)

    assert result["version"] == "14.8.1"
    assert warnings == []
    assert deps.calls == [("metadata", "/repo")]


def test_manifest_service_validates_and_prefetches_targets(tmp_path):
    manifest = tmp_path / "docmancer.docs.yaml"
    manifest.write_text(
        """
version: 1
targets:
  - id: router
    library: go_router
    ecosystem: pub
    version: "14.8.1"
    docs_url: https://pub.dev/documentation/go_router/14.8.1/
    allowed_domains: [pub.dev]
""",
        encoding="utf-8",
    )
    deps = FakeManifestDeps()
    service = DocsManifestService(deps)

    validation = service.validate_docs_manifest(str(manifest), targets=["router"])
    result = service.prefetch_docs_manifest(str(manifest), force_refresh=True, continue_on_error=False)

    assert validation.valid is True
    assert validation.targets[0].library == "go_router"
    assert result.status == "ok"
    assert deps.calls[-1][0] == "prefetch"

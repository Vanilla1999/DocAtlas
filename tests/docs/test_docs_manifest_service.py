from __future__ import annotations

from docmancer.docs.application.docs_manifest_service import DocsManifestService
from docmancer.docs.application.docs_target_service import DocsTargetService
from docmancer.docs.models import DependencyObservation, DocsTarget, DocsTargetResult, DocsTargetsPrefetchResult, ProjectMetadata


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
        return DocsTargetService.target_from_dict(value)

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
    manifest = tmp_path / "docatlas.docs.yaml"
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
    assert validation.valid is False
    assert "manifest version must be 2" in validation.errors


def test_manifest_v2_normalizes_product_identity_and_writes_resolved_lock(tmp_path):
    manifest = tmp_path / "docatlas.docs.yaml"
    manifest.write_text(
        """
version: 2
targets:
  - id: docker-compose-reference
    identity:
      kind: product
      ecosystem: docker
      namespace: docker
      name: compose
    version:
      requested: rolling
      policy: rolling
    source:
      type: reference
      url: https://docs.docker.com/reference/compose-file/
      authority: official_product
      version_binding: rolling
      format: html
    scope:
      allowed_domains: [docs.docker.com]
      path_prefixes: [/reference/compose-file/]
      max_pages: 60
      coverage: bounded
      discovery_strategy: llms.txt
""",
        encoding="utf-8",
    )
    deps = FakeManifestDeps()
    deps.prefetch_docs_targets = lambda targets, **_kwargs: DocsTargetsPrefetchResult(
        status="ok",
        results=[DocsTargetResult(
            canonical_id="docker:docker-compose@rolling:reference",
            status="ready",
            library="docker:compose",
            ecosystem="docker",
            version="rolling",
            source_type="reference",
        )],
    )
    service = DocsManifestService(deps)

    validation = service.validate_docs_manifest(str(manifest))
    result = service.prefetch_docs_manifest(str(manifest))

    assert validation.valid is True
    target = validation.targets[0]
    assert target.library == "docker/compose"
    assert target.discovery_strategy == "llms.txt"
    assert target.authority == "official_product"
    assert result.status == "ok"
    lock = (tmp_path / ".docatlas/docs.lock.json").read_text(encoding="utf-8")
    assert '"manifest_digest": "sha256:' in lock
    assert '"version_policy": "rolling"' in lock


def test_manifest_v2_rejects_false_exactness_and_persisted_query(tmp_path):
    manifest = tmp_path / "docatlas.docs.yaml"
    manifest.write_text(
        """
version: 2
targets:
  - id: unsafe
    query: task-specific question
    identity: {kind: package, ecosystem: go, name: example.com/library}
    version: {requested: latest, policy: exact}
    source:
      type: api
      url: https://pkg.go.dev/example.com/library
      authority: official_registry
      version_binding: rolling
      version_evidence: {note: "trust me"}
      format: godoc
    scope:
      allowed_domains: [pkg.go.dev]
      path_prefixes: [/example.com/library]
      max_pages: 20
      coverage: bounded
""",
        encoding="utf-8",
    )

    validation = DocsManifestService(FakeManifestDeps()).validate_docs_manifest(str(manifest))

    assert validation.valid is False
    assert any("query is task-specific" in error for error in validation.errors)
    assert any("exact version policy" in error for error in validation.errors)


def test_manifest_v2_deep_merges_nested_defaults(tmp_path):
    manifest = tmp_path / "docatlas.docs.yaml"
    manifest.write_text(
        """
version: 2
defaults:
  source: {authority: official_product, version_binding: rolling, format: html}
  scope: {allowed_domains: [docs.docker.com], max_pages: 40, coverage: bounded}
targets:
  - id: dockerfile
    identity: {kind: product, ecosystem: docker, name: dockerfile}
    version: {requested: rolling, policy: rolling}
    source: {type: reference, url: https://docs.docker.com/reference/dockerfile/}
    scope: {path_prefixes: [/reference/dockerfile/]}
""",
        encoding="utf-8",
    )

    validation = DocsManifestService(FakeManifestDeps()).validate_docs_manifest(str(manifest))

    assert validation.valid is True
    assert validation.targets[0].allowed_domains == ["docs.docker.com"]
    assert validation.targets[0].max_pages == 40


def test_resolved_lock_detects_changed_project_dependency_evidence(tmp_path):
    manifest = tmp_path / "docatlas.docs.yaml"
    manifest.write_text(
        """
version: 2
targets:
  - id: sample
    identity: {kind: package, ecosystem: go, name: sample}
    version: {requested: project-version, policy: project, package: "go:example.com/sample", fallback: latest}
    source: {type: api, url: "https://pkg.go.dev/example.com/sample", authority: official_registry, version_binding: rolling, format: godoc}
    scope: {allowed_domains: [pkg.go.dev], path_prefixes: [/example.com/sample], coverage: bounded}
""",
        encoding="utf-8",
    )
    deps = FakeManifestDeps()
    version = {"value": "v1.0.0"}

    def metadata(project_path):
        selected = version["value"]
        return ProjectMetadata(
            project_path=project_path,
            packages={"go:example.com/sample": selected},
            dependencies=[DependencyObservation(
                ecosystem="go",
                package_name="example.com/sample",
                specifier_raw=selected,
                resolved_version=selected,
                version_source="vendor_modules_exact",
            )],
        )

    deps.read_project_metadata = metadata
    service = DocsManifestService(deps)
    service.prefetch_docs_manifest(str(manifest), project_path=str(tmp_path))
    version["value"] = "v1.1.0"

    validation = service.validate_docs_manifest(str(manifest), project_path=str(tmp_path))

    assert any("project dependency evidence changed" in warning for warning in validation.warnings)


def test_selected_target_prefetch_preserves_other_resolved_lock_entries(tmp_path):
    manifest = tmp_path / "docatlas.docs.yaml"
    manifest.write_text(
        """
version: 2
targets:
  - {id: first, identity: {kind: product, ecosystem: web, name: first}, version: {requested: rolling, policy: rolling}, source: {type: reference, url: "https://docs.example/first/", authority: official_product, version_binding: rolling, format: html}, scope: {allowed_domains: [docs.example], path_prefixes: [/first/], coverage: bounded}}
  - {id: second, identity: {kind: product, ecosystem: web, name: second}, version: {requested: rolling, policy: rolling}, source: {type: reference, url: "https://docs.example/second/", authority: official_product, version_binding: rolling, format: html}, scope: {allowed_domains: [docs.example], path_prefixes: [/second/], coverage: bounded}}
""",
        encoding="utf-8",
    )
    service = DocsManifestService(FakeManifestDeps())

    service.prefetch_docs_manifest(str(manifest))
    service.prefetch_docs_manifest(str(manifest), targets=["first"])

    lock = service._read_lock(manifest)
    assert {item["library"] for item in lock["targets"]} == {"first", "second"}

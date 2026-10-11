"""Split tests from test_docs_service.py; shared helpers remain in the façade module."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_prefetch_docs_targets_requires_allowed_domains_for_remote(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.prefetch_docs_targets([{"library": "flutter-api", "docs_url": "https://api.flutter.dev/"}])

    assert result.status == "failed"
    assert result.results[0].message == "allowed_domains is required for remote docs targets"


def test_prefetch_docs_targets_rejects_domain_not_allowed(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.prefetch_docs_targets(
        [
            {
                "library": "flutter-api",
                "docs_url": "https://api.flutter.dev/",
                "allowed_domains": ["docs.flutter.dev"],
            }
        ]
    )

    assert result.status == "failed"
    assert "not in allowed_domains" in result.results[0].message


def test_prefetch_docs_targets_rejects_path_outside_prefix(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.prefetch_docs_targets(
        [
            {
                "library": "riverpod-guides",
                "ecosystem": "web",
                "source_type": "guides",
                "seed_urls": ["https://riverpod.dev/blog/release"],
                "allowed_domains": ["riverpod.dev"],
                "path_prefixes": ["/docs/"],
            }
        ]
    )

    assert result.status == "failed"
    assert "outside path_prefixes" in result.results[0].message




def test_validate_docs_manifest_valid_manifest(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    manifest = _write_manifest(
        tmp_path / "docatlas.docs.yaml",
        """
version: 2
targets:
  - id: flutter-api-stable
    identity: {kind: sdk, ecosystem: flutter, name: flutter-api}
    version: {requested: stable, policy: channel}
    source: {type: api, url: https://api.flutter.dev/, authority: official_product, version_binding: channel, format: dartdoc}
    scope: {allowed_domains: [api.flutter.dev], coverage: bounded}
""",
    )

    result = service.validate_docs_manifest(str(manifest))

    assert result.valid is True
    assert len(result.targets) == 1
    assert result.targets[0].library == "flutter-api"


def test_validate_docs_manifest_invalid_yaml(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    manifest = _write_manifest(tmp_path / "docatlas.docs.yaml", "version: [")

    result = service.validate_docs_manifest(str(manifest))

    assert result.valid is False
    assert "invalid YAML" in result.errors[0]


def test_validate_docs_manifest_requires_allowed_domains(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    manifest = _write_manifest(
        tmp_path / "docatlas.docs.yaml",
        """
version: 2
targets:
  - id: flutter-api-stable
    identity: {kind: sdk, ecosystem: flutter, name: flutter-api}
    version: {requested: stable, policy: channel}
    source: {type: api, url: https://api.flutter.dev/, authority: official_product, version_binding: channel, format: dartdoc}
    scope: {coverage: bounded}
""",
    )

    result = service.validate_docs_manifest(str(manifest))

    assert result.valid is False
    assert "allowed_domains is required" in result.errors[0]


def test_validate_docs_manifest_duplicate_target_ids(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    manifest = _write_manifest(
        tmp_path / "docatlas.docs.yaml",
        """
version: 2
targets:
  - id: duplicate
    identity: {kind: product, ecosystem: web, name: one}
    version: {requested: rolling, policy: rolling}
    source: {type: reference, url: https://one.example.com/, authority: official_product, version_binding: rolling, format: html}
    scope: {allowed_domains: [one.example.com], coverage: bounded}
  - id: duplicate
    identity: {kind: product, ecosystem: web, name: two}
    version: {requested: rolling, policy: rolling}
    source: {type: reference, url: https://two.example.com/, authority: official_product, version_binding: rolling, format: html}
    scope: {allowed_domains: [two.example.com], coverage: bounded}
""",
    )

    result = service.validate_docs_manifest(str(manifest))

    assert result.valid is False
    assert "duplicate target id: duplicate" in result.errors


def test_validate_docs_manifest_invalid_source_type(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    manifest = _write_manifest(
        tmp_path / "docatlas.docs.yaml",
        """
version: 2
targets:
  - id: bad-source
    identity: {kind: sdk, ecosystem: flutter, name: flutter-api}
    version: {requested: stable, policy: channel}
    source: {type: blog, url: https://api.flutter.dev/, authority: official_product, version_binding: channel, format: dartdoc}
    scope: {allowed_domains: [api.flutter.dev], coverage: bounded}
""",
    )

    result = service.validate_docs_manifest(str(manifest))

    assert result.valid is False
    assert "invalid source_type" in result.errors[0]


def test_validate_docs_manifest_rejects_path_prefix_escape(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    manifest = _write_manifest(
        tmp_path / "docatlas.docs.yaml",
        """
version: 2
targets:
  - id: riverpod-guides
    identity: {kind: product, ecosystem: web, name: riverpod-guides}
    version: {requested: latest, policy: rolling}
    source: {type: guides, url: https://riverpod.dev/docs/, authority: official_product, version_binding: rolling, format: html}
    scope:
      seed_urls: [https://riverpod.dev/blog/release]
      allowed_domains: [riverpod.dev]
      path_prefixes: [/docs/]
      coverage: bounded
""",
    )

    result = service.validate_docs_manifest(str(manifest))

    assert result.valid is False
    assert "outside path_prefixes" in result.errors[0]


def test_inspect_library_docs_ready_target(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="14.8.1",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )

    result = service.inspect_library_docs("pub:go_router@14.8.1:api")

    assert result.canonical_id == "pub:go_router@14.8.1:api"
    assert result.source_id == "pub:go_router:api"
    assert result.status == "empty_index"
    assert result.library == "go_router"
    assert result.docs_url_resolved == "https://pub.dev/documentation/go_router/14.8.1/"
    assert result.docs_snapshot_exact is True
    assert result.requested_version == "14.8.1"
    assert result.resolved_version == "14.8.1"
    assert result.version_source == "explicit"
    assert result.version_confidence == "high"
    assert result.version_inferred is False
    assert result.stale is False
    assert result.reason_code == "empty_index"
    assert result.pages == 0
    assert result.chunks == 0


def test_inspect_on_empty_index_reports_empty_index_state(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="click",
        ecosystem="python",
        version="8.1.7",
        source_type="api",
        docs_url="https://click.palletsprojects.com/en/8.1.x/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    config = service._index_config_for(record)
    SQLiteStore(config.index.db_path, config.index.extracted_dir)

    result = service.inspect_library_docs("python:click@8.1.7:api")

    assert result.status == "empty_index"
    assert result.reason_code == "empty_index"
    assert result.pages == 0
    assert result.chunks == 0


def test_list_libraries_shows_pages_and_chunks(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="click",
        ecosystem="python",
        version="8.1.7",
        source_type="api",
        docs_url="https://click.palletsprojects.com/en/8.1.x/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _write_library_index(service, record)

    result = service.list_libraries()

    assert result[0].status == "indexed"
    assert result[0].reason_code == "healthy"
    assert result[0].pages == 1
    assert result[0].chunks == 1


def test_list_libraries_exposes_removable_canonical_id(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="14.8.1",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
        now=now,
        status="available",
    )

    result = service.list_libraries()

    assert result[0].library_id == "pub:go_router@14.8.1:api"
    assert result[0].canonical_id == "pub:go_router@14.8.1:api"
    assert result[0].source_id == "pub:go_router:api"


def test_stale_index_triggers_warning_not_empty_state(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    record = service.registry.upsert(
        library="click",
        ecosystem="python",
        version="8.1.7",
        source_type="api",
        docs_url="https://click.palletsprojects.com/en/8.1.x/",
        now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        status="available",
        last_refreshed_at=_old_iso(),
    )
    _write_library_index(service, record)

    result = service.inspect_library_docs("python:click@8.1.7:api")

    assert result.status == "stale"
    assert result.reason_code == "stale"
    assert result.stale is True
    assert result.pages == 1
    assert result.chunks == 1


def test_remove_library_docs_exact_canonical_id_only(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="14.8.1",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
        now=now,
        status="available",
    )
    service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="latest",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/latest/",
        now=now,
        status="available",
    )

    result = service.remove_library_docs("pub:go_router@14.8.1:api")

    assert result.removed is True
    assert service.registry.get("pub:go_router@14.8.1:api") is None
    assert service.registry.get("pub:go_router@latest:api") is not None


def test_remove_api_does_not_remove_guides(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="riverpod",
        ecosystem="web",
        version="latest",
        source_type="api",
        docs_url="https://pub.dev/documentation/riverpod/latest/",
        now=now,
        status="available",
    )
    service.registry.upsert(
        library="riverpod",
        ecosystem="web",
        version="latest",
        source_type="guides",
        docs_url="https://riverpod.dev/docs/",
        now=now,
        status="available",
    )

    service.remove_library_docs("web:riverpod@latest:api")

    assert service.registry.get("web:riverpod@latest:api") is None
    assert service.registry.get("web:riverpod@latest:guides") is not None


def test_prune_library_docs_dry_run_removes_nothing(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="14.8.1",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
        now=_old_iso(120),
        status="available",
        last_refreshed_at=_old_iso(120),
    )

    result = service.prune_library_docs(library="go_router", older_than_days=90, dry_run=True)

    assert result.would_remove == ["pub:go_router@14.8.1:api"]
    assert service.registry.get("pub:go_router@14.8.1:api") is not None


def test_prune_library_docs_keep_versions_respected(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    for version in ["14.8.1", "17.2.3"]:
        service.registry.upsert(
            library="go_router",
            ecosystem="pub",
            version=version,
            source_type="api",
            docs_url=f"https://pub.dev/documentation/go_router/{version}/",
            now=_old_iso(120),
            status="available",
            last_refreshed_at=_old_iso(120),
        )

    result = service.prune_library_docs(
        library="go_router",
        keep_versions=["17.2.3"],
        older_than_days=90,
        dry_run=True,
    )

    assert result.would_remove == ["pub:go_router@14.8.1:api"]


def test_prune_library_docs_removes_failed_stale_records(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="15.0.0",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/15.0.0/",
        now=_old_iso(120),
        status="failed",
        last_error="404",
    )

    result = service.prune_library_docs(library="go_router", older_than_days=90, dry_run=False)

    assert result.removed == ["pub:go_router@15.0.0:api"]
    assert service.registry.get("pub:go_router@15.0.0:api") is None


def test_prune_library_docs_dry_run_includes_failed_records_even_when_not_old(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="15.0.0",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/15.0.0/",
        now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        status="failed",
        last_error="404",
    )

    result = service.prune_library_docs(library="go_router", older_than_days=90, dry_run=True)

    assert result.would_remove == ["pub:go_router@15.0.0:api"]
    assert service.registry.get("pub:go_router@15.0.0:api") is not None


def test_prefetch_docs_targets_rejects_localhost_url(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.prefetch_docs_targets(
        [{"library": "local", "docs_url": "http://localhost:8000", "allowed_domains": ["localhost"]}]
    )

    assert result.status == "failed"
    assert result.results[0].message == "localhost URLs are not allowed"


def test_prefetch_docs_targets_rejects_private_ip_url(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.prefetch_docs_targets(
        [{"library": "router", "docs_url": "http://192.168.1.1", "allowed_domains": ["192.168.1.1"]}]
    )

    assert result.status == "failed"
    assert result.results[0].message == "private network URLs are not allowed"


def test_prefetch_docs_targets_rejects_file_url(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.prefetch_docs_targets(
        [{"library": "passwd", "docs_url": "file:///etc/passwd", "allowed_domains": ["etc"]}]
    )

    assert result.status == "failed"
    assert result.results[0].message == "unsupported URL scheme: file"

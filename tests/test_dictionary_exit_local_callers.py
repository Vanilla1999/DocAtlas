"""Direct local callers deny before effects; explicit source context stays read-only."""
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from docmancer.docs import _patch_plan_context_part01 as scanners
from docmancer.docs.application import _project_docs_service_part02 as sync_shard
from docmancer.docs.application.project_docs_service import ProjectDocsService
from docmancer.docs.models import ProjectMetadata

pytestmark = pytest.mark.behavioral


def write(root, relative, content=b"literal fixture\n"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def catalog(root, *, code_files=(), config=None):
    write(root, "README.md")
    data = dict(schema_version=1, documents=[dict(
        path="README.md", role="overview", scope="project", module_path=None,
        description="Explicit fixture.", authority="source_of_truth", status="active", impact="track",
    )], code_files=list(code_files))
    write(root, "docatlas.project-docs.yaml", yaml.safe_dump(data).encode())
    if config is not None:
        write(root, "docatlas.yaml", yaml.safe_dump(dict(project=config)).encode())


def no_tree_reads(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("unexpected directory enumeration")
    for name in ("glob", "rglob", "iterdir"):
        monkeypatch.setattr(Path, name, deny)
    monkeypatch.setattr(os, "scandir", deny)


def guarded_file_reads(monkeypatch, *, selected=()):
    calls = []
    original = Path.open
    controls = {"docatlas.project-docs.yaml", "docatlas.yaml", ".gitignore"}
    def guarded(path, *args, **kwargs):
        assert path.name in controls or path in selected, f"unselected read: {path}"
        calls.append(path)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded)
    return calls


@pytest.mark.parametrize("held", [False, True])
@pytest.mark.parametrize("arguments", [
    {}, dict(with_vectors=True), dict(changed_paths=["README.md"]),
    dict(deleted_paths=["formerly-selected.md"]),
    dict(renamed_paths=[dict(old_path="formerly-selected.md", new_path="README.md")]),
    dict(changed_paths=[], deleted_paths=[], renamed_paths=[]),
])
def test_direct_sync_denies_before_path_index_adapter_lock_or_mutation(tmp_path, monkeypatch, held, arguments):
    calls = []
    def deny(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("sync effect before an explicit mutation grant")
    facade = SimpleNamespace(config=SimpleNamespace(index=SimpleNamespace(db_path=tmp_path / "must-not-create.db")),
                             _project_sync_project_docs_impl=deny)
    service = ProjectDocsService(facade)
    for name in ("_agent_instance", "_indexed_project_doc_sources", "read_project_metadata", "ingest_project_docs"):
        monkeypatch.setattr(service, name, deny, raising=False)
    for name in ("validate_project_path", "storage_writer_lease", "storage_mutation_lock"):
        monkeypatch.setattr(sync_shard, name, deny)
    monkeypatch.setattr(Path, "open", deny)
    monkeypatch.setattr(Path, "stat", deny)
    no_tree_reads(monkeypatch)
    with pytest.raises(PermissionError, match="no explicit mutation grant and validated member transaction"):
        service.sync_project_docs(str(tmp_path), _coordination_held=held, **arguments)
    assert calls == []


def test_private_incremental_sync_cannot_bypass_denial_with_supplied_metadata(tmp_path, monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("incremental side effect")
    service = ProjectDocsService(SimpleNamespace())
    for name in ("_agent_instance", "_indexed_project_doc_sources", "ingest_project_docs"):
        monkeypatch.setattr(service, name, deny, raising=False)
    monkeypatch.setattr(Path, "open", deny)
    monkeypatch.setattr(Path, "stat", deny)
    no_tree_reads(monkeypatch)
    with pytest.raises(PermissionError, match="orphan deletion"):
        service._sync_project_docs_incremental(
            tmp_path, ProjectMetadata(project_path=str(tmp_path)), with_vectors=True,
            changed_paths=["README.md"], deleted_paths=["formerly-selected.md"], renamed_paths=None,
        )


@pytest.mark.parametrize("state", ["absent", "empty", "invalid"])
def test_callable_scanners_empty_code_never_enumerate_read_or_certify_absence(tmp_path, monkeypatch, state):
    path = write(tmp_path, "existing.py", b"class ExistingThing: pass\n")
    write(tmp_path, "pubspec.lock")
    write(tmp_path, ".dart_tool/package_config.json")
    if state != "absent":
        catalog(tmp_path)
    if state == "invalid":
        write(tmp_path, "docatlas.project-docs.yaml", b"schema_version: 900\n")
    no_tree_reads(monkeypatch)
    calls = guarded_file_reads(monkeypatch)
    original_stat = Path.stat
    def guarded_stat(candidate, *args, **kwargs):
        assert candidate not in {path, tmp_path / "pubspec.lock", tmp_path / ".dart_tool/package_config.json"}
        return original_stat(candidate, *args, **kwargs)
    monkeypatch.setattr(Path, "stat", guarded_stat)
    assert list(scanners._iter_source_files(tmp_path)) == []
    assert list(scanners._iter_dependency_source_files(tmp_path)) == []
    assert scanners._read_text(path) is None
    assert scanners._read_text(path, root=tmp_path) is None
    assert scanners._changed_file_candidate(tmp_path, "existing.py") is None
    assert scanners._resolved_dart_package_roots(tmp_path)[0] == []
    assert "resolve_dart_package_roots" not in scanners.__dict__
    assert scanners._pubspec_lock_packages(tmp_path) == set()
    assert scanners._find_dependency_symbol("ImportedThing", tmp_path / "pubspec.lock", "class ImportedThing {}") is None
    apis, warnings = scanners.discover_dart_dependency_apis(
        "Use ExistingThing BottomSheet", project_path=str(tmp_path), symbol_queries=["ExistingThing"], include_dependency_source=True)
    assert apis == [] and any("unresolved" in warning for warning in warnings)
    assert scanners.discover_missing_symbols("ExistingThing", project_path=str(tmp_path), symbol_queries=["ExistingThing"], searched_dependency=True) == []
    assert scanners.discover_rejected_sources("camera dialog bottom sheet plan", project_path=str(tmp_path)) == []
    assert scanners._find_patterns_for_plan(str(tmp_path), [dict(file="existing.py", symbols=["ExistingThing"])]) == []
    mapped = scanners.build_implementation_map(
        "Change ExistingThing", project_path=str(tmp_path), relevant_files=[dict(file="existing.py")],
        existing_apis=[dict(symbol="InventedAPI")], missing_symbols=[dict(symbol="MissingAPI")],
    )
    assert mapped["current_behavior"] == [] and mapped["minimal_patch_path"] == []
    assert any("unresolved" in warning for warning in mapped["warnings"])
    assert all(candidate.name in {"docatlas.project-docs.yaml", "docatlas.yaml", ".gitignore"} for candidate in calls)


def test_real_selected_readonly_caller_retains_original_crlf_bytes_hash_and_spans(tmp_path, monkeypatch):
    raw = "import unselected\r\nclass LiteralThing:\r\n    label = 'Кварк'\r\n".encode()
    selected = write(tmp_path, "selected.py", raw)
    write(tmp_path, "unselected.py", b"class HiddenThing: pass\n")
    catalog(tmp_path, code_files=["selected.py"])
    no_tree_reads(monkeypatch)
    calls = guarded_file_reads(monkeypatch, selected=(selected,))
    assert list(scanners._iter_source_files(tmp_path)) == [selected]
    assert scanners._read_text(selected, root=tmp_path) == raw.decode()
    assert scanners._read_text(selected) is None  # Bare path is not a read grant.
    candidate = scanners._changed_file_candidate(tmp_path, "selected.py")
    assert candidate["action"] == "read"
    assert candidate["content_hash"] == "sha256:" + hashlib.sha256(raw).hexdigest()
    assert candidate["refs"][0]["start_line"] == 1 and candidate["refs"][0]["end_line"] == 3
    mapped = scanners.build_implementation_map(
        "Change LiteralThing", project_path=str(tmp_path), relevant_files=[candidate], existing_apis=[], missing_symbols=[])
    assert mapped["current_behavior"][0]["content_hash"] == candidate["content_hash"]
    assert mapped["current_behavior"][0]["confidence"] == "unknown"
    assert mapped["minimal_patch_path"] == []
    assert selected.read_bytes() == raw
    assert all(path == selected or path.name in {"docatlas.project-docs.yaml", "docatlas.yaml", ".gitignore"} for path in calls)


@pytest.mark.parametrize("path", ["unselected.py", "../outside.py", "./selected.py", "docs/*.py", "selected.py/"])
def test_changed_path_is_not_membership_or_a_read_grant(tmp_path, monkeypatch, path):
    selected = write(tmp_path, "selected.py", b"class LiteralThing: pass\n")
    write(tmp_path, "unselected.py")
    catalog(tmp_path, code_files=["selected.py"])
    no_tree_reads(monkeypatch)
    calls = guarded_file_reads(monkeypatch)
    assert scanners._changed_file_candidate(tmp_path, path) is None
    assert selected not in calls


@pytest.mark.parametrize("restriction", ["ignore", "exclude", "extension", "generated", "bytes", "depth", "count", "deadline", "roots"])
def test_readonly_callers_preserve_existing_source_boundaries(tmp_path, monkeypatch, restriction):
    relative = "nested/inner/selected.py" if restriction == "depth" else "nested/selected.py"
    path = write(tmp_path, relative, b"class LiteralThing: pass\n")
    configurations = {
        "ignore": {}, "exclude": dict(exclude_paths=["nested/selected.py"]),
        "extension": dict(include_extensions=[".dart"]),
        "generated": dict(generated_paths=["nested/selected.py"]),
        "bytes": dict(max_file_bytes=1), "depth": dict(max_directory_depth=1),
        "count": dict(max_scanned_files=1), "deadline": {},
        "roots": dict(source_roots=["other"]),
    }
    members = [relative]
    if restriction == "count":
        write(tmp_path, "nested/second.py")
        members.append("nested/second.py")
    catalog(tmp_path, code_files=members, config=configurations[restriction])
    if restriction == "ignore":
        write(tmp_path, ".gitignore", b"nested/\n")
    if restriction == "deadline":
        counter = iter([0.0, 100.0])
        monkeypatch.setattr(scanners, "time", SimpleNamespace(monotonic=lambda: next(counter)))
    no_tree_reads(monkeypatch)
    calls = guarded_file_reads(monkeypatch)
    assert scanners._read_text(path, root=tmp_path) is None
    assert path not in calls


@pytest.mark.parametrize("parent", [False, True])
def test_selected_symlink_cannot_read_outside_root(tmp_path, monkeypatch, parent):
    outside = tmp_path / "outside"
    outside.mkdir()
    target = write(outside, "selected.py", b"outside bytes\n")
    root = tmp_path / "repo"
    root.mkdir()
    if parent:
        (root / "linked").symlink_to(outside, target_is_directory=True)
        path = "linked/selected.py"
    else:
        (root / "selected.py").symlink_to(target)
        path = "selected.py"
    catalog(root, code_files=[path])
    no_tree_reads(monkeypatch)
    calls = guarded_file_reads(monkeypatch)
    assert list(scanners._iter_source_files(root)) == []
    assert scanners._changed_file_candidate(root, path) is None
    assert target not in calls


def test_public_service_sync_delegate_reaches_guard_without_service_initialization(tmp_path, monkeypatch):
    from docmancer.docs.service import LibraryDocsService

    def deny(*args, **kwargs):
        raise AssertionError("public delegate effect")
    delegate = ProjectDocsService(SimpleNamespace())
    for name in ("_agent_instance", "_indexed_project_doc_sources", "ingest_project_docs"):
        monkeypatch.setattr(delegate, name, deny, raising=False)
    monkeypatch.setattr(Path, "open", deny)
    monkeypatch.setattr(Path, "stat", deny)
    no_tree_reads(monkeypatch)
    facade = SimpleNamespace(project_docs=delegate)
    with pytest.raises(PermissionError, match="no explicit mutation grant"):
        LibraryDocsService.sync_project_docs(facade, str(tmp_path), deleted_paths=["formerly-selected.md"])

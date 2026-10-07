"""Finite local membership, actual callers, and no implicit read expansion."""
from dataclasses import asdict, replace
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from docmancer.docs.project import ProjectMetadataReader
from docmancer.docs.project_docs_catalog import read_project_docs_catalog
from docmancer.docs.domain.source_boundary import SourceBoundary, iter_bounded_source_files
from docmancer.docs.domain.source_map import build_project_source_evidence, collect_project_source_facts
from docmancer.docs.domain.code_graph import build_project_code_graph
from docmancer.docs.application.patch_constraints_service import PatchConstraintsService
from docmancer.docs.application.project_docs_service import ProjectDocsService
from docmancer.docs._patch_plan_context_part02 import build_patch_plan_context
from docmancer.docs.domain.project_doc_ranking import rerank_project_doc_chunks
from docmancer.docs.local_membership import document_binding, finite_doc_reference
from docmancer.docs.application.patch_review_service import PatchReviewService

pytestmark = pytest.mark.behavioral

PILOT = {
    "README.md": "overview", "CONTRIBUTING.md": "development",
    "docs/INDEX.md": "overview", "docs/PROJECT_MAP.md": "project_architecture",
    "wiki/Architecture.md": "project_architecture",
    "docs/adr/0003-context-first-project-reads.md": "development",
    "docs/mcp-docs-server.md": "api_contract", "docs/testing.md": "runbook",
    "docs/project-docs-mcp-workflow.md": "runbook",
    "wiki/Supported-Sources.md": "api_contract",
}


def write(root, path, text="literal bytes\n"):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def catalog(root, paths=("README.md",), **extra):
    documents = []
    for path in paths:
        write(root, path)
        documents.append(dict(path=path, role=PILOT.get(path, "development"),
                              scope="project", module_path=None, description="Literal fixture.",
                              authority="source_of_truth", status="active", impact="track"))
    data = dict(schema_version=1, documents=documents, code_files=[])
    data.update(extra)
    write(root, "docatlas.project-docs.yaml", yaml.safe_dump(data))
    return data


def forbid_walk(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("implicit tree enumeration")
    for name in ("glob", "rglob", "iterdir"):
        monkeypatch.setattr(Path, name, forbidden)


def test_committed_pilot_exact_roles_hashes_and_no_discovery(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    forbid_walk(monkeypatch)
    metadata = ProjectMetadataReader().read(root)
    assert metadata.docs_catalog_present and metadata.docs_catalog_valid
    assert {item.path: item.reason for item in metadata.docs_candidates} == PILOT
    assert metadata.code_files == ()
    assert metadata.dependencies == [] and metadata.dependency_source_roots == {}
    assert len(metadata.docs_candidates) == 10
    for item in metadata.docs_candidates:
        assert item.doc_scope == "project" and item.module_path is None
        assert item.lifecycle_status == "active" and item.impact_policy == "track"
        assert item.content_hash == "sha256:" + hashlib.sha256((root / item.path).read_bytes()).hexdigest()
        assert item.catalog_entry_hash.startswith("sha256:")


def test_actual_inspect_and_patch_constraints_read_only_ten_members(tmp_path, monkeypatch):
    catalog(tmp_path, PILOT)
    write(tmp_path, "docs/unselected.md", "Must edit everything\n")
    write(tmp_path, "src/unselected.py", "class InvisibleThing: pass\n")
    forbid_walk(monkeypatch)
    facade = SimpleNamespace(read_project_metadata=lambda path: ProjectMetadataReader().read(path),
                             active_index_diagnostics=lambda path: {})
    docs = ProjectDocsService(facade)
    monkeypatch.setattr(docs, "_indexed_project_doc_sources", lambda path: [])
    inspection = docs.inspect_project_docs(str(tmp_path))
    assert {row["path"] for row in inspection.candidate_sources} == set(PILOT)
    assert inspection.dependency_sources["manifests_found"] == []
    packet = PatchConstraintsService(facade).get_patch_constraints(
        "Inspect `InvisibleThing`", project_path=str(tmp_path), changed_files=["src/unselected.py"])
    assert packet.index_state["visible_source_count"] == 10
    assert set(packet.index_state["source_paths"]) == set(PILOT)
    assert packet.source_evidence == [] and packet.repo_map == [] and packet.symbol_candidates == []
    assert packet.source_of_truth_rules == []
    assert any("does not authorize edits" in warning for warning in packet.warnings)


@pytest.mark.parametrize("state", ["absent", "empty", "invalid"])
def test_empty_or_absent_code_membership_never_scans_or_certifies_absence(tmp_path, monkeypatch, state):
    if state != "absent":
        catalog(tmp_path)
    if state == "invalid":
        write(tmp_path, "docatlas.project-docs.yaml", "schema_version: 900\n")
    write(tmp_path, "src/exists.py", "class ExistingThing: pass\n")
    forbid_walk(monkeypatch)
    assert collect_project_source_facts(tmp_path, question="ExistingThing", include_unmatched=True) == []
    assert build_project_source_evidence(tmp_path, requirements=["MissingThing"]) == []
    graph = build_project_code_graph(tmp_path, question="ExistingThing")
    assert graph.nodes == [] and graph.edges == []
    assert graph.diagnostics["status"] == "unresolved_membership"
    assert graph.diagnostics["analysis_complete"] is False
    packet = build_patch_plan_context("ExistingThing", project_path=str(tmp_path), changed_files=["src/exists.py"])
    assert packet["answer_available"] is False
    assert packet["answer_completeness"] == "unresolved"
    assert packet["missing_symbols"] == [] and packet["relevant_files"] == []


@pytest.mark.parametrize("bad", ["../outside.md", "/absolute.md", "docs/*.md", "./README.md", "docs//file.md", "docs\\file.md"])
def test_invalid_literal_member_fails_whole_catalog(tmp_path, bad):
    data = catalog(tmp_path)
    data["documents"].append({**data["documents"][0], "path": bad})
    write(tmp_path, "docatlas.project-docs.yaml", yaml.safe_dump(data))
    assert not read_project_docs_catalog(tmp_path).valid
    assert ProjectMetadataReader().read(tmp_path).docs_candidates == []


@pytest.mark.parametrize("parent", [False, True])
def test_symlink_out_of_root_rejected_before_read(tmp_path, parent):
    catalog(tmp_path)
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    write(outside, "secret.md", "outside bytes\n")
    if parent:
        (tmp_path / "link").symlink_to(outside, target_is_directory=True)
        path = "link/secret.md"
    else:
        (tmp_path / "secret.md").symlink_to(outside / "secret.md")
        path = "secret.md"
    data = yaml.safe_load((tmp_path / "docatlas.project-docs.yaml").read_text())
    data["documents"][0]["path"] = path
    write(tmp_path, "docatlas.project-docs.yaml", yaml.safe_dump(data))
    assert not read_project_docs_catalog(tmp_path).valid
    assert ProjectMetadataReader().read(tmp_path).docs_candidates == []


def test_selected_index_links_never_expand_membership(tmp_path, monkeypatch):
    catalog(tmp_path, ["docs/INDEX.md"])
    write(tmp_path, "docs/INDEX.md", "[sibling](unselected.md)\n[code](../src/secret.py)\n")
    write(tmp_path, "docs/unselected.md")
    write(tmp_path, "src/secret.py")
    forbid_walk(monkeypatch)
    assert [item.path for item in ProjectMetadataReader().discover_docs(tmp_path)] == ["docs/INDEX.md"]


def test_roots_are_not_finite_membership(tmp_path, monkeypatch):
    catalog(tmp_path, roots=[dict(path="docs", index="INDEX.md")])
    forbid_walk(monkeypatch)
    assert not read_project_docs_catalog(tmp_path).valid
    assert ProjectMetadataReader().discover_docs(tmp_path) == []


def test_no_dependency_metadata_reads(tmp_path, monkeypatch):
    catalog(tmp_path)
    for path in (".fvmrc", "pubspec.yaml", "pubspec.lock", "pyproject.toml", "package.json", ".dart_tool/package_config.json"):
        write(tmp_path, path, "not granted\n")
    original = Path.read_text
    def guarded(path, *args, **kwargs):
        assert path.name in {"docatlas.project-docs.yaml", ".gitignore", "docatlas.yaml"}
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", guarded)
    metadata = ProjectMetadataReader().read(tmp_path)
    assert len(metadata.docs_candidates) == 1 and metadata.packages == {}


def test_finite_code_members_never_expand_imports_and_preserve_line_spans(tmp_path, monkeypatch):
    write(tmp_path, "selected.py", "import unselected\nclass LiteralThing: pass\n")
    write(tmp_path, "unselected.py", "class HiddenThing: pass\n")
    catalog(tmp_path, code_files=["selected.py"])
    forbid_walk(monkeypatch)
    facts = collect_project_source_facts(tmp_path, question="LiteralThing")
    assert [item["path"] for item in facts] == ["selected.py"]
    snippets = build_project_source_evidence(tmp_path, requirements=["LiteralThing"])
    assert snippets[0]["path"] == "selected.py"
    assert snippets[0]["line_start"] == snippets[0]["line_end"] == 2
    graph = build_project_code_graph(tmp_path, question="LiteralThing")
    assert {node.path for node in graph.nodes} == {"selected.py"}
    assert any(edge.kind == "unresolved_import" for edge in graph.edges)


@pytest.mark.parametrize("restriction", ["ignore", "exclude", "extension", "bytes", "depth", "generated", "roots"])
def test_finite_membership_preserves_boundaries(tmp_path, restriction):
    path = "nested/file.py"
    write(tmp_path, path, "class LiteralThing: pass\n")
    boundary = SourceBoundary(code_files=(path,))
    overrides = {
        "ignore": dict(gitignore_patterns=("nested/",)),
        "exclude": dict(exclude_paths=(path,)), "extension": dict(include_extensions=(".dart",)),
        "bytes": dict(max_file_bytes=1), "depth": dict(max_directory_depth=0),
        "generated": dict(generated_paths=(path,)),
        "roots": dict(source_roots=("other",)),
    }
    assert list(iter_bounded_source_files(tmp_path, boundary=replace(boundary, **overrides[restriction]),
                                         supported_extensions=frozenset({".py"}))) == []


def test_rank_only_bound_members_without_path_demotion_or_authority(tmp_path):
    path = "docs/research/docatlas-dogfood/literal.md"
    catalog(tmp_path, [path])
    chunk = SimpleNamespace(path=path, stale=False, lifecycle_status="active", metadata={}, score=1.0)
    selected = rerank_project_doc_chunks([chunk], question="literal", intent=SimpleNamespace(broad=False),
                                       finite_member_paths=frozenset({path}))
    assert selected == [chunk]
    assert "authority" not in chunk.metadata
    assert rerank_project_doc_chunks([chunk], question="literal", intent=SimpleNamespace(broad=False),
                                    finite_member_paths=frozenset()) == []


def test_review_demotion_removed_only_for_actual_hash_bound_member(tmp_path):
    path = "docs/research/docatlas-dogfood/literal.md"
    catalog(tmp_path, [path])
    binding = document_binding(tmp_path, path)
    item = dict(id="literal", source=path, confidence="medium", type="architecture",
                instruction="literal", source_refs=[dict(path=path, local_read_binding=binding)])
    assert finite_doc_reference(item)
    assert PatchReviewService._summary_constraint_rank(item, [path], "literal")[0] < 75
    write(tmp_path, path, "changed bytes\n")
    assert not finite_doc_reference(item)
    assert PatchReviewService._summary_constraint_rank(item, [path], "literal")[0] >= 75


@pytest.mark.parametrize("consent", [None, False, 1, "true", True])
def test_generated_read_requires_literal_boolean_consent_and_finite_member(tmp_path, consent):
    path = "generated/selected.py"
    write(tmp_path, path, "class LiteralThing: pass\n")
    boundary = SourceBoundary(code_files=(path,))
    selected = list(iter_bounded_source_files(tmp_path, boundary=boundary,
        supported_extensions=frozenset({".py"}), include_generated=consent))
    assert selected == ([tmp_path / path] if consent is True else [])
    assert list(iter_bounded_source_files(tmp_path, boundary=replace(boundary, code_files=()),
        supported_extensions=frozenset({".py"}), include_generated=True)) == []

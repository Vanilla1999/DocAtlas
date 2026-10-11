"""Literal source budgets and topic-free, context-only documentation gaps."""
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from docmancer.docs.domain import project_state, source_map
from docmancer.docs.domain.source_boundary import SourceBoundary


def _write(root, relative, text="class ArbitraryWidget: pass\n"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def _declare_code_files(root, *paths):
    (root / "docatlas.project-docs.yaml").write_text(
        json.dumps({"schema_version": 1, "documents": [], "code_files": list(paths)}),
        encoding="utf-8",
    )


def _observe_source_reads(monkeypatch, root):
    original_read_text = Path.read_text
    observed = {}

    def read_text(path, *args, **kwargs):
        value = original_read_text(path, *args, **kwargs)
        if path.is_relative_to(root) and path.suffix in {".py", ".dart"}:
            observed.setdefault(path.relative_to(root).as_posix(), []).append(
                hashlib.sha256(value.encode("utf-8")).hexdigest()
            )
        return value

    monkeypatch.setattr(Path, "read_text", read_text)
    return observed








@pytest.mark.parametrize("suffix", ["Gate", "Service", "Repository", "Controller", "Manager", "Policy", "Adapter"])
def test_real_snippet_budget_does_not_prefer_role_names(tmp_path, suffix, monkeypatch):
    _write(tmp_path, "a.dart", "class ArbitraryQuux {}\n")
    _write(tmp_path, "b.dart", f"class Later{suffix} {{}}\n")
    _write(tmp_path, "unlisted.dart", "class ArbitraryQuux {}\n")
    original = {path: (tmp_path / path).read_bytes() for path in ("a.dart", "b.dart")}
    observed = _observe_source_reads(monkeypatch, tmp_path)
    assert source_map.build_project_source_evidence(
        tmp_path, requirements=["ArbitraryQuux", f"Later{suffix}"], max_items=1,
    ) == []
    assert observed == {}
    _declare_code_files(tmp_path, "a.dart", "b.dart")
    items = source_map.build_project_source_evidence(
        tmp_path, requirements=["ArbitraryQuux", f"Later{suffix}"], max_items=1,
    )
    assert [item["matched_terms"] for item in items] == [["ArbitraryQuux"]]
    assert items[0]["path"] == "a.dart"
    assert items[0]["line_start"] == items[0]["line_end"] == 1
    assert items[0]["symbols"][0]["name"] == "ArbitraryQuux"
    assert observed == {
        path: [hashlib.sha256(data).hexdigest()] for path, data in original.items()
    }
    assert items[0]["source"]["path"] == "a.dart"
    assert items[0]["source"]["line_start"] == items[0]["source"]["line_end"] == 1
    assert items[0]["snippet"] == original["a.dart"].decode("utf-8").strip()


@pytest.mark.parametrize("query", [None, "", "   ", "Explain UnseenQuux", "Объясни НевидимыйКварк", "  AlphaWidget?\nНе меняй BetaService!  "])
def test_gap_passes_original_query_and_explicit_unmatched_contract(tmp_path, monkeypatch, query):
    calls = []
    original = project_state.collect_project_source_facts
    _write(tmp_path, "src/arbitrary.py")
    _declare_code_files(tmp_path, "src/arbitrary.py")

    def capture(root, **kwargs):
        calls.append(kwargs)
        return original(root, **kwargs)

    monkeypatch.setattr(project_state, "collect_project_source_facts", capture)
    action = project_state.create_project_docs_next_action(tmp_path, query)
    assert calls == [{
        "question": query if query is not None else "", "max_files": 6,
        "token_budget": 800, "include_unmatched": True,
    }]
    assert {"category": "source map", "paths": ["src/arbitrary.py"], "facts": []} in action["documentation_gap"]["evidence_to_collect"]
    retry = action["after"][1]["arguments_patch"]
    assert retry == {"project_path": str(tmp_path), **({"question": query} if query is not None else {})}
    assert action["requires_confirmation"] is True
    assert action["documentation_gap"]["evidence_complete"] is False
    assert all(section["state"] == "missing" for section in action["documentation_gap"]["required_sections"])






@pytest.mark.parametrize("question", ["", "   "])
def test_empty_question_does_not_create_snippets_absence_or_universal_support(tmp_path, question):
    _write(tmp_path, "a.py")
    assert source_map.build_project_source_evidence(tmp_path, question=question) == []
    assert source_map.build_project_repo_map(tmp_path, question=question) == []
    assert project_state.evaluate_documentation_sections([], []) == ([], False)
    assert project_state.create_project_docs_next_action(tmp_path, question)["documentation_gap"]["evidence_complete"] is False


@pytest.mark.parametrize("flag", [None, False, 1, "true", True])
@pytest.mark.parametrize("collector", ["facts", "snippets"])
def test_generated_requires_boolean_true_even_for_explicit_path(tmp_path, flag, collector, monkeypatch):
    _write(tmp_path, "lib/a.dart", "class OrdinaryQuux {}\n")
    _write(tmp_path, "lib/generated/a.g.dart", "class GeneratedQuux {}\n")
    mixed_members = ("lib/a.dart", "lib/generated/a.g.dart")
    source_bytes = {path: (tmp_path / path).read_bytes() for path in mixed_members}
    observed = _observe_source_reads(monkeypatch, tmp_path)

    # Two authored grants, identical for every flag. A denied mixed declaration
    # never falls back to a subset; the normal-only grant is a separate control.
    for members in (mixed_members, ("lib/a.dart",)):
        _declare_code_files(tmp_path, *members)
        observed.clear()
        if collector == "facts":
            rows = source_map.collect_project_source_facts(
                tmp_path, question="include generated lib/generated/a.g.dart GeneratedQuux",
                include_unmatched=True, include_generated=flag,
            )
        else:
            rows = source_map.build_project_source_evidence(
                tmp_path, requirements=["lib/generated/a.g.dart", "OrdinaryQuux"], include_generated=flag,
            )
        if members == mixed_members and flag is not True:
            assert rows == []
            assert observed == {}
        else:
            assert {row["path"] for row in rows if row.get("path")} == set(members)
            assert observed == {
                path: [hashlib.sha256(source_bytes[path]).hexdigest()] for path in members
            }


def test_generated_consent_never_bypasses_roots_excludes_gitignore_or_symlinks(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    outside = _write(tmp_path, "outside/out.py")
    for relative in ["src/keep.py", "src/generated/keep.py", "src/generated/drop.py", "src/generated/ignored.py", "other/generated/out.py", "src/vendor/no.py"]:
        _write(root, relative)
    (root / "src/link.py").symlink_to(outside)
    (root / "src/linked").symlink_to(outside.parent, target_is_directory=True)
    boundary = SourceBoundary(
        source_roots=("src", "../outside", "src/linked"),
        exclude_paths=("src/generated/drop.py",),
        gitignore_patterns=("src/generated/ignored.py",),
        code_files=("src/keep.py", "src/generated/keep.py"),
    )
    observed = _observe_source_reads(monkeypatch, tmp_path)
    rows = source_map.collect_project_source_facts(
        root, include_unmatched=True, include_generated=True, source_boundary=boundary,
    )
    assert [row["path"] for row in rows] == ["src/generated/keep.py", "src/keep.py"]
    snippets = source_map.build_project_source_evidence(
        root, requirements=["ArbitraryWidget"], include_generated=True, source_boundary=boundary,
    )
    assert {row["path"] for row in snippets} == {"src/generated/keep.py", "src/keep.py"}
    assert set(observed) == {"project/src/keep.py", "project/src/generated/keep.py"}
    for denied in (
        "src/generated/drop.py", "src/generated/ignored.py", "other/generated/out.py",
        "src/vendor/no.py", "src/link.py", "src/linked/out.py",
    ):
        observed.clear()
        mixed = replace(boundary, code_files=("src/keep.py", denied))
        assert source_map.collect_project_source_facts(
            root, include_unmatched=True, include_generated=True, source_boundary=mixed,
        ) == []
        assert source_map.build_project_source_evidence(
            root, requirements=["ArbitraryWidget"], include_generated=True, source_boundary=mixed,
        ) == []
        assert observed == {}






def test_ast_spans_original_bytes_and_new_unmatched_context_survive(tmp_path):
    text = "from pkg import Thing\r\n\r\nclass ArbitraryWidget:\r\n    def run(self):\r\n        return 'Привет Quux'\r\n"
    path = _write(tmp_path, "src/a.py", text)
    _declare_code_files(tmp_path, "src/a.py")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    cache = source_map.ProjectSourceFacts()
    rows = source_map.collect_project_source_facts(tmp_path, include_unmatched=True, source_facts=cache)
    row = rows[0]
    assert row["imports"] == ["pkg.Thing"]
    assert row["symbols"] == [
        {"kind": "class", "name": "ArbitraryWidget", "line_start": 3, "line_end": 5},
        {"kind": "method", "name": "run", "line_start": 4, "line_end": 5, "parent": "ArbitraryWidget"},
    ]
    assert row["line_start"] == 1 and row["line_end"] == 5
    assert "Привет Quux" in row["content"]
    assert row["matched_terms"] == [] and row["selection_score"] == 0
    row["symbols"].clear()
    assert source_map.collect_project_source_facts(tmp_path, include_unmatched=True, source_facts=cache)[0]["symbols"]
    assert project_state._documentation_gap_evidence(tmp_path, "Unseen") == [{"category": "source map", "paths": ["src/a.py"]}]
    assert path.read_bytes() == text.encode("utf-8")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_supported_extension_intersection_and_secret_scrubbing_remain(tmp_path):
    _write(tmp_path, "a.dart", "class ArbitraryWidget {}\nfinal password = 'private';\n")
    _write(tmp_path, "b.unsupported")
    boundary = SourceBoundary(include_extensions=(".dart", ".unsupported"), code_files=("a.dart",))
    rows = source_map.collect_project_source_facts(tmp_path, include_unmatched=True, source_boundary=boundary)
    assert [row["language"] for row in rows] == ["dart"]
    snippets = source_map.build_project_source_evidence(tmp_path, requirements=["password"], source_boundary=boundary)
    assert "[REDACTED]" in snippets[0]["snippet"] and "private" not in snippets[0]["snippet"]
    mixed = replace(boundary, code_files=("a.dart", "b.unsupported"))
    assert source_map.collect_project_source_facts(tmp_path, include_unmatched=True, source_boundary=mixed) == []
    assert source_map.build_project_source_evidence(tmp_path, requirements=["password"], source_boundary=mixed) == []




@pytest.mark.parametrize("question", ["", "Explain UnseenQuux", "Объясни НевидимыйКварк"])
def test_default_inspection_conditional_gap_remains_context_only(tmp_path, question):
    from docmancer.docs.application.project_context_service import ProjectContextService
    from docmancer.docs.models import ProjectDocsInspectResult, ProjectDocsResult, ProjectMetadata

    path = _write(tmp_path, "src/arbitrary.py")
    _declare_code_files(tmp_path, "src/arbitrary.py")
    before = path.read_bytes()
    seen = []

    class Facade:
        def read_project_metadata(self, project_path):
            return ProjectMetadata(project_path=project_path)

        def get_project_docs(self, project_path, query, **kwargs):
            seen.append(query)
            return ProjectDocsResult(project_path=project_path, query=query, results=[], answer_available=False)

        def inspect_project_docs(self, project_path):
            # Real inspection has no question parameter. It must not invent one.
            action = project_state.create_project_docs_next_action(tmp_path)
            assert "question" not in action["after"][1]["arguments_patch"]
            return ProjectDocsInspectResult(
                project_detected=True, project_path=project_path, reason_code="no_project_docs",
                recommended_next_actions=[action],
            )

    result = ProjectContextService(Facade()).get_project_context(
        str(tmp_path), question, mode="project-only", limit=8,
    )
    assert seen == [question]
    assert result.question == question
    assert result.answer_available is False
    assert result.support_decision.answer_supported is False
    assert result.answer_completeness["edit_ready"] is False
    action = next(item for item in result.next_actions if item.get("action") == "create_reviewable_project_doc")
    assert action["requires_confirmation"] is True
    assert action["documentation_gap"]["evidence_complete"] is False
    assert path.read_bytes() == before
    assert result.diagnostics["retrieval_routing"]["stages"]["repo_map"]["observed_item_count"] >= 1

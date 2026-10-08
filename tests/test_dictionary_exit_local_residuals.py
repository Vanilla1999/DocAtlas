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
@pytest.mark.parametrize("supplied", [False, True])
def test_role_suffix_never_promotes_literal_terms(suffix, supplied):
    terms = ["AlphaWidget", "Beta" + suffix, "GammaQuux", "DeltaProvider"]
    assert source_map._source_evidence_terms(
        question=" ".join(terms), requirements=terms if supplied else None,
    ) == terms


@pytest.mark.parametrize("supplied", [False, True])
def test_sixteen_term_budget_uses_stable_first_occurrence_not_roles(supplied):
    terms = [f"Literal{i}Quux" for i in range(16)] + ["LateService", "LateGate"]
    assert source_map._source_evidence_terms(
        question=" ".join(terms), requirements=terms if supplied else None,
    ) == terms[:16]


def test_literal_spelling_deduplication_and_exact_paths_remain_stable():
    assert source_map._source_evidence_terms(
        question="", requirements=["AlphaWidget", "alphawidget", "BetaService", "AlphaWidget"],
    ) == ["AlphaWidget", "BetaService"]
    assert source_map._source_evidence_terms(
        question="BetaService src/arbitrary.py", requirements=None,
    )[0] == "src/arbitrary.py"


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


@pytest.mark.parametrize("query", [None, "", "UnseenQuux", "НевидимыйКварк"])
def test_empty_or_unmatched_gap_has_context_without_synthetic_topic(tmp_path, query):
    _write(tmp_path, "a.py")
    _write(tmp_path, "z_architecture.py", "class Architecture: pass\n")
    _declare_code_files(tmp_path, "a.py", "z_architecture.py")
    evidence = project_state._documentation_gap_evidence(tmp_path, query)
    assert evidence == [{"category": "source map", "paths": ["a.py", "z_architecture.py"]}]
    facts = source_map.collect_project_source_facts(
        tmp_path, question=query or "", include_unmatched=True,
    )
    assert all(item["selection_score"] == 0 and item["matched_terms"] == [] for item in facts)
    assert source_map.build_project_repo_map(tmp_path, question=query or "") == []


@pytest.mark.parametrize("reason", ["no_project_docs", "architecture_doc_creation_recommended", "project_docs_ready"])
@pytest.mark.parametrize("query", ["", "  Explain Quux?\nKeep Beta  ", "Что делает Quux? Не изменяй Beta!"])
def test_all_structured_retry_emitters_keep_original_question(tmp_path, reason, query):
    action, confirmation, confirmation_reason, args, _, _ = project_state.project_docs_structured_next_action(
        reason_code=reason, root=tmp_path, query=query,
    )
    if reason == "project_docs_ready":
        assert action is None and confirmation is False
        assert args["question"] == query
    else:
        assert confirmation is True and confirmation_reason == "repo_write"
        assert action["after"][1]["arguments_patch"]["question"] == query
        assert action["documentation_gap"]["evidence_complete"] is False


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


@pytest.mark.parametrize("changes", [
    {"enabled": False}, {"max_scanned_files": 0}, {"max_scanned_bytes": 1},
    {"max_file_bytes": 1}, {"scan_deadline_seconds": 0},
    {"max_directory_depth": 0}, {"include_extensions": (".unsupported",)},
])
def test_parser_scan_caps_still_fail_closed_with_generated_consent(tmp_path, changes):
    _write(tmp_path, "src/generated/a.py")
    boundary = replace(SourceBoundary(), **changes)
    assert source_map.collect_project_source_facts(
        tmp_path, include_unmatched=True, include_generated=True, source_boundary=boundary,
    ) == []
    rows = source_map.build_project_source_evidence(
        tmp_path, requirements=["ArbitraryWidget"], include_generated=True, source_boundary=boundary,
    )
    assert all(row["evidence_class"] == "absent_in_source" and row["matched"] is False for row in rows)


def test_gap_honors_config_and_retains_six_file_deterministic_cap(tmp_path):
    for index in range(9):
        _write(tmp_path, f"src/{index}.py")
    _write(tmp_path, "other/out.py")
    _write(tmp_path, "src/generated/generated.py")
    (tmp_path / "docatlas.yaml").write_text("project:\n  source_roots: [src]\n", encoding="utf-8")
    _declare_code_files(tmp_path, *(f"src/{index}.py" for index in range(9)))
    all_facts = source_map.collect_project_source_facts(tmp_path, include_unmatched=True, max_files=9)
    assert [item["path"] for item in all_facts] == [f"src/{index}.py" for index in range(9)]
    assert project_state._documentation_gap_evidence(tmp_path, "") == [{
        "category": "source map", "paths": [f"src/{index}.py" for index in range(6)],
    }]
    assert source_map.collect_project_source_facts(
        tmp_path, include_unmatched=True,
        source_boundary=replace(SourceBoundary.from_project(tmp_path), code_files=("src/0.py", "other/out.py")),
    ) == []


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


@pytest.mark.parametrize("limit", [0, -1])
def test_nonpositive_output_budgets_do_not_open_empty_question_allpass(tmp_path, limit):
    _write(tmp_path, "a.py")
    assert source_map.collect_project_source_facts(tmp_path, include_unmatched=True, max_files=limit) == []
    assert source_map.collect_project_source_facts(tmp_path, include_unmatched=True, token_budget=limit) == []
    assert source_map.build_project_source_evidence(tmp_path, requirements=["ArbitraryWidget"], max_items=limit) == []


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

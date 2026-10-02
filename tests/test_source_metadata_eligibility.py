"""Metadata eligibility must not interpret the language of source prose."""
import pytest

from docmancer.docs.domain.evidence_qualification import (
    evidence_policy_rejection_reason,
    source_metadata_rejection_reason,
    qualify_evidence,
)
from docmancer.docs.domain.query_terms import documentation_query_terms


@pytest.mark.parametrize("text", [
    "The output includes citation metadata.",
    "Ответ включает метаданные цитат.",
    "La salida incluye los metadatos de las citas.",
    "出力には引用のメタデータが含まれます。",
    "يتضمن الإخراج بيانات الاستشهاد.",
])
@pytest.mark.parametrize("override, expected", [
    ({}, None),
    ({"project_identity": ""}, "missing_project_identity"),
    ({"project_identity": "other"}, "wrong_project_identity"),
    ({"stale": True}, "stale_evidence"),
    ({"freshness": "stale"}, "stale_evidence"),
    ({"index_freshness": "pending"}, "unsynchronized_index"),
    ({"risk_flags": ["unsafe"]}, "unsafe_evidence"),
    ({"lifecycle_status": "superseded"}, "lifecycle_not_allowed"),
])
def test_metadata_guards_are_independent_of_visible_language(text, override, expected):
    candidate = {"project_identity": "project", "source_class": "project_doc", **override}
    kwargs = {"candidate": candidate, "expected_project_identity": "project"}
    assert source_metadata_rejection_reason(**kwargs) == expected
    assert evidence_policy_rejection_reason({}, visible_text=text, **kwargs) == expected


def test_legacy_exclusions_and_guard_precedence_are_preserved():
    probe = {"forbidden_evidence_terms": ["budget"]}
    assert evidence_policy_rejection_reason(
        probe, visible_text="BUDGET", candidate={"stale": True},
    ) == "stale_evidence"
    assert evidence_policy_rejection_reason(probe, visible_text="BUDGET") == "forbidden_evidence_term"
    assert evidence_policy_rejection_reason(
        {}, visible_text="text", catalog_role="historical",
        forbidden_catalog_roles=("historical",),
    ) == "forbidden_catalog_role"


def test_optional_metadata_and_explicit_history_keep_existing_contract():
    assert source_metadata_rejection_reason() is None
    assert source_metadata_rejection_reason(
        candidate={"lifecycle_status": "superseded"}, lifecycle_intent="historical",
    ) is None


def test_query_terms_preserve_non_latin_scripts_and_accents():
    for question, expected in (
        ("presupuesto además documentación", ("presupuesto", "además", "documentación")),
        ("出力には引用のメタデータが含まれます", ("出力には引用のメタデータが含まれます",)),
        ("ميزانية الإجابة", ("ميزانية", "الإجابة")),
        ("budget 引用メタデータ ميزانية", ("budget", "引用メタデータ", "ميزانية")),
    ):
        assert documentation_query_terms(question) == expected


def test_query_terms_preserve_existing_technical_token_spellings():
    assert documentation_query_terms("--max-tokens api.value path/to/file.md") == (
        "--max-tokens", "api.value", "path/to/file.md",
    )


def test_visible_qualification_preserves_unicode_fallback_terms():
    for term in ("documentación", "引用メタデータ", "ميزانية"):
        result = qualify_evidence(
            {"query_text": term}, query_id="query-original",
            visible_text=f"{term} details are available.",
        )
        assert term in result.trace.get("body_matched_terms", ()), result


def test_independent_host_lookup_preserves_unicode_distinctive_terms():
    from docmancer.docs.application.context_query_probes import independent_query_probes

    for term in ("documentación", "引用メタデータ", "ميزانية"):
        matches = independent_query_probes(
            {"snippet": f"{term} details are available."},
            {"queries": [
                {"query_id": "query-original", "origin": "original", "text": "unrelated"},
                {"query_id": "query-lookup-1", "origin": "host_lookup", "text": term},
            ]},
        )
        assert "query-lookup-1" in matches, (term, matches)
        shared_plan = {"queries": [
            {"query_id": "query-original", "origin": "original", "text": term},
            {"query_id": "query-lookup-1", "origin": "host_lookup", "text": term},
        ]}
        shared_matches = independent_query_probes(
            {"snippet": f"{term} details are available."}, shared_plan,
        )
        assert "query-lookup-1" not in shared_matches
        unrelated_matches = independent_query_probes(
            {"snippet": "Unrelated details are available."}, shared_plan,
        )
        assert "query-lookup-1" not in unrelated_matches


def test_unicode_query_focus_selects_source_local_window():
    from docmancer.docs.domain.context_windows import _focused_snippet

    for term in ("documentación", "引用メタデータ", "ميزانية"):
        text = "Background information is unrelated. " * 12
        witness = f"{term} includes the citation metadata."
        text += witness + " More unrelated information follows." * 12
        snippet, start, end = _focused_snippet(text, (term,), limit=100)
        assert witness in snippet, (term, snippet)
        assert snippet == text[start:end]
        assert len(snippet) <= 100


def test_window_focus_has_no_language_specific_stopwords():
    from docmancer.docs.domain.context_windows import _query_terms

    assert _query_terms(("project проект works работает",)) == {
        "project", "проект", "works", "работает",
    }


def test_public_read_library_and_patch_branches_remain_separate(monkeypatch):
    from docmancer.docs.interfaces.mcp import context_tools
    from tests.docs.test_patch_context_public import _Facade

    calls = []
    context_projection = context_tools.project_docs_context
    answer_projection = context_tools.project_docs_answer

    def context(**kwargs):
        calls.append("context")
        return context_projection(**kwargs)

    def answer(**kwargs):
        calls.append("answer")
        return answer_projection(**kwargs)

    monkeypatch.setattr(context_tools, "project_docs_context", context)
    monkeypatch.setattr(context_tools, "project_docs_answer", answer)

    class Facade(_Facade):
        def get_docs_context(self, question, **kwargs):
            result = super().get_docs_context(question, **kwargs)
            result["mode_selected"] = "dependency" if kwargs.get("library") else "project"
            assert kwargs["allow_network"] is False
            assert kwargs["prepare_project_docs"] is False
            return result

    for question, extra, kind, expected in (
        ("Explain project architecture.", {}, "docs_context", ["context"]),
        ("Explain API usage.", {"library": "example"}, "docs_answer", ["answer"]),
        ("Fix MissingPermissionGate.", {}, "patch_context", []),
    ):
        calls.clear()
        result = context_tools.handle_context_tool(
            "get_docs_context", {"question": question, "project_path": "/repo", **extra},
            Facade([]),
        )
        assert result["kind"] == kind
        assert calls == expected
        assert not result.get("edit_ready", False)


def test_optional_lookup_filter_is_structural_not_language_vocabulary():
    from docmancer.docs.domain.query_terms import supplemental_query_is_useful

    for text in ("which", "happens", "должен", "ميزانية", "引用メタデータ"):
        assert supplemental_query_is_useful(text)
    for text in ("", "   ", "?!", "I a in so", "в от", "по"):
        assert not supplemental_query_is_useful(text)
    for text in ("--if", "pubspec.lock", "ns.lookup_context"):
        assert supplemental_query_is_useful(text)
    from types import SimpleNamespace
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan

    question = (
        "What happens in offline mode when the documentation needed for a question "
        "has not been prefetched or indexed yet?"
    )
    for text in ("happens", "должен", "ميزانية", "引用メタデータ"):
        plan = build_documentation_query_plan(
            question, requirements=SimpleNamespace(
                concept_queries=(text,), retrieval_hints=("ALPHA_KEY",),
            ),
        )
        assert any(q.query_id.startswith("query-relation-") for q in plan.queries)
        assert not any(q.text == text for q in plan.queries)
        assert any(q.text == "ALPHA_KEY" for q in plan.queries)

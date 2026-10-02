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


def test_public_read_library_and_patch_branches_remain_separate(monkeypatch, tmp_path):
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
            self.received_question = question
            result = super().get_docs_context(question, **kwargs)
            result["mode_selected"] = "dependency" if kwargs.get("library") else "project"
            assert kwargs["allow_network"] is False
            assert kwargs["prepare_project_docs"] is False
            return result

    for question, extra, kind, expected in (
        ("Explain project architecture.", {}, "docs_context", ["context"]),
        ("Explain API usage.", {"library": "example"}, "docs_answer", ["answer"]),
        ("Fix MissingPermissionGate.", {}, "docs_context", ["context"]),
        ("Fix MissingPermissionGate.", {"request_intent": "change"}, "patch_context", []),
        ("Fix MissingPermissionGate.", {"request_intent": "read"}, "docs_context", ["context"]),
        ("修正してください", {"request_intent": "change"}, "patch_context", []),
        ("اعرض الوثائق التاريخية", {"request_intent": "read", "lifecycle_intent": "historical"}, "docs_context", ["context"]),
        ("  引用のメタデータ？\n", {"request_intent": "read"}, "docs_context", ["context"]),
    ):
        calls.clear()
        facade = Facade([])
        result = context_tools.handle_context_tool(
            "get_docs_context", {"question": question, "project_path": "/repo", **extra},
            facade,
        )
        assert facade.received_question == question
        assert result["kind"] == kind
        assert calls == expected
        assert not result.get("edit_ready", False)
    for extra, reason in (
        ({"request_intent": "execute"}, "invalid_request_intent"),
        ({"lifecycle_intent": "latest"}, "invalid_lifecycle_intent"),
        ({"lifecycle_intent": "historical", "library": "example"}, "invalid_lifecycle_scope"),
    ):
        result = context_tools.handle_context_tool(
            "get_docs_context", {"question": "Question", "project_path": "/repo", **extra}, Facade([]),
        )
        assert result["error"]["reason_code"] == reason
    from tests.docs._shared_test_project_context_service import FakeProjectContextFacade
    from docmancer.docs.application.project_context_service import ProjectContextService

    for question in ("اعرض الوثائق التاريخية", "過去の文書を表示", "Muestra documentos históricos"):
        for lifecycle in ("current", "historical", "either"):
            facade = FakeProjectContextFacade()
            result = ProjectContextService(facade).get_project_context(
                "/repo", question, mode="project-only", request_intent="read",
                lifecycle_intent=lifecycle,
            )
            call = next(row for row in facade.calls if row[0] == "project")
            assert call[2] == question
            assert call[3]["requirements"].lifecycle_intent == lifecycle
            assert call[3]["documentation_query_plan"].original_question == question
            assert result.requirements.lifecycle_intent == lifecycle
            from types import SimpleNamespace
            from docmancer.core.config import DocmancerConfig
            from docmancer.docs.application.project_docs_service import ProjectDocsService
            from docmancer.docs.domain.lifecycle_policy import lifecycle_filters_for_intent

            backend_calls = []
            agent = SimpleNamespace(
                config=DocmancerConfig(),
                query=lambda text, **kwargs: backend_calls.append((text, kwargs)) or [],
            )
            service = ProjectDocsService(SimpleNamespace(_agent_instance=lambda: agent))
            service.query_project_docs(
                str(tmp_path), question, requirements=result.requirements,
                documentation_query_plan=call[3]["documentation_query_plan"],
                tokens=800, limit=3,
            )
            assert backend_calls
            expected_filters = lifecycle_filters_for_intent(lifecycle)
            for _, kwargs in backend_calls:
                assert kwargs["filters"].get("lifecycle_status") == expected_filters.get("lifecycle_status")
    # Direct callers without requirements cannot infer history or extra probes
    # from the question, even when it contains an old EN/RU intent phrase.
    for question in ("Show historical documentation", "Покажи архивную документацию", "  過去の文書\n"):
        backend_calls.clear()
        service.query_project_docs(str(tmp_path), question, tokens=800, limit=3)
        assert len(backend_calls) == 2  # original and authority-filtered original
        assert all(text == question for text, _ in backend_calls)
        assert all(kwargs["filters"].get("lifecycle_status") ==
                   lifecycle_filters_for_intent("current").get("lifecycle_status")
                   for _, kwargs in backend_calls)
    from docmancer.docs.application.unified_context_service import UnifiedDocsContextService

    class RoutedFacade(FakeProjectContextFacade):
        def get_project_context(self, *args, **kwargs):
            self.forwarded = kwargs
            return ProjectContextService(self).get_project_context(*args, **kwargs)

    routed = RoutedFacade()
    routed.unified_context = UnifiedDocsContextService(routed)
    payload = context_tools.handle_context_tool(
        "get_docs_context", {
            "question": "اعرض الوثائق التاريخية", "project_path": "/repo",
            "request_intent": "read", "lifecycle_intent": "historical",
        }, routed,
    )
    assert routed.forwarded["request_intent"] == "read"
    assert routed.forwarded["lifecycle_intent"] == "historical"
    assert payload["kind"] == "docs_context"
    assert not payload.get("edit_ready", False)


def test_optional_lookup_filter_is_structural_not_language_vocabulary(monkeypatch):
    from docmancer.docs.domain.query_terms import supplemental_query_is_useful

    for text in ("which", "happens", "должен", "ميزانية", "引用メタデータ"):
        assert supplemental_query_is_useful(text)
    for text in ("", "   ", "?!", "I a in so", "в от", "по"):
        assert not supplemental_query_is_useful(text)
    for text in ("--if", "pubspec.lock", "ns.lookup_context"):
        assert supplemental_query_is_useful(text)
    from types import SimpleNamespace
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan

    from docmancer.docs.domain import documentation_query_plan as planning
    from docmancer.docs.application import need_query_schedule as scheduling

    assert not hasattr(planning, "build_project_retrieval_aliases")
    assert not hasattr(scheduling, "compile_need_contracts")
    for question in ("  引用メタデータ `ALPHA_KEY`？\n", "ميزانية `ALPHA_KEY`", "¿Qué incluye `ALPHA_KEY`?"):
        plan = planning.build_documentation_query_plan(
            question, lookup_queries=("budget citation metadata", "预算"),
            explicit_path="docs/settings.md",
            requirements=SimpleNamespace(concept_queries=("guessed need",)),
        )
        scheduled, probes = scheduling.scheduled_plan(plan)
        assert scheduled == plan
        assert plan.original_question == question
        assert plan.queries[0].text == question
        assert any(q.text == "ALPHA_KEY" and q.origin == "exact_anchor" for q in probes)
        assert any(q.text == "预算" and q.origin == "host_lookup" for q in probes)
        assert all(q.relation != "audited_rewrite" for q in plan.queries)
        assert all(q.public_parent_query_id is None for q in plan.queries if q.origin == "host_lookup")
        assert all(not q.forbidden_evidence_terms and not q.forbidden_catalog_roles for q in plan.queries)
        assert all(q.text != "guessed need" for q in probes)
        assert len(probes) <= 12

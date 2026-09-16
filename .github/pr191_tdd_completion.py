from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

BASE = "196da000edf28fcfea9718d5dd3d5f43ad857e39"
TEST_MODULE = "tests/docs/test_query_planning_completion_safety.py"
TEST_MANIFEST = "tests/diagnostic_labels.query_planning_completion.json"
V2_MODULE = "tests/docs/test_v2_acceptance_gaps.py"
V2_MANIFEST = "tests/diagnostic_labels.v2_acceptance_gaps.json"


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise AssertionError(f"{path}: expected one replacement, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def node_digest(module: str) -> str:
    tree = ast.parse(Path(module).read_text(encoding="utf-8"))
    nodes: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            nodes.append(f"{module}::{node.name}")
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for method in node.body:
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name.startswith("test_"):
                    nodes.append(f"{module}::{node.name}::{method.name}")
    return hashlib.sha256("\n".join(sorted(nodes)).encode()).hexdigest()


def write_tests() -> None:
    test_text = r'''from __future__ import annotations

import pytest

from docmancer.docs.application._docs_context_projection_core import _requalify_visible_source
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan


def _continuation_source(**candidate_overrides):
    candidate = {
        "project_identity": "project:test",
        "source_class": "project_doc",
        "freshness": "current",
        "index_freshness": "synchronized",
        "risk_flags": [],
        "lifecycle_status": "active",
    }
    candidate.update(candidate_overrides)
    return {
        "path_or_url": "docs/workflow.md",
        "section": "Workflow",
        "snippet": "continue locally while keeping the documentary claim unproved.",
        "catalog_role": "runbook",
        "retrieval_query_matches": {"query-intent-1": {
            "qualified": True,
            "relation": "host_lookup",
            "qualification_route": "same_atom_continuation",
            "coverage_kind": "derived",
            "coverage_kinds": ["derived"],
            "query_text": "insufficient evidence documentation workflow",
        }},
        "retrieval_query_ids": ["query-intent-1"],
        "_independent_query_plan": {"queries": [{
            "query_id": "query-intent-1",
            "text": "insufficient evidence documentation workflow",
            "origin": "canonical_intent",
        }]},
        "_qualification_candidate": candidate,
        "_expected_project_identity": "project:test",
        "_lifecycle_intent": "current",
    }


@pytest.mark.parametrize(("overrides", "reason"), [
    ({"project_identity": "project:other"}, "wrong_project_identity"),
    ({"stale": True}, "stale_evidence"),
    ({"index_freshness": "stale"}, "unsynchronized_index"),
    ({"risk_flags": ["untrusted"]}, "unsafe_evidence"),
    ({"lifecycle_status": "superseded"}, "lifecycle_not_allowed"),
])
def test_same_atom_continuation_rechecks_source_eligibility(overrides, reason):
    visible = _requalify_visible_source(
        _continuation_source(**overrides),
        query_text={
            "query-original": "What should the agent do if evidence is insufficient?",
            "query-intent-1": "insufficient evidence documentation workflow",
        },
    )
    trace = visible["retrieval_query_matches"]["query-intent-1"]
    assert trace["qualified"] is False
    assert trace["qualification_reason"] == reason
    assert "query-intent-1" not in visible["retrieval_query_ids"]


def test_safe_same_atom_continuation_still_survives_without_lexical_rematch():
    visible = _requalify_visible_source(
        _continuation_source(),
        query_text={
            "query-original": "What should the agent do if evidence is insufficient?",
            "query-intent-1": "insufficient evidence documentation workflow",
        },
    )
    trace = visible["retrieval_query_matches"]["query-intent-1"]
    assert trace["qualified"] is True
    assert trace["qualification_route"] == "same_atom_continuation"
    assert trace["coverage_kind"] == "derived"
    assert "query-original" not in visible["retrieval_query_ids"]


@pytest.mark.parametrize("condition", [
    "and the disk is full",
    "and the worktree is dirty",
    "and credentials are missing",
    "and a second repository has stale documentation",
])
def test_conditional_host_lookup_cannot_drop_an_additional_condition(condition):
    question = f"What should I do if project documentation is stale {condition}?"
    plan = build_documentation_query_plan(
        question,
        lookup_queries=("How do I diagnose stale documentation?",),
    )
    host = next(row for row in plan.queries if row.query_id == "query-lookup-1")
    assert host.relation == "host_lookup"
    assert host.public_parent_query_id is None


def test_reviewed_nonconditional_host_rewrite_still_derives_original_lineage():
    plan = build_documentation_query_plan(
        "Где хранится индекс и как он изолирован для каждого проекта?",
        lookup_queries=("project documentation storage index isolation",),
    )
    host = next(row for row in plan.queries if row.query_id == "query-lookup-1")
    assert host.relation == "audited_rewrite"
    assert host.public_parent_query_id == "query-original"
'''
    Path(TEST_MODULE).write_text(test_text, encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "module_labels": {TEST_MODULE: "behavioral"},
        "node_overrides": {},
        "module_node_hashes": {TEST_MODULE: node_digest(TEST_MODULE)},
    }
    Path(TEST_MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply_fix() -> None:
    # Source eligibility is orthogonal to lexical qualification. Factor the
    # policy gate so structurally-derived continuations can reuse it without
    # pretending their child text independently matches the query.
    replace_once(
        "docmancer/docs/domain/evidence_qualification.py",
        '''def qualify_evidence(\n    probe: Mapping[str, Any], *, query_id: str, visible_text: str,\n    evidence_text: str | None = None,\n    catalog_role: str = "", forbidden_catalog_roles: tuple[str, ...] = (),\n    forbidden_evidence_terms: tuple[str, ...] = (),\n    candidate: Mapping[str, Any] | None = None,\n    expected_project_identity: str | None = None,\n    lifecycle_intent: LifecycleIntent = "current",\n) -> EvidenceQualification:\n    """Qualify one retrieval probe against evidence visible to the model."""\n    result = dict(probe)\n    if candidate is not None or expected_project_identity:\n        candidate = candidate or {}\n        identity = str(candidate.get("project_identity") or "").strip()\n        if (expected_project_identity or candidate.get("source_class") == "project_doc") and not identity:\n            return _rejected(result, "missing_project_identity")\n        if expected_project_identity and identity != expected_project_identity:\n            return _rejected(result, "wrong_project_identity")\n        if candidate.get("stale") or str(candidate.get("freshness") or "current") != "current":\n            return _rejected(result, "stale_evidence")\n        if str(candidate.get("index_freshness") or "synchronized") != "synchronized":\n            return _rejected(result, "unsynchronized_index")\n        if candidate.get("risk_flags"):\n            return _rejected(result, "unsafe_evidence")\n        if not lifecycle_allows(candidate, lifecycle_intent):\n            return _rejected(result, "lifecycle_not_allowed")\n    normalized_visible = visible_text.casefold()\n    forbidden_terms = tuple(dict.fromkeys((\n        *(str(value) for value in probe.get("forbidden_evidence_terms") or ()),\n        *forbidden_evidence_terms,\n    )))\n    forbidden_roles = set(str(value) for value in (\n        *(probe.get("forbidden_catalog_roles") or ()),\n        *forbidden_catalog_roles,\n    ))\n    if any(str(term).casefold() in normalized_visible for term in forbidden_terms):\n        return _rejected(result, "forbidden_evidence_term")\n    if catalog_role and catalog_role in forbidden_roles:\n        return _rejected(result, "forbidden_catalog_role")\n    body = evidence_text if evidence_text is not None else visible_text''',
        '''def evidence_policy_rejection_reason(\n    probe: Mapping[str, Any], *, visible_text: str, catalog_role: str = "",\n    forbidden_catalog_roles: tuple[str, ...] = (),\n    forbidden_evidence_terms: tuple[str, ...] = (),\n    candidate: Mapping[str, Any] | None = None,\n    expected_project_identity: str | None = None,\n    lifecycle_intent: LifecycleIntent = "current",\n) -> str | None:\n    """Return the source/policy rejection independently of lexical matching."""\n    if candidate is not None or expected_project_identity:\n        candidate = candidate or {}\n        identity = str(candidate.get("project_identity") or "").strip()\n        if (expected_project_identity or candidate.get("source_class") == "project_doc") and not identity:\n            return "missing_project_identity"\n        if expected_project_identity and identity != expected_project_identity:\n            return "wrong_project_identity"\n        if candidate.get("stale") or str(candidate.get("freshness") or "current") != "current":\n            return "stale_evidence"\n        if str(candidate.get("index_freshness") or "synchronized") != "synchronized":\n            return "unsynchronized_index"\n        if candidate.get("risk_flags"):\n            return "unsafe_evidence"\n        if not lifecycle_allows(candidate, lifecycle_intent):\n            return "lifecycle_not_allowed"\n    normalized_visible = visible_text.casefold()\n    forbidden_terms = tuple(dict.fromkeys((\n        *(str(value) for value in probe.get("forbidden_evidence_terms") or ()),\n        *forbidden_evidence_terms,\n    )))\n    forbidden_roles = set(str(value) for value in (\n        *(probe.get("forbidden_catalog_roles") or ()),\n        *forbidden_catalog_roles,\n    ))\n    if any(str(term).casefold() in normalized_visible for term in forbidden_terms):\n        return "forbidden_evidence_term"\n    if catalog_role and catalog_role in forbidden_roles:\n        return "forbidden_catalog_role"\n    return None\n\n\ndef qualify_evidence(\n    probe: Mapping[str, Any], *, query_id: str, visible_text: str,\n    evidence_text: str | None = None,\n    catalog_role: str = "", forbidden_catalog_roles: tuple[str, ...] = (),\n    forbidden_evidence_terms: tuple[str, ...] = (),\n    candidate: Mapping[str, Any] | None = None,\n    expected_project_identity: str | None = None,\n    lifecycle_intent: LifecycleIntent = "current",\n) -> EvidenceQualification:\n    """Qualify one retrieval probe against evidence visible to the model."""\n    result = dict(probe)\n    policy_reason = evidence_policy_rejection_reason(\n        probe, visible_text=visible_text, catalog_role=catalog_role,\n        forbidden_catalog_roles=forbidden_catalog_roles,\n        forbidden_evidence_terms=forbidden_evidence_terms, candidate=candidate,\n        expected_project_identity=expected_project_identity, lifecycle_intent=lifecycle_intent,\n    )\n    if policy_reason is not None:\n        return _rejected(result, policy_reason)\n    body = evidence_text if evidence_text is not None else visible_text''',
    )
    replace_once(
        "docmancer/docs/domain/evidence_qualification.py",
        '''    "EvidenceQualification",\n    "derived_parent_trace",\n    "qualify_evidence",''',
        '''    "EvidenceQualification",\n    "derived_parent_trace",\n    "evidence_policy_rejection_reason",\n    "qualify_evidence",''',
    )

    replace_once(
        "docmancer/docs/application/_docs_context_projection_core.py",
        '''from docmancer.docs.domain.evidence_qualification import (\n    derived_parent_trace,\n    qualify_evidence,\n)''',
        '''from docmancer.docs.domain.evidence_qualification import (\n    derived_parent_trace,\n    evidence_policy_rejection_reason,\n    qualify_evidence,\n)''',
    )
    replace_once(
        "docmancer/docs/application/_docs_context_projection_core.py",
        '''        if (\n            query_id != "query-original"\n            and trace.get("qualified") is True\n            and trace.get("qualification_route") == "same_atom_continuation"\n            and trace.get("coverage_kind") == "derived"\n        ):\n            matches = merge_query_matches(matches, {str(query_id): dict(trace)})\n            continue''',
        '''        if (\n            query_id != "query-original"\n            and trace.get("qualified") is True\n            and trace.get("qualification_route") == "same_atom_continuation"\n            and trace.get("coverage_kind") == "derived"\n        ):\n            continuation_trace = dict(trace)\n            policy_reason = evidence_policy_rejection_reason(\n                trace,\n                visible_text=visible_text,\n                catalog_role=str(source.get("catalog_role") or ""),\n                candidate=source.get("_qualification_candidate", source),\n                expected_project_identity=source.get("_expected_project_identity"),\n                lifecycle_intent=source.get("_lifecycle_intent", "current"),\n            )\n            if policy_reason is not None:\n                continuation_trace.update(\n                    qualified=False, qualification_reason=policy_reason,\n                )\n            matches = merge_query_matches(\n                matches, {str(query_id): continuation_trace},\n            )\n            continue''',
    )

    # A conditional troubleshooting original is not equivalent merely because
    # both strings map to the same broad intent. Only the already-reviewed
    # stale-or-no-results frame may retain the historical compatibility route;
    # extra conditions remain ordinary host lookups.
    helper = r'''
_REVIEWED_CONDITIONAL_TROUBLESHOOTING_RE = re.compile(
    r"(?:"
    r"(?:what\s+should\s+i\s+check|what\s+do\s+i\s+check|how\s+(?:do|should)\s+i\s+troubleshoot)"
    r"\s*,?\s*(?:if|when)\s+(?:(?:the|my|project|repository)\s+){0,3}"
    r"documentation\s+(?:is\s+)?(?:stale|outdated)\s+(?:or|and)\s+"
    r"(?:nothing(?:\s+is)?\s+found|no\s+results(?:\s+are)?\s+found|search\s+returns\s+no\s+results)"
    r"|(?:что\s+проверить|как\s+диагностировать)\s*,?\s*(?:если|когда)\s+"
    r"(?:(?:проектн\w*|репозиторн\w*)\s+)?документац\w*\s+устар\w*\s+"
    r"(?:или|и)\s+(?:ничего\s+не\s+находится|ничего\s+не\s+найдено|нет\s+результатов)"
    r")\s*[?!.]*\s*$",
    re.I,
)


def _reviewed_conditional_troubleshooting_frame(question: str) -> bool:
    return _REVIEWED_CONDITIONAL_TROUBLESHOOTING_RE.fullmatch(question) is not None


'''
    replace_once(
        "docmancer/docs/domain/documentation_query_plan.py",
        "def _host_lookup_can_derive_original(\n",
        helper + "def _host_lookup_can_derive_original(\n",
    )
    replace_once(
        "docmancer/docs/domain/documentation_query_plan.py",
        '''    conditional_troubleshooting = (\n        bool(_CONDITIONAL_SURFACE_RE.search(original_question))\n        and original_intents == {"troubleshooting"}\n        and bool(original_aliases)\n        and all(alias.force_context_only for alias in original_aliases)\n        and not technical_anchors(original_question)\n        and not _HOST_NEGATION_RE.search(original_question)\n        and not _UNVERIFIED_PREMISE_RE.search(original_question)\n        and not _NOVEL_TOPIC_QUALIFIER_RE.search(original_question)\n    )''',
        '''    conditional_troubleshooting = (\n        _reviewed_conditional_troubleshooting_frame(original_question)\n        and original_intents == {"troubleshooting"}\n        and bool(original_aliases)\n        and all(alias.force_context_only for alias in original_aliases)\n        and not technical_anchors(original_question)\n        and not _HOST_NEGATION_RE.search(original_question)\n        and not _UNVERIFIED_PREMISE_RE.search(original_question)\n        and not _NOVEL_TOPIC_QUALIFIER_RE.search(original_question)\n    )''',
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("tests", "fix"))
    args = parser.parse_args()
    if args.mode == "tests":
        write_tests()
    else:
        apply_fix()
    print(f"completed {args.mode}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise AssertionError(f"{path}: expected exactly one replacement, got {text.count(old)}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(path: str, marker: str, addition: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if marker in text:
        raise AssertionError(f"{path}: marker already exists: {marker}")
    target.write_text(text.rstrip() + "\n\n\n" + addition.strip() + "\n", encoding="utf-8")


# 1. Relation-aware optional query grouping stays inside the existing four slots.
replace_once(
    "docmancer/docs/domain/documentation_query_plan.py",
    '''from docmancer.docs.domain.query_terms import (\n    documentation_exact_terms,\n    documentation_technical_anchors,\n    is_exact_technical_token,\n    supplemental_query_is_useful,\n)''',
    '''from docmancer.docs.domain.query_terms import (\n    documentation_exact_terms,\n    documentation_query_terms,\n    documentation_technical_anchors,\n    is_exact_technical_token,\n    supplemental_query_is_useful,\n)''',
)

relation_helper = r'''
def _subject_relation_groups(question: str) -> tuple[str, ...]:
    """Build bounded subject-bearing probes from relations already in the question.

    These are retrieval hypotheses only. They preserve user-provided subjects,
    conditions, and comparison axes without adding an expected outcome. The
    caller spends the existing optional-query slots on them before falling back
    to isolated lexical hints.
    """
    groups: list[str] = []

    def side_alternatives(value: str) -> tuple[str, ...]:
        """Expand one slash alternative while preserving the surrounding phrase."""
        match = re.search(r"\b([A-Za-z][A-Za-z0-9_-]*)\s*/\s*([A-Za-z][A-Za-z0-9_-]*)\b", value)
        if match is None:
            return (" ".join(value.split()),)
        prefix, suffix = value[:match.start()], value[match.end():]
        return tuple(dict.fromkeys(
            " ".join(f"{prefix}{choice}{suffix}".split())
            for choice in match.group(1, 2)
        ))

    # For a comparison, first keep both user-named sides in the same lexical
    # probe. This is the only shape that can directly retrieve a source that
    # contrasts the two domains. Remaining slots keep each side together with
    # all user-named comparison axes; no answer-side vocabulary is invented.
    comparison = re.match(
        r"^\s*how\s+do\s+(.+?)\s+and\s+(.+?)\s+differ(?:\s+in\s+(.+?))?[?.!]*\s*$",
        question,
        re.I,
    )
    if comparison is not None:
        left, right, axis = (value.strip(" ,;?.!") if value else "" for value in comparison.groups())
        left_variants = side_alternatives(left)
        right_variants = side_alternatives(right)
        axis_parts = [
            part.strip(" ,;?.!")
            for part in re.split(r"\s+(?:and|or)\s+", axis, flags=re.I)
            if part.strip(" ,;?.!")
        ] if axis else []
        axis_text = " ".join(axis_parts)
        for left_value in left_variants:
            for right_value in right_variants:
                value = f"{left_value} {right_value}".strip()
                if value and supplemental_query_is_useful(value):
                    groups.append(value[:500])
        for side in (left_variants[0], " ".join(re.sub(r"\s*/\s*", " ", right).split())):
            value = " ".join(part for part in (side, axis_text) if part).strip()
            if value and supplemental_query_is_useful(value):
                groups.append(value[:500])

    # Passive state alternatives are common in conditional questions. Preserve
    # the bounded subject phrase (not just its first noun) plus every user-named
    # state. This keeps "documentation needed ... not indexed" distinct from a
    # generic mention of already-indexed content.
    condition = re.search(r"\b(?:when|if)\s+(.+?)(?:[?.!]|$)", question, re.I)
    if condition is not None:
        value = condition.group(1).strip(" ,;?.!")
        state = re.match(
            r"(.+?)\s+(?:is|are|was|were|has\s+(?:not\s+)?been|have\s+(?:not\s+)?been)\s+"
            r"([A-Za-z][A-Za-z0-9_-]+)\s+(?:or|and)\s+([A-Za-z][A-Za-z0-9_-]+)(?:\s+yet)?$",
            value,
            re.I,
        )
        if state is not None:
            subject_terms = documentation_query_terms(state.group(1))
            subject = " ".join(subject_terms[:4])
            negated = bool(re.search(r"\bnot\b", value, re.I))
            for named_state in state.group(2, 3):
                probe = " ".join(part for part in (subject, "not" if negated else "", named_state) if part)
                if probe and supplemental_query_is_useful(probe):
                    groups.append(probe[:500])
        elif value and len(value.split()) >= 2 and supplemental_query_is_useful(value):
            groups.append(value[:500])

    return tuple(dict.fromkeys(groups))


'''
replace_once(
    "docmancer/docs/domain/documentation_query_plan.py",
    "def build_documentation_query_plan(\n",
    relation_helper + "def build_documentation_query_plan(\n",
)
replace_once(
    "docmancer/docs/domain/documentation_query_plan.py",
    '''    optional_queries = [\n        *((text, "retrieval_hint") for text in clause_groups),\n        *((text, "concept_alias") for applies, text in concept_queries if applies),\n        *((text, "concept_alias") for text in requirement_concepts),\n        *((text, "retrieval_hint") for text in requirement_hints),\n    ]''',
    '''    relation_groups = _subject_relation_groups(question)\n    optional_queries = [\n        # Relation groups are optional canonical search hypotheses so they can\n        # contribute useful broad context without deriving public coverage.\n        *((text, "canonical_intent") for text in relation_groups),\n        *((text, "retrieval_hint") for text in clause_groups),\n        *((text, "concept_alias") for applies, text in concept_queries if applies),\n        *((text, "concept_alias") for text in requirement_concepts),\n        *((text, "retrieval_hint") for text in requirement_hints),\n    ]''',
)
replace_once(
    "docmancer/docs/domain/documentation_query_plan.py",
    '''    origin_counts = {"concept_alias": 0, "retrieval_hint": 0}\n    for text, origin in optional_queries:''',
    '''    origin_counts = {"canonical_intent": 0, "concept_alias": 0, "retrieval_hint": 0}\n    for text, origin in optional_queries:''',
)
replace_once(
    "docmancer/docs/domain/documentation_query_plan.py",
    '''        origin_counts[origin] += 1\n        queries.append(DocumentationLookup(\n            f"query-{'concept' if origin == 'concept_alias' else 'hint'}-{origin_counts[origin]}",\n            text,''',
    '''        origin_counts[origin] += 1\n        prefix = (\n            "relation" if origin == "canonical_intent"\n            else "concept" if origin == "concept_alias" else "hint"\n        )\n        queries.append(DocumentationLookup(\n            f"query-{prefix}-{origin_counts[origin]}",\n            text,''',
)

# 2. A negative relation probe needs visible negation bound to its state term.
replace_once(
    "docmancer/docs/domain/evidence_qualification.py",
    '''    normalized_evidence = "\\n".join(substantive_lines).casefold()\n    normalized_headings = "\\n".join(heading_lines).casefold()\n\n    if str(probe.get("mode") or "") == "exact_path":''',
    '''    normalized_evidence = "\\n".join(substantive_lines).casefold()\n    normalized_headings = "\\n".join(heading_lines).casefold()\n\n    relation_text = str(probe.get("query_text") or "").casefold()\n    if query_id.startswith("query-relation-"):\n        negated_state = re.search(\n            r"(?<!\\w)(?:not|without|never|no)(?!\\w)\\s+([a-z][a-z0-9_-]{2,})\\s*$",\n            relation_text, re.I,\n        )\n        if negated_state is not None:\n            state = re.escape(negated_state.group(1))\n            if re.search(\n                rf"(?<!\\w)(?:not|without|never|no)(?!\\w)(?:\\s+\\w+){{0,2}}\\s+{state}(?!\\w)",\n                normalized_evidence, re.I,\n            ) is None:\n                return _rejected(result, "missing_visible_relation_negation")\n\n    if str(probe.get("mode") or "") == "exact_path":''',
)

# 3. Bare offline runtime queries must not spend bounded evidence on test/smoke docs.
replace_once(
    "docmancer/docs/domain/project_retrieval_intent.py",
    '''            rows.append(ProjectRetrievalAlias(\n                intent_id=intent_id,\n                text=text,\n                force_context_only=force_context_only,\n                source_language=language,\n                preferred_catalog_roles=preferred_roles,\n                forbidden_catalog_roles=forbidden_roles,\n                forbidden_evidence_terms=(\n                    "docs/adr/", "mcp pack commands", "packs mcp runtime",\n                    "install-pack", "packs-serve",\n                ) if intent_id in {\n                    "docs_mcp_workflow", "docs_mcp_server_command", "docs_mcp_public_tools",\n                    "docs_mcp_tool_policy", "fail_closed_workflow", "response_contract",\n                } else (),\n            ))''',
    '''            forbidden_terms = (\n                "docs/adr/", "mcp pack commands", "packs mcp runtime",\n                "install-pack", "packs-serve",\n            ) if intent_id in {\n                "docs_mcp_workflow", "docs_mcp_server_command", "docs_mcp_public_tools",\n                "docs_mcp_tool_policy", "fail_closed_workflow", "response_contract",\n            } else ()\n            if intent_id == "offline_usage" and not _has(tokens, "test", "pytest", "тест"):\n                forbidden_terms = tuple(dict.fromkeys(\n                    (*forbidden_terms, "pytest", "smoke", "fixture", "test suite")\n                ))\n            rows.append(ProjectRetrievalAlias(\n                intent_id=intent_id,\n                text=text,\n                force_context_only=force_context_only,\n                source_language=language,\n                preferred_catalog_roles=preferred_roles,\n                forbidden_catalog_roles=forbidden_roles,\n                forbidden_evidence_terms=forbidden_terms,\n            ))''',
)

# 4. A request verb by itself is not a useful supplemental lookup.
replace_once(
    "docmancer/docs/domain/query_terms.py",
    '''    "what", "which", "how", "when", "where", "why", "who", "should", "would",\n    "can", "could", "will", "shall", "must", "not", "only", "if", "unless", "without",''',
    '''    "what", "which", "how", "when", "where", "why", "who", "should", "would",\n    "happen", "happens", "happened",\n    "can", "could", "will", "shall", "must", "not", "only", "if", "unless", "without",''',
)

# 5. Preserve relation-group evidence and original heading identity through visible rerank.
replace_once(
    "docmancer/docs/application/context_candidate_ranking.py",
    '''        canonical_match_ratio = max((\n            float(trace.get("match_ratio") or 0.0)\n            for key, trace in (source.get("retrieval_query_matches") or {}).items()\n            if key in (canonical_query_ids or set())\n            and isinstance(trace, dict) and trace.get("qualified") is True\n        ), default=0.0)\n        direct_required_traces = [''',
    '''        canonical_match_ratio = max((\n            float(trace.get("match_ratio") or 0.0)\n            for key, trace in (source.get("retrieval_query_matches") or {}).items()\n            if key in (canonical_query_ids or set())\n            and isinstance(trace, dict) and trace.get("qualified") is True\n        ), default=0.0)\n        relation_group_traces = [\n            trace\n            for key, trace in (source.get("retrieval_query_matches") or {}).items()\n            if str(key).startswith("query-relation-")\n            and key in (canonical_query_ids or set())\n            and isinstance(trace, dict) and trace.get("qualified") is True\n        ]\n        # Relation groups are compact probes made only from the user's own\n        # comparison sides/axes or condition states. They are stronger visible\n        # relevance evidence than a generic topical hit against the full\n        # question, but remain retrieval-only and never derive public coverage.\n        relation_group_count = len(relation_group_traces)\n        relation_group_match_ratio = max((\n            float(trace.get("match_ratio") or 0.0) for trace in relation_group_traces\n        ), default=0.0)\n        relation_group_lexical = max((\n            float(trace.get("lexical_score") or 0.0) for trace in relation_group_traces\n        ), default=0.0)\n        comparison_relation_marker = 0\n        if relation_group_traces and re.search(\n            r"\\b(?:differ|difference|compare|versus|vs\\.?)\\b",\n            query_text.get("query-original", ""), re.I,\n        ):\n            relation_surface = " ".join(str(identity.get(key) or "") for key in (\n                "heading_path", "title", "snippet", "content",\n            ))\n            comparison_relation_marker = int(bool(re.search(\n                r"\\b(?:separate|different|differ|distinct|versus|vs\\.?|rather than|not the same)\\b",\n                relation_surface, re.I,\n            )))\n        direct_required_traces = [''',
)
replace_once(
    "docmancer/docs/application/context_candidate_ranking.py",
    '''        return (\n            condition_lead_priority(query_text.get("query-original", ""), str(source.get("snippet") or "")),\n            required_relation_preference,\n            host_condition_priority,''',
    '''        return (\n            condition_lead_priority(query_text.get("query-original", ""), str(source.get("snippet") or "")),\n            required_relation_preference,\n            comparison_relation_marker,\n            relation_group_count,\n            relation_group_match_ratio,\n            relation_group_lexical,\n            host_condition_priority,''',
)

# Regression assertions for the recovered first-losses.
replace_once(
    "tests/docs/test_query_planning_alias_regressions.py",
    '''    assert not any('test suite' in a.text or a.text == 'DOCATLAS_OFFLINE' for a in aliases)''',
    '''    assert not any('test suite' in a.text or a.text == 'DOCATLAS_OFFLINE' for a in aliases)\n    offline = next(a for a in aliases if a.intent_id == 'offline_usage')\n    assert {'pytest', 'smoke', 'fixture', 'test suite'} <= set(offline.forbidden_evidence_terms)''',
)
replace_once(
    "tests/docs/test_query_planning_alias_regressions.py",
    '''    assert any('offline mode' in a.text for a in aliases)\n    assert len(aliases) <= 4''',
    '''    assert any('offline mode' in a.text for a in aliases)\n    assert not all('smoke' in a.forbidden_evidence_terms for a in aliases if a.intent_id == 'offline_usage')\n    assert len(aliases) <= 4''',
)

append_once(
    "tests/docs/test_query_planning_budget_regressions.py",
    "test_comparison_uses_subject_bearing_side_probes_before_single_word_hints",
    r'''
def test_comparison_uses_subject_bearing_side_probes_before_single_word_hints():
    question = (
        "How do project documentation and dependency/library documentation differ "
        "in retrieval scope and provenance?"
    )
    requirements = build_requirements(question, profile="project_docs_answer")
    plan = build_documentation_query_plan(question, requirements=requirements)
    optional = [
        q for q in plan.queries
        if q.origin in {"canonical_intent", "concept_alias", "retrieval_hint", "component_rewrite"}
        and q.query_id.startswith(("query-relation-", "query-concept-", "query-hint-", "query-component-"))
    ]
    relation = [q.text.casefold() for q in optional if q.query_id.startswith("query-relation-")]

    assert len(optional) <= 4
    assert "project documentation dependency documentation" in relation
    assert "project documentation library documentation" in relation
    assert "project documentation retrieval scope provenance" in relation
    assert "dependency library documentation retrieval scope provenance" in relation
    assert not any(q.text.casefold() == "differ" for q in optional)


def test_conditional_relation_keeps_subject_and_negative_states_in_existing_slots():
    question = (
        "What happens in offline mode when the documentation needed for a question "
        "has not been prefetched or indexed yet?"
    )
    requirements = build_requirements(question, profile="project_docs_answer")
    plan = build_documentation_query_plan(question, requirements=requirements)
    relation = [
        q.text.casefold() for q in plan.queries if q.query_id.startswith("query-relation-")
    ]

    assert "documentation needed question not prefetched" in relation
    assert "documentation needed question not indexed" in relation
    assert not any(q.text.casefold() == "happens" for q in plan.queries)
    assert len([
        q for q in plan.queries
        if q.query_id.startswith(("query-relation-", "query-concept-", "query-hint-", "query-component-"))
    ]) <= 4
''',
)

append_once(
    "tests/docs/test_relation_preserving_projection.py",
    "test_negated_relation_probe_rejects_positive_only_evidence",
    r'''
def test_negated_relation_probe_rejects_positive_only_evidence():
    from docmancer.docs.domain.evidence_qualification import qualify_evidence

    probe = {
        "query_text": "documentation needed question not indexed",
        "query_terms": ["documentation", "needed", "question", "indexed"],
    }
    positive = qualify_evidence(
        probe, query_id="query-relation-1",
        visible_text="Documentation is indexed; failures must not be presented as answers.",
        evidence_text="Documentation is indexed; failures must not be presented as answers.",
    )
    negative = qualify_evidence(
        probe, query_id="query-relation-1",
        visible_text="Project documentation is not yet indexed for the question.",
        evidence_text="Project documentation is not yet indexed for the question.",
    )

    assert positive.qualified is False
    assert positive.reason == "missing_visible_relation_negation"
    assert negative.qualified is True


def test_user_relation_probe_beats_generic_topical_original_hit():
    from docmancer.docs.application.context_candidate_ranking import _facet_aware_candidates

    generic = {
        "path": "docs/index.md", "snippet": "Documentation index and provenance overview.",
        "retrieval_query_matches": {"query-original": {
            "qualified": True, "match_ratio": 0.6, "lexical_score": 20.0,
        }},
    }
    relation = {
        "path": "docs/workflow.md",
        "snippet": "Dependency documentation uses a separately bound retrieval scope.",
        "_qualification_candidate": {"heading_path": "Dependency docs are separate"},
        "retrieval_query_matches": {"query-relation-2": {
            "qualified": True, "match_ratio": 0.75, "lexical_score": 8.0,
        }},
    }
    ranked = _facet_aware_candidates(
        [generic, relation],
        query_text={
            "query-original": "How do project documentation and dependency documentation differ in scope?",
            "query-relation-2": "dependency documentation scope",
        },
        required_query_ids=set(), canonical_query_ids={"query-relation-2"},
    )
    assert ranked[0] is relation
''',
)

# Diagnostic manifests protect test-node identity, so regenerate from the actual final test files.
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


def refresh_manifest(path: str, modules: tuple[str, ...]) -> None:
    target = Path(path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    for module in modules:
        if module not in payload["module_node_hashes"]:
            raise AssertionError(f"{path}: missing module {module}")
        payload["module_node_hashes"][module] = node_digest(module)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


refresh_manifest(
    "tests/diagnostic_labels.query_planning.json",
    (
        "tests/docs/test_query_planning_budget_regressions.py",
        "tests/docs/test_query_planning_alias_regressions.py",
    ),
)
refresh_manifest(
    "tests/diagnostic_labels.query_planning_p5.json",
    ("tests/docs/test_relation_preserving_projection.py",),
)

print("Applied PR #191 final relation-selection patch")

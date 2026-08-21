#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.application.evidence_selection import build_requirements, project_docs_selection_config, select_evidence
from docmancer.docs.application.model_visible_projection import estimate_projection_tokens
from docmancer.docs.application.recovery import build_recovery_diagnosis, recovery_action
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload
from docmancer.retrieval.query_planning import extract_document_locator

TREASURE = (
    "What is the documented contract for adaptive treasure gem trip sampling across positions 1,2,3, "
    "including 200 completed probes per position, meet_type=6 counters, gold encounter handling, "
    "checkpoint persistence, winner selection, and ambiguous mutation handling?"
)
FIXED_WRAPPER = {"what", "does", "the", "project", "documentation", "say", "about", "according", "to", "it"}


def _decision(question: str, candidates: list[dict], *, profile: str = "project_docs_answer"):
    requirements = build_requirements(question, profile=profile)
    return select_evidence(
        candidates,
        question=question,
        config=project_docs_selection_config(800),
        requirements=requirements,
    )


def _assert_suggestion_integrity(original: str, suggestion: str) -> None:
    original_folded = original.casefold()
    suggestion_tokens = set(re.findall(r"[A-Za-zА-Яа-яЁё0-9_.:/=+-]+", suggestion.casefold()))
    invented = {
        token for token in suggestion_tokens
        if token not in FIXED_WRAPPER and token not in original_folded
    }
    if invented:
        raise AssertionError(f"rephrase invented domain tokens: {sorted(invented)!r}; {suggestion!r}")


def _service(root: Path) -> tuple[LibraryDocsService, Path]:
    os.environ["DOCMANCER_HOME"] = str(root / "home")
    project = root / "project"
    docs = project / "docs"
    docs.mkdir(parents=True)
    (docs / "ADAPTIVE_TREASURE_CONTRACT.md").write_text(
        """# Adaptive Treasure Contract

## Scope
Adaptive treasure trip sampling covers positions 1,2,3.

## Sampling
Each position uses 200 completed probes.

## Counters
meet_type uses value 6 for gem counters.

## Persistence
checkpoint persistence stores completed progress.

## Selection
winner selection chooses the sampled position.

## Recovery
ambiguous mutation handling stops before state mutation.

## Safety
gold encounter handling preserves the gold target.
""",
        encoding="utf-8",
    )
    (project / "ARCHITECTURE.md").write_text(
        "# Architecture\n\nThe project keeps domain contracts under docs/.\n",
        encoding="utf-8",
    )
    (project / "docatlas.project-docs.yaml").write_text(
        """schema_version: 1
documents:
  - path: docs/ADAPTIVE_TREASURE_CONTRACT.md
    role: development
    scope: project
    description: Adaptive treasure source-of-truth contract.
    authority: source_of_truth
    status: active
    impact: track
  - path: ARCHITECTURE.md
    role: project_architecture
    scope: project
    description: High-level project architecture.
    authority: source_of_truth
    status: active
    impact: track
""",
        encoding="utf-8",
    )
    config = DocmancerConfig()
    config.index.db_path = str(root / "docmancer.db")
    config.index.extracted_dir = str(root / "extracted")
    service = LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=DocmancerAgent(config=config),
        job_tracker=DocsJobTracker(),
    )
    sync = service.sync_project_docs(str(project), with_vectors=False)
    if sync.status != "success":
        raise AssertionError(sync)
    return service, project


def main() -> int:
    # 1. Real regression: parser implementation details become bounded recovery,
    # not a global edit prohibition.
    decision = _decision(TREASURE, [])
    diagnosis = build_recovery_diagnosis(TREASURE, decision)
    assert diagnosis["origin"] == "parsing", diagnosis
    assert diagnosis["reason_code"] == "question_parse_uncertain", diagnosis
    assert diagnosis["documentation_supported"] is False
    assert diagnosis["investigation_allowed"] is True
    assert diagnosis["hard_stop"] is False
    assert diagnosis["disposition"] == "rephrase_question", diagnosis
    suggestions = diagnosis.get("suggested_questions") or []
    assert 1 <= len(suggestions) <= 2
    for suggestion in suggestions:
        _assert_suggestion_integrity(TREASURE, suggestion)
    action = recovery_action(diagnosis, project_path="/repo", scope="project", mode="project")
    assert action and action["type"] == "rephrase_question"
    assert action["tool"] == "get_docs_context"
    assert action["auto_execute"] is False
    assert action["arguments_patch"]["question"] == suggestions[0]

    # 2. Unknown modifier fuzz: recovery must not depend on adding words to a
    # special stop-word dictionary.
    for index in range(100):
        nonce = f"zxqv{index}"
        question = f"What is the {nonce} contract for adaptive treasure sampling?"
        d = build_recovery_diagnosis(question, _decision(question, []))
        assert d["hard_stop"] is False, (question, d)
        assert d["origin"] in {"parsing", "retrieval", "selection"}, (question, d)

    # 3. Circuit breaker: one server-generated rephrase may not recursively
    # propose another rephrase.
    retried = suggestions[0]
    exhausted = build_recovery_diagnosis(retried, _decision(retried, []))
    assert exhausted["disposition"] == "search_local_source", exhausted
    assert exhausted["rephrase_exhausted"] is True
    exhausted_action = recovery_action(exhausted, project_path="/repo", mode="project")
    assert exhausted_action and exhausted_action["tool"] == "code_search"
    assert exhausted_action["repeat_docs_context"] is False

    # 4. Eligibility is a concrete evidence-state problem, not a wording problem.
    known = "What are the public tools of the Docs MCP server?"
    stale = _decision(known, [{
        "stable_id": "stale",
        "source": "README.md",
        "content": "The public tools are get_docs_context, prepare_docs, and docs_status.",
        "freshness": "stale",
    }])
    stale_diag = build_recovery_diagnosis(known, stale)
    assert stale_diag["origin"] == "eligibility", stale_diag
    assert stale_diag["disposition"] == "repair_evidence_state"
    assert "suggested_questions" not in stale_diag

    # 5. Documentation gaps are not disguised as parser/retrieval failures.
    navigation = _decision(known, [{
        "stable_id": "navigation",
        "source": "docs/index.md",
        "content": "See the API reference for the public tool inventory.",
        "navigation_only": True,
    }])
    nav_diag = build_recovery_diagnosis(known, navigation)
    assert nav_diag["origin"] == "source_documentation", nav_diag
    assert nav_diag["reason_code"] == "documentation_gap"
    assert nav_diag["disposition"] == "search_local_source"
    assert "suggested_questions" not in nav_diag

    # 6. Positive authoritative conflict is the hard-stop class.
    conflict = {
        "status": "insufficient_evidence",
        "metrics": {"candidate_count": 2, "eligible_count": 2, "selected_count": 0},
        "unresolved_conflicts": ["winner policy conflicts"],
        "support_decision": {
            "answer_supported": False,
            "mandatory_requirement_ids": ["winner"],
            "missing_requirement_ids": ["winner"],
        },
    }
    conflict_diag = build_recovery_diagnosis("What is the winner policy?", conflict)
    assert conflict_diag["origin"] == "conflict", conflict_diag
    assert conflict_diag["hard_stop"] is True
    assert conflict_diag["disposition"] == "resolve_authoritative_conflict"
    assert recovery_action(conflict_diag, project_path="/repo") is None

    # 7. Explicit locator grammar and exact indexed-source fallback. Force the
    # normal lexical lane to zero so success can only come from canonical stored
    # sections for the resolved source.
    locator_question = (
        "According to ADAPTIVE_TREASURE_CONTRACT.md, what does it say about meet_type?"
    )
    assert extract_document_locator(locator_question) == "ADAPTIVE_TREASURE_CONTRACT.md"
    exact_requirement_probe = build_requirements(
        "In docs/ADAPTIVE_TREASURE_CONTRACT.md, summarize meet_type.",
        required_evidence_paths=("docs/ADAPTIVE_TREASURE_CONTRACT.md",),
        profile="project_document_answer",
    )
    exact_mandatory = [item for item in exact_requirement_probe if item.mandatory]
    assert any(
        item.kind == "evidence_path"
        and item.value.casefold().replace("\\", "/") == "docs/adaptive_treasure_contract.md"
        for item in exact_mandatory
    ), exact_mandatory
    assert not any(
        item.kind == "exact_term"
        and "adaptive_treasure_contract.md" in item.value.casefold().replace("\\", "/")
        for item in exact_mandatory
    ), exact_mandatory
    assert any(
        item.kind == "exact_term" and item.value.casefold() == "meet_type"
        for item in exact_mandatory
    ), exact_mandatory
    locator_miss = build_recovery_diagnosis(
        locator_question,
        _decision(locator_question, [], profile="project_document_answer"),
    )
    assert locator_miss["disposition"] == "search_local_source", locator_miss
    assert locator_miss["rephrase_exhausted"] is True
    assert "suggested_questions" not in locator_miss

    # A first-time exact-path wording that is not the server-generated wrapper
    # may still offer one narrower facet retry. The locator itself must not be
    # reflected back as the requested semantic topic.
    initial_exact = "In docs/ADAPTIVE_TREASURE_CONTRACT.md, summarize meet_type."
    initial_diag = build_recovery_diagnosis(
        initial_exact,
        _decision(initial_exact, [], profile="project_document_answer"),
    )
    assert initial_diag["disposition"] == "rephrase_question", initial_diag
    initial_suggestions = initial_diag.get("suggested_questions") or []
    assert initial_suggestions, initial_diag
    assert "about meet_type" in initial_suggestions[0].casefold(), initial_suggestions
    assert "about adaptive_treasure_contract" not in initial_suggestions[0].casefold()
    with tempfile.TemporaryDirectory(prefix="docatlas-recovery-") as tmp:
        service, project = _service(Path(tmp))
        original_query = service.project_docs.query_project_docs
        service.project_docs.query_project_docs = lambda *args, **kwargs: []
        try:
            result = call_docs_tool_payload(
                "get_docs_context",
                {
                    "question": "In docs/ADAPTIVE_TREASURE_CONTRACT.md, summarize meet_type.",
                    "project_path": str(project),
                    "mode": "project",
                    "delivery_strategy": "bounded_direct",
                    "packet_tokens": 1500,
                },
                service,
            )
        finally:
            service.project_docs.query_project_docs = original_query
        assert result["status"] == "ok", json.dumps(result, indent=2, default=str)
        assert result["answer_supported"] is True
        assert result.get("recovery_reason_code") in (None, "")
        assert {row["path_or_url"] for row in result["sources"]} == {
            "docs/ADAPTIVE_TREASURE_CONTRACT.md"
        }
        assert all(
            "docs/adaptive_treasure_contract.md" not in row["path_or_url"]
            for row in result["sources"]
        )
        assert "meet_type" in result["answer"]

        # 8. Public parser recovery is bounded to the insufficient-evidence budget.
        parser_result = call_docs_tool_payload(
            "get_docs_context",
            {
                "question": TREASURE,
                "project_path": str(project),
                "mode": "project",
                "delivery_strategy": "bounded_direct",
                "packet_tokens": 1500,
            },
            service,
        )
        assert parser_result["status"] == "insufficient_evidence", parser_result
        assert parser_result["documentation_supported"] is False
        assert parser_result["investigation_allowed"] is True
        assert parser_result["hard_stop"] is False
        assert parser_result["recovery_origin"] == "parsing", parser_result
        recovery = parser_result.get("recommended_next_action") or {}
        assert recovery.get("type") == "rephrase_question", parser_result
        assert recovery.get("auto_execute") is False
        assert recovery.get("arguments_patch", {}).get("question")
        assert estimate_projection_tokens(parser_result) <= 300

    print(
        "PASS: parser/retrieval failures expose bounded non-automatic recovery; "
        "100 unknown contract modifiers do not create hard stops; rephrase is limited "
        "to one retry; eligibility/documentation/conflict classes remain distinct; "
        "exact indexed documents recover canonical stored sections when lexical retrieval misses; "
        "public insufficient projection stays <=300 tokens"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

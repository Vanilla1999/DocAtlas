"""Split tests from test_model_visible_projection.py; shared helpers remain in the façade module."""
from tests.docs import _shared_test_model_visible_projection as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})
from docmancer.docs.application.docs_context_projection import project_docs_context


def test_docs_selector_accounts_for_serialized_projection_cost():
    from docmancer.docs.application.evidence_selection import docs_selection_config, select_evidence

    candidates = [
        {
            "stable_id": f"source-{index}",
            "source": f"docs/source-{index}.md",
            "title": f"Source {index}",
            "relevance_score": 1.0 - index / 10,
            "content": " ".join(f"documented_{index}_{word}" for word in range(24)),
        }
        for index in range(1, 4)
    ]
    selection = select_evidence(
        candidates,
        question="Summarize the documented facts",
        config=docs_selection_config(800),
    )

    projection, snapshot = project_docs_answer(
        question="Summarize the documented facts",
        retrieval={"status": "success", "context_pack": candidates},
        canonical_selection=selection,
    )

    assert selection.status == "ok"
    assert len(selection.selected_candidates) < len(candidates)
    # Generic selection has no claim assignments and cannot become a docs answer.
    assert projection["status"] == "insufficient_evidence"
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []


def test_docs_context_prioritizes_required_query_over_optional_aliases():
    base = {
        "source_class": "project_doc", "heading_path": "Contract",
        "project_identity": "git:example/project", "lifecycle_status": "active",
        "freshness": "current", "index_freshness": "synchronized",
        "risk_flags": [], "doc_scope": "project",
    }
    projection, _snapshot = project_docs_context(retrieval={
        "context_pack": [
            {
                **base, "path": "roadmap/README.md", "authority": "source_of_truth",
                "content": "Optional aliases describe project contract documentation in planning notes.",
                "retrieval_query_matches": {
                    "query-concept-1": {"qualified": True, "lexical_score": 20.0},
                    "query-concept-2": {"qualified": True, "lexical_score": 20.0},
                },
            },
            {
                **base, "path": "docs/mcp-docs-server.md", "authority": "supporting",
                "content": "The response contract returns docs_answer or docs_context according to evidence support.",
                "retrieval_query_matches": {
                    "query-original": {"qualified": True, "lexical_score": 1.0},
                },
            },
        ],
        "documentation_query_plan": {
            "required_query_ids": ["query-original"],
            "query_ids": ["query-original", "query-concept-1", "query-concept-2"],
            "queries": [
                {"query_id": "query-original", "text": "What response contract is returned?", "origin": "original"},
                {"query_id": "query-concept-1", "text": "contract docs", "origin": "concept_alias"},
                {"query_id": "query-concept-2", "text": "answer protocol", "origin": "concept_alias"},
            ],
        },
    })
    assert projection["sources"][0]["path_or_url"] == "docs/mcp-docs-server.md"
    assert projection["query_coverage"] == "full"


def test_docs_context_ranks_equal_facet_candidates_deterministically():
    base = {
        "source_class": "project_doc", "project_identity": "git:example/project",
        "lifecycle_status": "active", "freshness": "current",
        "index_freshness": "synchronized", "risk_flags": [],
        "retrieval_query_matches": {
            "query-facet-1": {"qualified": True, "lexical_score": 1.0},
        },
    }
    projection, _ = project_docs_context(retrieval={
        "context_pack": [
            {**base, "path": "docs/supporting.md", "authority": "supporting", "content": "Supporting storage location documentation."},
            {**base, "path": "docs/canonical.md", "authority": "source_of_truth", "content": "Canonical storage location documentation."},
        ],
        "documentation_query_plan": {
            "original_question": "Where is storage located?",
            "required_query_ids": ["query-facet-1"],
            "queries": [{
                "query_id": "query-facet-1", "text": "storage location",
                "origin": "mandatory_facet", "facet_id": "facet-storage",
                "requirement_id": "requirement-storage",
            }],
        },
    })

    assert projection["status"] == "ok"
    assert projection["sources"][0]["path_or_url"] == "docs/canonical.md"


def test_docs_context_covered_facet_uses_only_assigned_witness():
    base = {
        "source_class": "project_doc", "project_identity": "git:example/project",
        "lifecycle_status": "active", "freshness": "current",
        "index_freshness": "synchronized", "risk_flags": [],
        "retrieval_query_matches": {
            "query-facet-1": {"qualified": True, "lexical_score": 1.0},
        },
    }
    projection, snapshot = project_docs_context(retrieval={
        "context_pack": [
            {**base, "stable_id": "lexical-only", "path": "docs/lexical.md", "content": "The storage location is discussed here but not proved."},
            {**base, "stable_id": "assigned", "path": "docs/proof.md", "content": "The exact project storage location is ~/.docatlas/projects/<hash>."},
        ],
        "selection_decision": {"assignments": [{
            "requirement_id": "requirement-storage", "evidence_id": "assigned",
        }]},
        "documentation_query_plan": {
            "original_question": "Where is storage located?",
            "required_query_ids": ["query-facet-1"],
            "queries": [{
                "query_id": "query-facet-1", "text": "storage location",
                "origin": "mandatory_facet", "facet_id": "facet-storage",
                "requirement_id": "requirement-storage",
            }],
        },
    })

    facet = projection["facets"][0]
    proof_source = next(
        source for source in projection["sources"]
        if source["path_or_url"] == "docs/proof.md"
    )
    assert facet["status"] == "covered"
    assert facet["evidence_ids"] == [proof_source["evidence_id"]]
    assert validate_model_visible_projection(
        projection, snapshot=snapshot, max_tokens=800,
    ) == []

def test_project_projection_materializes_every_selected_mandatory_witness():
    from docmancer.docs.application.evidence_selection import docs_selection_config, select_evidence

    question = "Summarize the policy period and implementation status"
    candidates = [
        {
            "stable_id": "policy-period",
            "source": "docs/plan.md",
            "title": "Policy period",
            "content": "The proposed policy period is 72 hours.",
        },
        {
            "stable_id": "implementation-status",
            "source": "docs/plan.md",
            "title": "Implementation status",
            "content": "This policy is not implemented and must be confirmed before implementation.",
        },
    ]
    selection = select_evidence(
        candidates,
        question=question,
        config=docs_selection_config(800),
        public_requirements=["72 hours", "not implemented"],
    )

    projection, snapshot = project_docs_answer(
        question=question,
        retrieval={"status": "success", "context_pack": candidates},
        canonical_selection=selection,
    )

    assert selection.support_decision.answer_supported is True
    assert projection["status"] == "ok"
    assert "proposed policy period is 72 hours" in projection["answer"]
    assert "not implemented and must be confirmed before implementation" in projection["answer"]
    assert projection["answer_evidence_ids"] == list(selection.support_decision.selected_evidence_ids)
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []


def test_explicit_answer_cannot_hide_a_selected_mandatory_witness():
    from docmancer.docs.application.evidence_selection import docs_selection_config, select_evidence

    question = "Summarize first fact and second fact"
    candidates = [
        {"stable_id": "first", "source": "docs/one.md", "content": "The first fact is enabled."},
        {"stable_id": "second", "source": "docs/two.md", "content": "The second fact is proposed."},
    ]
    selection = select_evidence(
        candidates,
        question=question,
        config=docs_selection_config(800),
        public_requirements=["first fact", "second fact"],
    )

    projection, _ = project_docs_answer(
        question=question,
        retrieval={
            "status": "success",
            "answer": "The first fact is enabled.",
            "context_pack": candidates,
        },
        canonical_selection=selection,
    )

    assert "The first fact is enabled." in projection["answer"]
    assert "The second fact is proposed." in projection["answer"]
    assert projection["answer_evidence_ids"] == ["first", "second"]


def test_docs_projection_exposes_a_compact_model_visible_support_summary():
    from docmancer.docs.application.evidence_selection import (
        library_docs_selection_config,
        select_evidence,
    )

    question = "Compare async with launch and explain how to obtain the async result"
    candidate = {"source": "docs/launch.md", "content": "launch starts fire-and-forget work."}
    selection = select_evidence(
        [candidate], question=question, config=library_docs_selection_config(800),
    )
    full_support = selection.support_decision.as_payload()
    support = {
        key: full_support[key]
        for key in (
            "answer_supported", "answer_available", "support_status", "reason_code",
            "missing_requirement_ids", "satisfied_requirement_ids",
            "mandatory_requirement_ids", "mandatory_coverage", "evidence_coverage",
            "selected_evidence_ids", "decision_hash",
        )
    }
    projection, _ = project_docs_answer(
        question=question,
        retrieval={
            "status": "success", "context_available": True,
            "answer_available": False, "selection_profile": "library_docs_answer",
            "selection_decision": selection, "context_pack": [candidate], **support,
        },
    )

    assert projection["status"] == "insufficient_evidence"
    assert {key: projection[key] for key in (
        "answer_supported", "answer_available", "support_status", "reason_code", "decision_hash",
    )} == {key: support[key] for key in (
        "answer_supported", "answer_available", "support_status", "reason_code", "decision_hash",
    )}
    assert "support_envelope" not in projection
    assert "missing_requirement_ids" not in projection


def test_supported_library_projection_shares_decision_and_visible_evidence_ids():
    from docmancer.docs.application.evidence_selection import (
        library_docs_selection_config,
        select_evidence,
    )

    question = "Compare create_task with gather and explain how the scheduled task result is obtained"
    candidate = {
        "stable_id": "runtime-witness",
        "source": "docs/runtime.md",
        "content": (
            "Compare create_task with gather; obtain the scheduled task result "
            "from create_task."
        ),
    }
    selection = select_evidence(
        [candidate],
        question=question,
        config=library_docs_selection_config(800),
    )

    projection, _ = project_docs_answer(
        question=question,
        retrieval={
            "status": "success",
            "answer_available": True,
            "selection_profile": "library_docs_answer",
            "selection_decision": selection,
            "context_pack": [candidate],
        },
    )

    selected_ids = list(selection.support_decision.selected_evidence_ids)
    assert projection["status"] == "ok"
    assert [source["evidence_id"] for source in projection["sources"]] == selected_ids
    assert projection["answer_evidence_ids"] == selected_ids
    assert projection["selected_evidence_ids"] == selected_ids


def test_tiny_budget_uses_a_compact_model_visible_support_summary():
    from docmancer.docs.application.evidence_selection import (
        library_docs_selection_config,
        select_evidence,
    )

    question = "Compare create_task with gather and explain how the scheduled task result is obtained"
    candidate = {
        "stable_id": "runtime-witness",
        "source": "docs/runtime.md",
        "content": (
            "Compare create_task with gather; obtain the scheduled task result "
            "from create_task."
        ),
    }
    selection = select_evidence(
        [candidate],
        question=question,
        config=library_docs_selection_config(800),
    )
    retrieval = {
        "status": "success",
        "answer_available": True,
        "selection_profile": "library_docs_answer",
        "selection_decision": selection,
        "context_pack": [candidate],
    }

    normal, _ = project_docs_answer(
        question=question, retrieval=retrieval, max_tokens=800,
    )
    tiny, _ = project_docs_answer(
        question=question, retrieval=retrieval, max_tokens=100,
    )
    expected_support = selection.support_decision.as_payload()

    assert {key: normal[key] for key in expected_support} == expected_support
    assert tiny["status"] == "insufficient_evidence"
    assert estimate_projection_tokens(tiny) <= 300
    assert validate_model_visible_projection(tiny, snapshot={}, max_tokens=300) == []
    assert tiny["decision_hash"] == expected_support["decision_hash"]
    assert tiny["answer_supported"] is False
    assert "support_envelope" not in tiny


def test_library_projection_materializes_display_text_only_witness():
    from docmancer.docs.application.evidence_selection import (
        library_docs_selection_config,
        select_evidence,
    )

    question = "Compare create_task with gather and explain how the scheduled task result is obtained"
    text = "Compare create_task with gather; obtain the scheduled task result from create_task."
    candidate = {
        "stable_chunk_id": "display-only-witness",
        "parent_logical_id": "runtime",
        "source": "docs/runtime.md",
        "display_text": text,
        "display_content_hash": __import__("hashlib").sha256(text.encode()).hexdigest(),
        "authority": "official",
        "docs_exactness": "exact",
        "version": "3.12",
        "retrieval_rank": 1,
        "score": 1.0,
    }
    selection = select_evidence(
        [candidate], question=question, config=library_docs_selection_config(800),
    )

    projection, snapshot = project_docs_answer(
        question=question,
        retrieval={
            "status": "success", "answer_available": True,
            "selection_profile": "library_docs_answer",
            "selection_decision": selection, "context_pack": [candidate],
        },
    )

    expected_ids = list(selection.support_decision.selected_evidence_ids)
    assert selection.support_decision.answer_supported is True
    assert [source["evidence_id"] for source in projection["sources"]] == expected_ids
    assert projection["answer_evidence_ids"] == expected_ids
    assert projection["selected_evidence_ids"] == expected_ids
    assert projection["sources"][0]["snippet"] == text
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []


def test_library_projection_does_not_add_language_specific_code_policy():
    from docmancer.docs.application.evidence_selection import (
        library_docs_selection_config,
        select_evidence,
    )

    question = "Show code comparing async with launch and explain how to obtain the async result"
    candidate = {
        "stable_id": "coroutine-witness", "source": "docs/coroutines.md",
        "content": "async differs from launch; obtain the async result with await().",
    }
    selection = select_evidence(
        [candidate], question=question, config=library_docs_selection_config(800),
    )
    projection, _ = project_docs_answer(
        question=question,
        retrieval={
            "status": "success", "answer_available": True,
            "selection_profile": "library_docs_answer",
            "selection_decision": selection, "context_pack": [candidate],
        },
    )

    assert "required_code_groups" not in projection


def test_generic_projection_retains_compact_canonical_evidence_id():
    projection, _ = project_docs_answer(
        question="What is the retry policy?",
        retrieval={
            "status": "success", "answer_available": True,
            "primary_snippet": {
                "stable_id": "selector-owned-long-stable-chunk-identifier",
                "source": "docs/retries.md", "content": "Retries are bounded.",
            },
        },
    )

    assert projection["sources"][0]["evidence_id"].startswith("ev-")


def test_patch_projection_binds_duplicate_path_sections_by_exact_evidence_id():
    evidence = [
        {
            "path": "src/a.py", "heading_path": "same", "source_class": "code_graph",
            "authority": "canonical", "instruction_trust": "scoped_agent_policy",
            "symbols": ["first"],
            "content": "Must preserve FIRST behavior.", "snippet": "FIRST",
        },
        {
            "path": "src/a.py", "heading_path": "same", "source_class": "code_graph",
            "authority": "canonical", "instruction_trust": "scoped_agent_policy",
            "symbols": ["second"],
            "content": "Must preserve SECOND behavior.", "snippet": "SECOND",
        },
    ]
    packet = build_action_packet(
        question="Fix src/a.py", context_pack=evidence, project_path="/repo",
    )
    assert packet["status"] == "ok"
    assert validate_action_packet(packet, evidence_items=evidence, project_path="/repo") == []

    projection, snapshot = project_patch_context(packet=packet, evidence_items=evidence)

    contents = [snapshot[row["evidence_id"]]["source"]["content"] for row in packet["source_of_truth"]]
    assert contents == ["Must preserve FIRST behavior.", "Must preserve SECOND behavior."]
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=1_500) == []

"""Public reads and required evidence paths never invent mutation authority."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace

import pytest

from docmancer.docs.application.action_packet import build_action_packet, validate_action_packet
from docmancer.docs.application._action_packet_part03 import build_action_packet as shard_packet
from docmancer.docs.application.model_visible_projection import (
    canonical_projection_bytes, validate_model_visible_projection,
)
from docmancer.docs.application.unified_context_service import UnifiedDocsContextService
from docmancer.docs.domain.mutation_intent import (
    MutationIntentContract, RequestedTarget, build_mutation_intent,
    evaluate_mutation_readiness, resolve_mutation_targets, with_explicit_path_targets,
)
from docmancer.docs.domain.request_intent import (
    _mask_non_top_level_text, _top_level_clause_spans, find_change_clause, is_change_request,
)
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.interfaces.mcp import context_tools as ingress
from tests.test_dictionary_exit_read_routing import ReadFacade


class PublicFacade(ReadFacade):
    def get_docs_context(self, question, **kwargs):
        self.calls.append(("public", question, kwargs))
        return UnifiedDocsContextService(self).get_docs_context(question, **kwargs)


@pytest.mark.parametrize("question", [
    "Delete src/config.py", "Create docs/README.md", "Rename src/a.py to src/b.py",
    "Please fix MarbleValve and implement tests", "Создай файл src/config.py",
    "First inspect. Then remove src/config.py", "```sh\nrm src/config.py\n```",
])
def test_text_cannot_construct_a_mutation_contract(question):
    contract = build_mutation_intent(question)
    assert contract.operation == "none" and contract.artifact_kind == "unknown"
    assert not contract.requested_targets and contract.request_plan is None
    assert not contract.acceptance_conditions and contract.destination is None
    assert not is_change_request(question) and find_change_clause(question) is None
    readiness = evaluate_mutation_readiness(contract)
    assert not readiness.ready and "mutation_intent_not_detected" in readiness.missing


def test_syntax_helpers_keep_offsets_without_semantic_inference():
    text = 'Inspect `src/a.py`.\n"Delete src/b.py"\n```py\ncreate()\n```\nRead now.'
    masked = _mask_non_top_level_text(text)
    assert len(masked) == len(text)
    assert [i for i, c in enumerate(text) if c == "\n"] == [i for i, c in enumerate(masked) if c == "\n"]
    assert "src/a.py" not in masked and "Delete" not in masked and "create" not in masked
    assert "Read now" in masked
    assert all(0 <= start < end <= len(text) for start, end in _top_level_clause_spans(masked))


@pytest.mark.parametrize("question", ["Delete src/config.py", "Create MarbleValve", "Fix MarbleValve", "  Fix MarbleValve  "])
def test_actual_public_facade_is_read_only_even_with_unknown_mutation_fields(tmp_path, question):
    facade = PublicFacade(tmp_path)
    result = ingress.handle_context_tool("get_docs_context", {
        "question": question, "project_path": str(tmp_path), "scope": "project",
        "mutation_intent": {"operation": "delete"}, "kind": "patch_context",
    }, facade)
    call = next(row for row in facade.calls if row[0] == "public")
    assert call[1] == question and "mutation_intent" not in call[2]
    assert call[2]["scope"] == "project"
    assert result.get("kind") != "patch_context"
    assert result.get("edit_ready", False) is False
    assert result.get("status") != "bad_request", result
    assert len(canonical_projection_bytes(result)) <= 800 * 4


@pytest.mark.parametrize("builder", [build_action_packet, shard_packet])
def test_action_packet_without_contract_never_infers_operation(builder):
    packet = builder(question="Delete src/config.py", context_pack=[],
        required_target_paths=("src/config.py",), required_evidence_paths=("src/config.py",))
    assert packet["mutation_intent"]["operation"] == "none"
    assert not packet["mutation_intent"]["ready"]
    assert validate_action_packet(packet, evidence_items=[]) == []


def test_paths_only_enrich_metadata_without_promoting_operation():
    bound = with_explicit_path_targets(build_mutation_intent("modify src/a.py"), ("src/a.py",))
    assert bound.operation == "none" and not evaluate_mutation_readiness(bound).ready
    assert bound.requested_targets[0].value == "src/a.py"
    assert bound.requested_targets[0].provenance == "explicit_task_contract"


def test_explicit_sdk_contract_preserves_resolution_and_readiness_gates():
    contract = MutationIntentContract("modify", "source", (
        RequestedTarget("src/a.py", "path", -1, -1, "explicit_sdk"),))
    assert not evaluate_mutation_readiness(contract).ready
    item = {"path": "src/a.py", "source_class": "project_file",
            "content": "def marble(): pass", "source_exists": True}
    resolved = resolve_mutation_targets(contract, [item], evidence_id_for_item=lambda row: "source:a")
    assert resolved.operation == "modify" and resolved.resolved_targets[0].path == "src/a.py"
    assert evaluate_mutation_readiness(resolved).ready
    rejected = resolve_mutation_targets(contract, [{**item, "matched": False}],
        evidence_id_for_item=lambda row: "source:a")
    assert not rejected.resolved_targets and not evaluate_mutation_readiness(rejected).ready
    packet = build_action_packet(question="arbitrary prose", context_pack=[], mutation_intent_contract=contract)
    assert packet["mutation_intent"]["operation"] == "modify"
    assert not packet["mutation_intent"]["ready"]


class PartialFacade:
    def __init__(self):
        self.calls = []

    def get_docs_context(self, question, **kwargs):
        self.calls.append((question, kwargs))
        return {
            "status": "partial_success", "mode_selected": "project",
            "answer_available": False, "answer_supported": False,
            "documentation_query_plan": asdict(build_documentation_query_plan(
                question, lookup_queries=("MissingAnchor",))),
            "context_pack": [{
                "source_class": "project_doc", "path": "docs/valve.md",
                "content": "MarbleValve retains its literal project configuration for bounded local reads.",
                "project_identity": "git:example/project", "authority": "source_of_truth",
                "doc_scope": "project", "lifecycle_status": "active", "freshness": "current",
                "index_freshness": "synchronized", "risk_flags": [],
                "retrieval_query_matches": {"query-original": {
                    "qualified": True, "mode": "and", "query_text": question,
                    "query_origin": "original", "relation": "direct"}},
            }],
        }


@pytest.mark.parametrize("partial_status", ["ok", "insufficient_evidence"])
def test_partial_read_recovery_keeps_projector_sources_snapshot_and_validator(monkeypatch, partial_status):
    captured = {}
    projector = ingress.project_docs_context
    validator = ingress.validate_model_visible_projection

    def capture_projection(**kwargs):
        projection, snapshot = projector(**kwargs)
        # Exercise both the live partial-read status and the recovery status
        # contract without fabricating sources or bypassing transport validation.
        projection["status"] = partial_status
        captured["projection"] = deepcopy(projection)
        captured["snapshot"] = deepcopy(snapshot)
        return projection, snapshot

    def capture_validation(projection, **kwargs):
        captured["validated_projection"] = deepcopy(projection)
        captured["validated_snapshot"] = deepcopy(kwargs["snapshot"])
        captured["validation_budget"] = kwargs["max_tokens"]
        return validator(projection, **kwargs)

    monkeypatch.setattr(ingress, "project_docs_context", capture_projection)
    monkeypatch.setattr(ingress, "validate_model_visible_projection", capture_validation)
    result = ingress.handle_context_tool("get_docs_context", {
        "question": "MarbleValve", "project_path": "/repo", "lookup_queries": ["MissingAnchor"],
    }, PartialFacade())
    assert captured["projection"]["status"] == partial_status
    assert captured["projection"]["context_available"]
    assert captured["validated_projection"]["sources"] == captured["projection"]["sources"]
    assert captured["snapshot"] == captured["validated_snapshot"]
    assert captured["validation_budget"] == 800
    if partial_status == "insufficient_evidence":
        # OPEN validator dependency: the current transport rejects this status
        # paired with retrieval_only. Ingress must retain sources for validation
        # rather than bypass that gate or replace the packet with empty recovery.
        assert result["status"] == "failed"
        assert result["error"]["reason_code"] == "invalid_model_visible_projection"
        assert "inconsistent support_status" in result["error"]["message"]
        return
    assert result["sources"] == captured["projection"]["sources"]
    assert result["query_coverage"] == "partial"
    assert result["context_available"] and not result["edit_ready"]
    assert result["support_status"] == "retrieval_only"
    assert len(canonical_projection_bytes(result)) <= 800 * 4
    assert validate_model_visible_projection(result, snapshot=captured["snapshot"], max_tokens=800) == []


def test_public_empty_read_preserves_operational_block_and_terminal_cap(tmp_path):
    facade = PublicFacade(tmp_path)
    facade.docs = replace(facade.docs, status="invalid_project_docs_catalog", results=[],
        reason_code="invalid_project_docs_catalog", requires_confirmation=True,
        confirmation_reason="repo_write")
    result = ingress.handle_context_tool("get_docs_context", {
        "question": "Fix MarbleValve", "project_path": str(tmp_path),
    }, facade)
    assert not result.get("context_available") and not result.get("edit_ready")
    assert len(canonical_projection_bytes(result)) <= 800 * 4

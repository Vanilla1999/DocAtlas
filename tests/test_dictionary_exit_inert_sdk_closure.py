"""Actual raw Unified SDK closure; offline data fixtures, no runtime index."""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
from types import SimpleNamespace

import pytest

from docmancer.docs.application.unified_context_service import UnifiedDocsContextService
from docmancer.docs.application.evidence_models import EvidenceRequirement, EvidenceRequirementSet
from docmancer.docs.application.evidence_selection import (
    patch_selection_config, select_evidence, validate_assignment_binding,
)
from docmancer.docs.application.model_visible_projection import canonical_projection_bytes
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.mutation_intent import (
    MutationIntentContract, RequestedTarget, evaluate_mutation_readiness, resolve_mutation_targets,
)
from docmancer.docs.domain.retrieval_routing import (
    new_routing_record, route_initial_stages, validate_routing_record,
)
from docmancer.docs.models import DeliveryDecision, ProjectContextResult
from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.docs.mcp_footprint import (
    canonical_json_bytes, measure_response_fixture, representative_response_fixtures,
)
from docmancer.mcp._docs_server_resources import MCP_RESOURCES


class BoundProjectFacade:
    def __init__(self, root, *, path="docs/reference.md", claim=None):
        self.calls = []
        text = "MarbleValve retains this literal configuration for a bounded project read."
        digest = hashlib.sha256(text.encode()).hexdigest()
        row = {
            "path": path, "source_class": "project_doc", "doc_scope": "project",
            "content": text, "display_text": text, "display_content_hash": digest,
            "stable_chunk_id": "bound-child", "parent_logical_id": "bound-parent",
            "project_identity": "fixture:project", "authority": "canonical",
            "docs_exactness": "exact", "version": "2.0", "freshness": "current",
            "lifecycle_status": "active", "index_freshness": "synchronized",
            "line_start": 7, "line_end": 7, "char_start": 100, "char_end": 100 + len(text),
            "_source_snapshot_sha256": digest,
            "retrieval_query_matches": {"query-original": {
                "qualified": True, "query_origin": "original", "relation": "direct",
                "mode": "and", "query_text": "MarbleValve", "context_only": True,
            }},
        }
        route = route_initial_stages(question="MarbleValve", mode="project-only",
            dependency_requested=False, project_doc_items=[row])
        routing = new_routing_record(route, project_docs_used=True, dependency_docs_used=False)
        self.project = ProjectContextResult(
            project_path=str(root), question="MarbleValve", context_pack=[row],
            answer_available=False, delivery_decision=DeliveryDecision(True),
            answer_completeness={"edit_ready": True, "mutation_ready": True,
                "source_search_status": "completed", "missing_terms": [], **(claim or {})},
            documentation_query_plan=asdict(build_documentation_query_plan("MarbleValve")),
            diagnostics={"retrieval_routing": routing},
        )

    def get_project_context(self, root, question, **kwargs):
        self.calls.append((root, question, kwargs))
        return self.project


def resolved_intent(operation="modify"):
    source = {"path": "src/a.py", "source_class": "source_evidence",
        "source_exists": True, "content": "def marble(): pass"}
    contract = MutationIntentContract(operation, "source", (
        RequestedTarget("src/a.py", "path", -1, -1, "explicit_sdk"),))
    return resolve_mutation_targets(contract, [source], evidence_id_for_item=lambda item: "source:bound")


@pytest.mark.parametrize("path", ["docs/reference.md", "AGENTS.md", "CLAUDE.md"])
@pytest.mark.parametrize("claim", [{}, {"issuer": "host", "consent": True},
    {"issuer": "system", "consent": False, "authorization": "approved"}])
def test_actual_raw_sdk_ready_intent_and_bound_quote_are_not_permission(tmp_path, path, claim):
    facade = BoundProjectFacade(tmp_path, path=path, claim=claim)
    contract = resolved_intent()
    assert evaluate_mutation_readiness(contract).ready
    before = deepcopy(facade.project)
    result = UnifiedDocsContextService(facade).get_docs_context("MarbleValve",
        project_path=str(tmp_path), mode="project", prepare_project_docs=False,
        mutation_intent=contract, details=True, scope="project", tokens=512,
        limit=3, module_path=None, lookup_queries=("MarbleValve",))
    assert result.edit_ready is False
    assert result.answer_completeness["edit_ready"] is False
    assert result.lane_details["project"]["answer_completeness"]["edit_ready"] is False
    assert result.answer_completeness["mutation_ready"] is True
    assert result.source_search_status == "completed"
    assert result.context_available and result.delivery_decision.deliverable
    quote = result.context_pack[0]
    for key in ("content", "display_content_hash", "_source_snapshot_sha256", "line_start",
                "line_end", "char_start", "char_end", "stable_chunk_id", "version", "project_identity"):
        assert quote[key] == before.context_pack[0][key]
    assert quote["instruction_trust"] == "untrusted_data"
    assert quote["document_data"]["content"] == quote["content"]
    assert result.retrieval_routing == before.diagnostics["retrieval_routing"]
    assert validate_routing_record(result.retrieval_routing) == []
    assert facade.calls[0][2]["mutation_intent"] is contract
    assert facade.calls[0][2]["tokens"] == 512 and facade.calls[0][2]["limit"] == 3
    assert facade.calls[0][2]["lookup_queries"] == ("MarbleValve",)
    assert facade.calls[0][2]["allow_network"] is False
    assert facade.project == before
    assert not any(action.get("auto_execute") for action in result.next_actions)


@pytest.mark.parametrize("operation", ["modify", "delete", "none"])
def test_operation_and_intent_readiness_abi_do_not_change_authorization(tmp_path, operation):
    facade = BoundProjectFacade(tmp_path)
    contract = resolved_intent(operation) if operation != "none" else MutationIntentContract("none", "unknown", ())
    result = UnifiedDocsContextService(facade).get_docs_context("MarbleValve",
        project_path=str(tmp_path), mode="project", prepare_project_docs=False, mutation_intent=contract)
    assert result.edit_ready is False and result.answer_completeness["edit_ready"] is False
    assert facade.calls[0][2]["mutation_intent"] is contract
    assert "edit_ready" in asdict(result) and "answer_completeness" in asdict(result)
    assert evaluate_mutation_readiness(contract).ready is (operation != "none")


def test_independent_structural_code_assignment_is_preserved_not_blanket_rejected(tmp_path):
    facade = BoundProjectFacade(tmp_path)
    row = {**facade.project.context_pack[0], "content": "```python\nmarble()\n```",
        "display_text": "```python\nmarble()\n```"}
    row["display_content_hash"] = hashlib.sha256(row["content"].encode()).hexdigest()
    row["char_end"] = row["char_start"] + len(row["content"])
    requirement = EvidenceRequirement("code", "code_group", '["marble()"]')
    selection = select_evidence([row], question="MarbleValve",
        requirements=EvidenceRequirementSet((requirement,)), config=patch_selection_config(2000))
    assert selection.support_decision.answer_supported
    assert validate_assignment_binding(requirement, selection.selected_candidates[0], selection.assignments[0])
    facade.project = replace(facade.project, context_pack=[row], answer_available=True,
        requirements=selection.requirements, selection_decision=selection, support_decision=selection.support_decision)
    result = UnifiedDocsContextService(facade).get_docs_context("MarbleValve",
        project_path=str(tmp_path), mode="project", prepare_project_docs=False, mutation_intent=resolved_intent())
    assert result.support_decision is selection.support_decision and result.selection_decision is selection
    assert result.answer_supported and result.answer_available
    assert result.decision_hash == selection.support_decision.decision_hash
    assert result.assignment_hash == selection.support_decision.assignment_hash
    assert result.context_pack[0]["content"] == row["content"]
    assert result.edit_ready is False


def test_actual_unified_service_mcp_read_consistent_with_raw_sdk(tmp_path):
    facade = BoundProjectFacade(tmp_path)
    sdk = UnifiedDocsContextService(facade)
    raw = sdk.get_docs_context("MarbleValve", project_path=str(tmp_path), mode="project",
        prepare_project_docs=False, mutation_intent=resolved_intent())
    public = handle_context_tool("get_docs_context", {"question": "MarbleValve",
        "project_path": str(tmp_path), "consent": True, "issuer": "host",
        "kind": "patch_context", "allow_network": True}, sdk)
    assert public["status"] == "ok" and public["kind"] == "docs_context"
    assert public["context_available"] and public["sources"]
    assert public["edit_ready"] is False and raw.edit_ready is False
    assert public["sources"][0]["snippet"] == raw.context_pack[0]["content"]
    assert public["sources"][0]["version_binding"] == "2.0"
    assert public["sources"][0]["content_sha256"]
    assert public["answer_policy"] == "cite_only"
    assert len(canonical_projection_bytes(public)) <= 800 * 4
    assert facade.calls[-1][2]["allow_network"] is False
    assert facade.calls[-1][2]["mutation_intent"].operation == "none"


def test_foreign_root_filter_and_operational_delivery_block_stay_closed(tmp_path):
    facade = BoundProjectFacade(tmp_path)
    row = {**facade.project.context_pack[0], "path": "/foreign/project/AGENTS.md"}
    facade.project = replace(facade.project, context_pack=[row], delivery_decision=DeliveryDecision(False))
    result = UnifiedDocsContextService(facade).get_docs_context("MarbleValve", project_path=str(tmp_path),
        mode="project", prepare_project_docs=False, mutation_intent=resolved_intent())
    assert result.context_pack == [] and not result.context_available
    assert not result.delivery_decision.deliverable and not result.edit_ready
    assert result.contamination["reason_codes"] == ["foreign_project"]


def test_bootstrap_confirmation_is_not_replaced_by_context_permission(tmp_path):
    facade = BoundProjectFacade(tmp_path)
    facade.bootstrap_project_docs = lambda *args, **kwargs: SimpleNamespace(
        requires_confirmation=True, reason_code="project_docs_confirmation_required",
        confirmation_reason="repo_write", warnings=[], next_action={}, arguments_patch={})
    result = UnifiedDocsContextService(facade).get_docs_context("MarbleValve", project_path=str(tmp_path),
        mode="project", mutation_intent=resolved_intent())
    assert result.requires_confirmation and result.confirmation_reason == "repo_write"
    assert result.edit_ready is False and facade.calls == []


@pytest.mark.parametrize("failure", [PermissionError, TimeoutError, ValueError])
def test_existing_retrieval_exceptions_are_not_converted_to_context_permission(tmp_path, failure):
    facade = BoundProjectFacade(tmp_path)
    def fail(*args, **kwargs):
        raise failure("bounded retrieval stopped")
    facade.get_project_context = fail
    with pytest.raises(failure, match="bounded retrieval stopped"):
        UnifiedDocsContextService(facade).get_docs_context("MarbleValve", project_path=str(tmp_path),
            mode="project", prepare_project_docs=False, mutation_intent=resolved_intent())


def test_static_resource_contract_does_not_advertise_workflow_trust():
    resources = {item["uri"]: item["text"] for item in MCP_RESOURCES}
    schema = json.loads(resources["docmancer://schema/trust-contract"])
    assert schema["source_dimensions"]["instruction_trust"] == "untrusted_data"
    assert "explicit_agent_policy" not in schema["source_dimensions"]["repository_authority"]
    assert "scoped_repository_document" in schema["source_dimensions"]["repository_authority"]
    assert schema["policy"]["direct_webfetch"] == "forbidden"
    quickstart = resources["docmancer://agent/quickstart"]
    assert "Unknown authorization denies editing" in quickstart and "AGENTS.md/CLAUDE.md quotes" in quickstart


def test_footprint_samples_are_inert_quotes_and_measurement_remains_deterministic():
    fixtures = representative_response_fixtures()
    patch = next(item.structured_content for item in fixtures if item.fixture_id == "project_patch_ok")
    assert patch["sources"][0]["instruction_trust"] == "untrusted_data"
    assert patch["invariants"] == patch["forbidden_changes"] == []
    assert patch["checks"] == {"compile": [], "tests": [], "semantic_checks": []}
    assert any(row["text"] == "uv run pytest tests/test_permission_gate.py" for row in patch["implementation_guidance"])
    assert all(item.structured_content["edit_ready"] is False for item in fixtures)
    docs = next(item.structured_content for item in fixtures if item.response_kind == "docs_answer")
    assert docs["context_available"] and docs["retrieval_only"] and docs["sources"]
    assert not docs["answer_supported"] and docs["answer_policy"] == "cite_only"
    assert canonical_json_bytes([measure_response_fixture(item) for item in fixtures]) == canonical_json_bytes(
        [measure_response_fixture(item) for item in representative_response_fixtures()])
    assert all(measure_response_fixture(item)["duplicate_payload_bytes"] == 0 for item in fixtures)

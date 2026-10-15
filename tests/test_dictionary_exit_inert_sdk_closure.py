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


















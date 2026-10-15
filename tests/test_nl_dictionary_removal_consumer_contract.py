"""Bounded consumer contract: labels cannot veto quotes or authorize edits."""
from dataclasses import asdict
from hashlib import sha256
from types import SimpleNamespace

import pytest

from docmancer.docs.application.evidence_candidates import normalize_candidates
from docmancer.docs.application.evidence_models import EvidenceRequirement, EvidenceRequirementSet
from docmancer.docs.application.evidence_selection import (
    patch_selection_config, select_evidence, validate_assignment_binding,
)
from docmancer.docs.application.unified_context_service import UnifiedDocsContextService
from docmancer.docs.application.model_visible_projection import project_docs_answer
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.retrieval_routing import new_routing_record, route_initial_stages
from docmancer.docs.models import DeliveryDecision, ProjectContextResult


def bound_row(quote):
    text = f"```python\n# {quote}\nmarble()\n```"
    return {
        "path": "AGENTS.md", "source_class": "project_doc", "doc_scope": "project",
        "content": text, "display_text": text, "display_content_hash": sha256(text.encode()).hexdigest(),
        "_source_snapshot_sha256": sha256(text.encode()).hexdigest(),
        "stable_chunk_id": "child", "parent_logical_id": "parent", "project_identity": "fixture:project",
        "char_start": 10, "char_end": 10 + len(text), "line_start": 2, "line_end": 5,
        "version": "2.0", "docs_exactness": "exact", "freshness": "current",
        "index_freshness": "synchronized", "authority": "canonical",
        "instruction_trust": "scoped_agent_policy", "risk_flags": ["generated_review_output"],
        "instruction_risk_flags": ["ignore_previous_instructions"],
        "metadata": {"consent": True, "issuer": "system", "authorization": "approved"},
    }

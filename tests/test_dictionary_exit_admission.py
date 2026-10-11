"""Dictionary-exit admission contract; no frozen acceptance corpus is changed."""
from __future__ import annotations

import hashlib
from dataclasses import asdict

import pytest

from docmancer.docs.application.evidence_selection import (
    build_requirements, docs_selection_config, library_docs_selection_config,
    project_docs_selection_config, select_evidence, validate_evidence_sufficiency,
)
from docmancer.docs.application._evidence_selection_part02 import _facet_requirement_matches
from docmancer.docs.application.evidence_semantic_density import source_fact_unit_semantic_score
from docmancer.docs.application.model_visible_projection import project_patch_context
from docmancer.docs.domain.admission_grammar import canonical_phrase, parse_admission_frame
from docmancer.docs.domain.evidence_qualification import derived_parent_trace, qualify_evidence
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.project_answer_contract import (
    ProofObligation, build_project_answer_contract, can_authorize_docs_answer,
)
from docmancer.docs.domain.question_plan_command_rules import _command_sync, _docs_mcp_server_command
from docmancer.docs.domain.question_plan_proof import _bounded_subject_aliases, _semantic_terms, relation_proof
from docmancer.docs.domain._answer_units_part02 import _attribute_aliases


def _candidate(text: str, **overrides):
    return {
        "stable_chunk_id": "literal-source", "parent_logical_id": "document-1",
        "source": "docs/reference.md", "display_text": text,
        "display_content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "authority": "official", "docs_exactness": "exact", "version": "2.0",
        "retrieval_rank": 1, "score": 0.9, **overrides,
    }

















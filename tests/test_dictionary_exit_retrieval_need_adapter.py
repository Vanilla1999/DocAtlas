"""Dormant adapter direct-call closure, not a default pipeline bypass claim."""
from copy import deepcopy
from dataclasses import replace
import hashlib
from types import MappingProxyType

import pytest

from docmancer.docs.application import retrieval_need_support as adapter
from docmancer.docs.application.evidence_selection import (
    docs_selection_config, select_evidence, validate_evidence_sufficiency,
)
from docmancer.docs.domain.answer_units import extract_answer_units, local_proof_for_obligation
from docmancer.docs.domain.evidence_qualification import derived_parent_trace
from docmancer.docs.domain.project_answer_contract import ProofObligation


CREDIT = {
    "need_local_witness": True, "admission_route": "typed_local",
    "matched_need_ids": ["query-need-1"], "need_witness_spans": [[0, 20]],
    "need_witness_source_key": "old-body", "_admission_demands": ["forged"],
    "context_eligible": True, "context_need_ids": ["query-need-1"],
    "_need_context": {"supported": True},
}
QUERY = {"query_origin": "retrieval_need", "need_relation": "default"}




















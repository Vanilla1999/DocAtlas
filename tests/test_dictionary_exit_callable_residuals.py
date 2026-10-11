"""Allocated inventory R6–R10 probes; context integrity is not answer approval."""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import re
from types import MappingProxyType, SimpleNamespace

import pytest

from docmancer.docs.application import retrieval_need_support as needs
from docmancer.docs.application import _library_docs_service_shared as library
from docmancer.docs.application.library_source_discovery import _python_candidates
from docmancer.docs.application.model_visible_projection import _answer_text, _needs_actionable_limitation
from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.docs.domain import _answer_units_part02 as proof_helpers
from docmancer.docs.domain._project_answer_contract_part01 import _cardinality
from docmancer.docs.domain.answer_units import extract_answer_units, local_proof_for_obligation
from docmancer.docs.domain.code_graph import CodeGraph, CodeGraphEdge, CodeGraphNode, score_code_graph_file
from docmancer.docs.domain.evidence_set_types import SourceKey
from docmancer.docs.domain.evidence_set_validation import build_dependency_sets, span_matches_source, validate_evidence_set
from docmancer.docs.domain.legacy_question_coverage import legacy_coverage_gaps
from docmancer.docs.domain.patch_request_plan import PatchRequestPlan, _operation, _target_list, build_patch_request_plan
from docmancer.docs.domain.project_answer_contract import ProofObligation
from docmancer.docs.domain.query_reference_binding import ScopeKey
from docmancer.docs.domain.source_dependency_graph import digest, source_graph


def source_key(raw):
    return SourceKey(ScopeKey('p', 'v', 's'), 'd', 'a.md', digest(raw))































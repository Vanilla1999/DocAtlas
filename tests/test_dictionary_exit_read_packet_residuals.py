"""R2–R5 diagnostics: literal context is not policy/behavior authorization."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import re

import pytest

from docmancer.docs.application.action_packet import build_action_packet, validate_action_packet
from docmancer.docs.application._action_packet_part01 import (
    _critical_fact_count, _extract_facts,
)
from docmancer.docs.application._action_packet_part02 import (
    _constraint_signature, _has_behavioral_contract,
)
from docmancer.docs.application.evidence_candidates import (
    normalize_candidates, observed_qualifiers, projected_text, requirement_value_visible,
)
from docmancer.docs.application.evidence_selection import (
    docs_selection_config, patch_selection_config, select_evidence,
)
from docmancer.docs.application._evidence_selection_part02 import _deduplicate
from docmancer.docs.application.model_visible_projection import (
    project_docs_answer, validate_model_visible_projection,
)
from docmancer.docs.domain.evidence_qualification import (
    _general_relation_is_locally_bound, _proof_relation_is_locally_bound,
    _visible_comparison_relation, qualify_evidence,
)
from docmancer.docs.domain.normative_language import (
    classify_normative_modality, python_declaration_line_indexes,
)
from docmancer.docs.domain.technical_tokens import technical_term_pattern


def row(text, identity="quote-1", **overrides):
    return {
        "stable_chunk_id": identity, "parent_logical_id": "document-1",
        "source": "docs/RULES.md", "display_text": text,
        "display_content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "authority": "canonical", "docs_exactness": "exact", "version": "2.0",
        "retrieval_rank": 1, "score": 0.9, **overrides,
    }

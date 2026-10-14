from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json

import pytest

from docmancer.docs.application.evidence_candidates import normalize_candidates
from docmancer.docs.application.evidence_models import EvidenceRequirement, EvidenceRequirementSet
from docmancer.docs.application.evidence_selection import (
    docs_selection_config, patch_selection_config, select_evidence,
    validate_assignment_binding, validate_evidence_sufficiency,
)
from docmancer.docs.application._evidence_selection_part01 import _candidate_source_view
from docmancer.docs.application._evidence_selection_part02 import _witness_for_requirement
from docmancer.docs.application._evidence_selection_part03 import _with_coverage
from docmancer.docs.application.model_visible_projection import project_docs_answer, validate_model_visible_projection


CODE = EvidenceRequirement("code", "code_group", '["erase_all()"]')


def row(text="Unrelated policy must remain.", **changes):
    return {"path": "docs/example.md", "content": text, "authority": "canonical", **changes}


def select(raw, requirements=(CODE,), docs=False):
    return select_evidence(
        [raw], question="inspect", requirements=EvidenceRequirementSet(requirements),
        config=docs_selection_config(800) if docs else patch_selection_config(),
    )

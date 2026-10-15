from __future__ import annotations

from dataclasses import replace
import hashlib

import pytest

from docmancer.docs.domain import answer_units as api
from docmancer.docs.domain import _answer_units_part02 as proofs
from docmancer.docs.domain.project_answer_contract import (
    ProofObligation,
    obligations_can_authorize_docs_answer,
)


def _obligation(kind="exact_fact", **kwargs):
    return ProofObligation("explicit", kind, "Widget", **kwargs)




























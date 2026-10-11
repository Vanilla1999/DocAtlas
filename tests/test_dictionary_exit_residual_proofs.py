from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import re

import pytest

from docmancer.docs.domain import answer_units as api
from docmancer.docs.domain import _answer_units_part02 as residual
from docmancer.docs.domain import governance_value_proof as governance
from docmancer.docs.domain.question_premise_proof import premise_relation_proof
from docmancer.docs.domain.project_answer_contract import (
    ProofObligation, obligations_can_authorize_docs_answer,
)


def obligation(kind="exact_fact", **kwargs):
    return ProofObligation("explicit-residual", kind, "Widget", **kwargs)


def supplied(text):
    return replace(api.extract_answer_units(text)[0], proposition=True)




















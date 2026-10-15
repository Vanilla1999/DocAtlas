"""Bounded admission exit: unknown NL is not evidence or rewrite authority."""
from dataclasses import FrozenInstanceError, replace
import hashlib
import re

import pytest

from docmancer.docs.domain import admission_local_binding as binding
from docmancer.docs.domain import admission_meaning as meaning
from docmancer.docs.domain import question_plan_core as core
from docmancer.docs.domain.admission_contract import (
    AdmissionDecision, HardGuards, LocalWitnessDecision, choose_admission,
    choose_need_admission,
)
from docmancer.docs.domain.admission_grammar import MeaningSlot, NEW_RELATIONS
from docmancer.docs.domain.answer_units import extract_answer_units, local_proof_for_obligation
from docmancer.docs.domain.project_answer_contract import ProofObligation
from docmancer.docs.domain.query_reference_binding import ScopeKey, resolve_references
from docmancer.docs.domain.question_frame_core import QuestionClause
from docmancer.docs.domain.question_retrieval_needs import RetrievalNeed


NL = (
    "What is RelayClient default timeout?",
    "What is RelayClient default retry delay duration when preview is not enabled?",
    "What is RelayClient default lease duration?",
    "What is RelayClient default timeout and retry delay?",
    "RelayClient uses timeouts everywhere. Its default behavior is to raise `Oops` after 7 seconds.",
    "Каков таймаут RelayClient по умолчанию, если режим отключён?",
    "the  Ω\u0301\tquux flurbs 🤖\n未知。",
    "", "   ",
)
































from __future__ import annotations

from pathlib import Path

from docmancer.docs.application.evidence_selection import (
    build_requirements,
    diagnose_proofability,
    project_docs_selection_config,
    select_evidence,
)
from docmancer.docs.application.model_visible_projection import (
    project_docs_answer,
    validate_model_visible_projection,
)
from tests.docs.test_question_frame_paraphrase_e2e import _service


def _select(question: str, candidates: list[dict], *, budget: int = 800):
    requirements = build_requirements(question, profile="project_docs_answer")
    return select_evidence(
        candidates,
        question=question,
        config=project_docs_selection_config(budget),
        requirements=requirements,
    )



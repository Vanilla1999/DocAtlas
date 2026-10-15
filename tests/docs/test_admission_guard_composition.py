"""Real planner, qualifier, and indexed pipeline controls for typed admission."""
from dataclasses import asdict

import pytest

from docmancer.docs.domain.admission_contract import (
    HardGuards, LocalWitnessDecision, choose_admission,
)
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.evidence_qualification import qualify_evidence, derived_parent_trace
from docmancer.docs.domain.query_terms import documentation_query_terms, query_constraint_roles
from tests.docs._reference_binding_fixtures import capture_reference_case, visible

QUESTION = ('Please explain the documented default timeout of RelayClient, '
            'stating the duration rather than discussing unrelated configuration options.')
FACT = 'RelayClient default timeout is 7 seconds.'


def need_probe(question=QUESTION):
    plan = build_documentation_query_plan(question)
    need = next(q for q in plan.queries if q.origin == 'retrieval_need')
    probe = asdict(need)
    probe.update(query_text=need.text, query_origin=need.origin,
                 query_terms=list(documentation_query_terms(need.text)),
                 exact_terms=list(query_constraint_roles(need.text).hard_exact),
                 bound_subjects=list(query_constraint_roles(need.text).bound_subjects))
    return probe


def qualify(body=FACT, *, probe=None, candidate=None):
    probe = need_probe() if probe is None else probe
    return qualify_evidence(probe, query_id=probe['query_id'],
        visible_text=body, evidence_text=body,
        candidate={'project_identity': 'repo', **(candidate or {})},
        expected_project_identity='repo')




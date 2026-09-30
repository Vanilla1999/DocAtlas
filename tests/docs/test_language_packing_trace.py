"""Collector invariants and same-input causal replay of the viewed HTTPX case."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
from unittest.mock import patch

import pytest

from experiments.language_aware_context import packing_probe as probe
from experiments.language_aware_context.packing_experiment import packing_experiment


def test_collector_calls_preference_once_and_preserves_return(monkeypatch):
    from docmancer.docs.application import _docs_context_projection_core as core
    values = [{'snippet': 'first'}, {'snippet': 'second'}]
    original = deepcopy(values)
    calls = []
    sentinel = object()
    def preference(candidates, selected, *args):
        calls.append(candidates)
        candidates.reverse()
        return sentinel
    monkeypatch.setattr(core, '_prefer_missing_baseline_candidate', preference)
    with probe.capture_packing_trace() as trace:
        assert core._prefer_missing_baseline_candidate(values, [], set(), set(), set()) is sentinel
    assert len(calls) == 1 and calls[0] is values
    assert values == original[::-1]
    assert trace['events'][0]['before_top3'][0]['snippet'] == 'first'
    assert trace['events'][0]['after_top3'][0]['snippet'] == 'second'
    assert core._prefer_missing_baseline_candidate is preference


def test_collector_marks_omissions_instead_of_claiming_complete(monkeypatch):
    from docmancer.docs.application import _docs_context_projection_core as core
    monkeypatch.setattr(probe, 'MAX_EVENTS', 0)
    with probe.capture_packing_trace() as trace:
        core._prefer_missing_baseline_candidate([], [], set(), set(), set())
    assert trace == {'events': [], 'omitted_events': 1}


def test_collector_restores_hooks_after_exception():
    from docmancer.docs.application import _docs_context_projection_core as core
    from docmancer.docs.application import docs_context_projection as facade
    from docmancer.docs.application.projection_decision_trace import ProjectionDecisionTrace
    before = (core._prefer_missing_baseline_candidate, facade._run_core, ProjectionDecisionTrace.record)
    with pytest.raises(ValueError, match='deliberate'):
        with probe.capture_packing_trace():
            raise ValueError('deliberate')
    assert before == (core._prefer_missing_baseline_candidate, facade._run_core, ProjectionDecisionTrace.record)


def test_same_prepared_input_delivers_complete_quote_with_intervention():
    # Both projector conditions see deep copies of the SAME actual handler input,
    # while the exact indexed files/snapshot are still alive. Not a simulated search.
    from docmancer.docs.interfaces.mcp import context_tools
    from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens
    from eval.evidence_quality_v2.run import audit_payload
    from experiments.language_aware_context.ci_diagnostic import TASKS, CLAIMS, claim_check
    from experiments.language_aware_context.baseline_probe import run
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / 'eval/evidence_quality_v2/source-manifest.json').read_text())
    tid, project, question, lookup = next(t for t in TASKS if t[0] == 'httpx-disable-client')
    spec = {'schema_version': 1, 'sources': [
        {'path': row['path'], 'sha256': row['sha256']}
        for row in manifest['sources'] if row['project'] == project]}
    projector = context_tools.project_docs_context
    replayed = []
    def replay(*, retrieval, **kwargs):
        exact_input = deepcopy(retrieval)
        original_result = projector(retrieval=retrieval, **kwargs)
        with packing_experiment():
            alternative, snapshot = projector(retrieval=deepcopy(exact_input), **deepcopy(kwargs))
        result = {'status': 'EXECUTED', 'payload': alternative,
                  'budget_tokens': docs_context_budget_tokens(alternative),
                  'audit_errors': audit_payload(alternative, snapshot,
                      Path(exact_input['_source_continuation_project_root']))}
        assert result['audit_errors'] == []
        assert claim_check(result, *CLAIMS[tid])['status'] == 'COMPLETE'
        replayed.append(result)
        return original_result
    with patch.object(context_tools, 'project_docs_context', replay):
        observed = run(root / 'eval/evidence_quality_v2/sources' / project,
                       spec, {'question': question, 'lookup_queries': [lookup]})
    assert len(replayed) == 1
    assert observed['status'] == 'EXECUTED' and observed['audit_errors'] == []

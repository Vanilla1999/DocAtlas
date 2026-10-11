"""Collector invariants and same-input causal replay of the viewed HTTPX case."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
from unittest.mock import patch

import pytest

from experiments.language_aware_context import packing_probe as probe
from experiments.language_aware_context.packing_experiment import packing_experiment




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

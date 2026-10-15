"""Known development regression; not independent quality."""
from pathlib import Path
import json

from experiments.language_aware_context.packing_experiment import packing_experiment


def test_real_handler_retains_complete_client_example_with_lookup():
    # The corpus and claim are the pre-existing viewed development case. Gold
    # clauses are evaluated after real execution and never passed to the adapter.
    from experiments.language_aware_context.baseline_probe import run
    from experiments.language_aware_context.ci_diagnostic import TASKS, CLAIMS, claim_check
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / 'eval/evidence_quality_v2/source-manifest.json').read_text())
    task_id, project, question, lookup = next(t for t in TASKS if t[0] == 'httpx-disable-client')
    spec = {'schema_version': 1, 'sources': [
        {'path': row['path'], 'sha256': row['sha256']}
        for row in manifest['sources'] if row['project'] == project]}
    with packing_experiment():
        result = run(root / 'eval/evidence_quality_v2/sources' / project,
                     spec, {'question': question, 'lookup_queries': [lookup]})
    assert result['status'] == 'EXECUTED' and result['audit_errors'] == []
    assert 0 < result['budget_tokens']
    assert result['payload'].get('answer_supported') is not True
    assert result['payload'].get('edit_ready') is not True
    assert claim_check(result, *CLAIMS[task_id])['status'] == 'COMPLETE'

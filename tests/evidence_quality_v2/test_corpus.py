import hashlib,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]/'eval/evidence_quality_v2'

def test_frozen_80_and_groups_not_hidden():
    protocol=json.loads((ROOT/'protocol.json').read_text());data=json.loads((ROOT/'cases.json').read_text())
    assert hashlib.sha256((ROOT/'cases.json').read_bytes()).hexdigest()==protocol['cases_sha256']
    assert hashlib.sha256((ROOT/'source-manifest.json').read_bytes()).hexdigest()==protocol['source_sha256']
    cases=data['cases'];assert len(cases)==len({c['id'] for c in cases})==80
    assert len({c['question'] for c in cases})==80
    assert Counter(c['split'] for c in cases)=={'development':40,'frozen_validation_exposed':40}
    for project in {c['project_group'] for c in cases}:
        assert len({c['split'] for c in cases if c['project_group']==project})==1
    assert data['unseen_validation']=='NOT_MEASURED'
    old=json.loads((ROOT.parent/'direct_docatlas_questions_15/cases.json').read_text())
    assert not {c['question'] for c in old['cases']} & {c['question'] for c in cases}

def test_source_hashes_and_witness_truth():
    sources=json.loads((ROOT/'source-manifest.json').read_text())['sources']
    for s in sources:
        path=ROOT/'sources'/s['project']/s['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==s['sha256']
    for c in json.loads((ROOT/'cases.json').read_text())['cases']:
        for claim in c['required_claims']:
            for witness in claim['witness_sets']:
                for part in witness['parts']:
                    source=(ROOT/'sources'/c['project_group']/part['path']).read_text()
                    assert part['text'] in source
        if c['answerability']=='within_budget':assert c['budget_check']['estimated_tokens']<=800

def test_production_catalog_contains_no_new_eval_or_gold():
    repo=ROOT.parents[1]
    assert 'evidence_quality_v2' not in (repo/'docatlas.project-docs.yaml').read_text()
    for path in (repo/'docmancer').rglob('*.py'):
        assert 'eval.evidence_quality_v2' not in path.read_text()

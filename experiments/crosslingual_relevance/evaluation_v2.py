"""Versioned external evaluation; no labels enter retrieval or rescue.

Canonical occurrence, source policy, relevance, and required-fact coverage are
separate fields. Unjudged sources are not called irrelevant. An expected file
name or a one-line overlap is never itself a witness.
"""
from __future__ import annotations
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent

@lru_cache(maxsize=16)
def corpus_documents(project: str) -> dict[str, str]:
    from eval.evidence_quality_v2.run import documents_for, load_protocol
    return documents_for(project, load_protocol()[2])


def canonical_row(row: Mapping[str, Any], documents: Mapping[str, str], *,
                  expected_identity: str | None = None) -> dict[str, Any]:
    path = row.get('path_or_url') or row.get('project_doc_path') or row.get('source_path')
    if not isinstance(path, str) or not path or path not in documents:
        return {'status':'unverified', 'reason':'missing_or_wrong_canonical_path'}
    if PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts:
        return {'status':'unverified', 'reason':'invalid_canonical_path'}
    start, end = row.get('line_start'), row.get('line_end')
    raw = documents[path]
    lines = raw.splitlines(keepends=True)
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
        return {'status':'unverified', 'reason':'missing_or_invalid_range'}
    text = row.get('snippet') or row.get('display_text') or row.get('text')
    if not isinstance(text, str) or not text.strip() or text not in ''.join(lines[start-1:end]):
        return {'status':'unverified', 'reason':'noncanonical_visible_bytes'}
    identity = row.get('project_identity')
    if expected_identity is not None and identity != expected_identity:
        return {'status':'rejected', 'reason':'wrong_project_identity'}
    digest = hashlib.sha256(raw.encode()).hexdigest()
    supplied = row.get('source_content_hash') or row.get('_source_snapshot_sha256')
    if supplied is not None and str(supplied).removeprefix('sha256:') != digest:
        return {'status':'rejected', 'reason':'snapshot_mismatch'}
    return {'status':'verified', 'path':path, 'text':text, 'line_start':start, 'line_end':end,
            'document_sha256':digest, 'text_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'identity_verified':expected_identity is not None}


def required_claims(task: Mapping[str, Any]) -> list[dict[str, Any]]:
    if 'required_claims' in task:
        return list(task['required_claims'])
    spec = json.loads((HERE/'evaluation_claims_v2.json').read_text())
    key = str(task.get('id') or task.get('task_id') or '')
    aliases = spec.get('task_aliases', {})
    return list(spec['tasks'].get(aliases.get(key, key), []))


def assess_packet(payload: Mapping[str, Any], task: Mapping[str, Any], *,
                  audit_errors: list[str] | None = None) -> dict[str, Any]:
    documents = corpus_documents(str(task['project']))
    rows = [canonical_row(row, documents, expected_identity=task.get('expected_project_identity'))
            for row in payload.get('sources', []) if isinstance(row, Mapping)]
    valid = [row for row in rows if row['status']=='verified']
    claims = required_claims(task)
    supported = []
    for claim in claims:
        # All clauses of one witness must occur in a single canonical quotation.
        # Different claims can be supported by different quotations.
        witnesses = claim['alternatives']
        for witness in witnesses:
            raw = documents.get(witness['path'])
            if raw is None or hashlib.sha256(raw.encode()).hexdigest() != witness['document_sha256']:
                raise ValueError('evaluation source identity changed')
            for text in witness['clauses']:
                if not text or text not in raw:
                    raise ValueError('evaluation witness is not in canonical source')
        if any(row['path']==w['path'] and all(c in row['text'] for c in w['clauses'])
               for row in valid for w in witnesses):
            supported.append(claim['id'])
    full = bool(claims) and len(supported)==len(claims)
    policy = 'NOT_EVALUATED' if audit_errors is None else ('FAIL' if audit_errors else 'PASS')
    return {'metric_revision':'canonical-required-claims-v2',
            'required_count':len(claims), 'supported_count':len(supported),
            'supported_claim_ids':supported, 'all_required_facts':full,
            'canonical_errors':[r for r in rows if r['status']!='verified'],
            'source_policy_status':policy, 'source_policy_errors':audit_errors,
            'relevance_false_admissions':None,  # No exhaustive relevance labels here.
            'final_model_answer_quality':'NOT_MEASURED',
            'verdict': 'NOT_EVALUATED' if not claims or policy=='NOT_EVALUATED'
                       else 'PASS' if full and not audit_errors and all(r['status']=='verified' for r in rows)
                       else 'FAIL'}


def hit_at_k(relevance: list[bool], k: int = 5) -> float:
    return float(any(relevance[:k]))


def recall_at_k(relevance: list[bool], k: int = 5) -> float:
    positives = sum(relevance)
    return sum(relevance[:k]) / positives if positives else 0.0


def rank_full_pool(blocks: list[dict], scores: list[float], task: dict, k: int = 5) -> dict:
    """Rank the full fixed corpus before attaching task-local judgments.

    Missing labels remain UNJUDGED. Known-positive recall is not corpus recall
    unless all pairs are judged. Stable text/path hashes break ties without gold.
    """
    if len(blocks) != len(scores) or not all(math.isfinite(s) for s in scores):
        raise ValueError('invalid score matrix row')
    judged = {b['block_id']:b for b in task['blocks']}
    def key(pair):
        b,s = pair
        identity = json.dumps([b.get('path'),b.get('text')],ensure_ascii=False,separators=(',',':'))
        return -s, hashlib.sha256(identity.encode()).hexdigest(), str(b['block_id'])
    ranked = sorted(zip(blocks,scores),key=key)
    rows=[]
    for rank,(b,s) in enumerate(ranked,1):
        label=judged.get(b['block_id'])
        rows.append({'block_id':b['block_id'],'score':float(s),'rank':rank,
                     'judgment':'UNJUDGED' if label is None else 'JUDGED',
                     'relevant':None if label is None else label['relevant_to_question'],
                     'source_allowed':None if label is None else label['source_allowed'],
                     'covered_fact_ids':None if label is None else label['covered_fact_ids']})
    known = {bid for bid,label in judged.items() if label['relevant_to_question'] and label['source_allowed']}
    top={r['block_id'] for r in rows[:k]}
    return {'block_scores':rows, 'pool_size':len(blocks),'judged_pairs':len(judged),
            'unjudged_in_top_k':sum(r['judgment']=='UNJUDGED' for r in rows[:k]),
            'known_allowed_positive_recall_at_k':len(top & known)/len(known) if known else None,
            'fully_judged':len(judged)==len(blocks),
            'semantic_false_positive_rate':None}


def save_new_report(path: Path, payload: Any) -> None:
    """Never overwrite an archived result or silently accept nonfinite metrics."""
    encoded=json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        stream.write(encoded)

"""P5: distinguish unestablished source facts from retrieval/projection losses.

No documentation is authored. The selected corpus is not the whole upstream
project. A missing approved witness is never called proof of a universal gap.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path

from eval.evidence_quality_v2.run import REPO, documents_for, load_protocol
from eval.evidence_quality_v2.runtime import digest, save_json


def approved_set_present(witness: dict, documents: dict[str, str]) -> bool:
    parts = witness.get('parts', [])
    if not parts:
        return False
    for part in parts:
        text = documents.get(part['path'])
        if text is None:
            return False
        lo, hi = part.get('line_start'), part.get('line_end')
        if lo is None and hi is None:
            occurrence = text  # frozen whole-source/occurrence-unbound witness
        elif type(lo) is int and type(hi) is int and 1 <= lo <= hi <= len(text.splitlines()):
            occurrence = '\n'.join(text.splitlines()[lo-1:hi])
        else:
            return False
        if not part.get('text') or part['text'] not in occurrence:
            return False
    return True


def audit(output: Path) -> dict:
    protocol, cases, manifest = load_protocol()
    if output.resolve().is_relative_to(REPO):
        raise ValueError('audit outputs must be outside checkout')
    documents = {p: documents_for(p, manifest) for p in sorted({c['project_group'] for c in cases})}
    rows = []
    for case in cases:
        claims = {}
        for claim in case['required_claims']:
            alternatives = claim.get('witness_sets', [])
            claims[claim['id']] = ('approved_source_present' if any(
                approved_set_present(w, documents[case['project_group']]) for w in alternatives)
                else 'source_span_integrity_failure' if alternatives
                else 'not_established_in_selected_sources')
        rows.append({'id': case['id'], 'project': case['project_group'], 'answerability': case['answerability'],
                     'claims': claims, 'documentation_change': 'NONE'})
    # The original regression corpus stays exact and separate from the new scorer.
    original = json.loads((REPO / 'eval/direct_docatlas_questions_15/cases.json').read_text())['cases']
    q05 = next(c for c in original if c['id'] == 'Q05')
    original_facts = []
    for group in q05['fact_groups']:
        evidence = []
        for witness in group['witnesses']:
            path = REPO / witness['path']
            if path.is_file() and witness['text'] in path.read_text(encoding='utf-8'):
                evidence.append({'path': witness['path'], 'file_sha256': digest(path.read_bytes()),
                                 'approved_witness_present': True})
        original_facts.append({'id': group['id'], 'evidence': evidence})
    summary = {'schema_version': 'documentation-gap-audit-v1', 'cases': len(rows),
               'source_manifest_sha256': protocol['source_sha256'], 'cases_sha256': protocol['cases_sha256'],
               'claim_inventory': dict(Counter(v for r in rows for v in r['claims'].values())),
               'rows': rows, 'Q05': original_facts, 'documentation_changes': [],
               'editorial_2x2': 'NOT_APPLICABLE: no documentation changed in this continuation',
               'verdict': 'NO_DOCUMENTATION_EDIT_JUSTIFIED',
               'scope': 'Selected version-pinned sources only. Unestablished fictional/request-specific facts remain unknown; no claim about all upstream knowledge.'}
    if any(v == 'source_span_integrity_failure' for r in rows for v in r['claims'].values()):
        raise ValueError('an approved source span changed; audit cannot complete')
    if not all(r['evidence'] for r in original_facts):
        raise ValueError('Q05 approved source changed; rerun source review before attribution')
    save_json(output / 'summary.json', summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.output)
    print(json.dumps({k:v for k,v in result.items() if k != 'rows'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

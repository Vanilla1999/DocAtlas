"""Compare executed public MCP arms. Quality wins before any token claim."""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--artifacts', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    suites = ('v40', 'new16', 'fresh8', 'semantic12', 'preservation8')
    modes = ('facet-guarded-v1', 'semantic-exact-prune-v1', 'semantic-nli-prune-v1')
    arms = {}; missing = []
    for suite in suites:
        for mode in (*modes, *(('semantic-rescue-v1',) if suite in ('semantic12','preservation8') else ())):
            found = list(a.artifacts.glob(f'**/{suite}/{mode}/SUMMARY.json'))
            if len(found) != 1:
                missing.append((suite, mode)); continue
            directory = found[0].parent
            arms[(suite,mode)] = {
                'summary': json.loads(found[0].read_text()),
                'rows': {r['case_id']: r for r in json.loads((directory/'ASSESSMENTS.json').read_text())},
                'checker': json.loads((directory/'CHECKER.json').read_text()),
                'inputs': json.loads((directory/'FREEZE.json').read_text())['files'],
            }
    compared = []
    for mode in modes[1:]:
        losses = []; gains = []; actual = 0; baseline = 0; seconds = 0; base_seconds = 0
        removed = 0; pairs = 0; documented = 0; total_documented = 0; facts = 0; total_facts = 0
        for suite in suites:
            if (suite,mode) not in arms or (suite,modes[0]) not in arms:
                continue
            ref, cand = arms[(suite,modes[0])], arms[(suite,mode)]
            assert ref['inputs'] == cand['inputs'], 'input bytes changed'
            assert ref['rows'].keys() == cand['rows'].keys()
            for cid,b in ref['rows'].items():
                c = cand['rows'][cid]
                assert b['question'] == c['question'] and b['search_question'] == c['search_question']
                assert b['candidate_fingerprint'] == c['candidate_fingerprint'], 'acquisition changed'
                for item in b['claims']:
                    d = next(x for x in c['claims'] if x['id'] == item['id'])
                    if item['covered'] and not d['covered']:
                        losses.append({'suite':suite,'case':cid,'claim':item['id']})
                    if not item['covered'] and d['covered']:
                        gains.append({'suite':suite,'case':cid,'claim':item['id']})
                if c['answerability'] != 'unanswerable':
                    total_documented += 1; documented += bool(c['passed'])
                total_facts += len(c['claims']); facts += sum(x['covered'] for x in c['claims'])
            for key in ('runtime_errors','integrity_errors'):
                assert ref['summary'][key] == cand['summary'][key] == 0
            baseline += ref['summary']['model_visible_tokens']; actual += cand['summary']['model_visible_tokens']
            seconds += cand['summary']['seconds_total']; base_seconds += ref['summary']['seconds_total']
            removed += cand['checker']['removed_groups']; pairs += cand['checker']['model_pairs']
        compared.append({'mode':mode,'lost_facts':losses,'gained_facts':gains,
            'covered_documented_cases':documented,'documented_cases':total_documented,
            'retained_facts':facts,'required_facts':total_facts,
            'tokens':actual,'baseline_tokens':baseline,'mcp_seconds':seconds,'baseline_seconds':base_seconds,
            'removed_groups':removed,'checker_pairs':pairs,
            'evidence_non_regression':not losses})
    unknown_mutations = sum(v['checker']['unknown_mutations'] for v in arms.values())
    report = {'missing_arms':missing,'arms':len(arms),'comparisons':compared,
              'unknown_mutations':unknown_mutations,
              'by_suite':{f'{s}/{m}':v['summary'] for (s,m),v in arms.items()},
              'provider_usage':None,'answer_model_calls':0,'general_sufficiency_proved':False}
    (a.out/'PAIRED.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(report,indent=2,ensure_ascii=False))
    assert not missing and not unknown_mutations, 'execution/control failure'
    # Exact-source removal must be strictly lossless. NLI is a hypothesis:
    # preserve and report its failures rather than relabeling them as success.
    exact = next(c for c in compared if c['mode']=='semantic-exact-prune-v1')
    assert exact['evidence_non_regression'], 'exact source coverage regression'


if __name__ == '__main__':
    main()

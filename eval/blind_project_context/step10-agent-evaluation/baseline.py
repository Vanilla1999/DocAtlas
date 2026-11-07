"""Portable accounting and transcription of manual grading of the failed baseline.

This is an evaluation artifact, not an agent runner or a production policy.
All 16 final answers were manually inspected. The explicit grades below apply
only to the access-denied traces from terra-step10-final/file-current. Never use
these grades for a repaired baseline or candidate; independently review those.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FROZEN = HERE.parent
RUN = Path('/tmp/opencode/terra-step10-final')
CORPORA = Path('/tmp/opencode/step8-corpora2')
CASES = ('T01-en', 'T01-ru', 'T02-ru', 'T05-ru', 'T10-ru', 'T12-ru', 'T15-en', 'T19-ru')
# Independent manual per-fact reasons after inspecting each actual final answer.
ABSENT = {
    'T01.F1': 'Does not give either required branch-name pattern feat/<topic> or fix/<description>; requesting a contributing guide is not the branch convention.',
    'T01.F2': 'Does not state that the full test suite must run before opening a PR.',
    'T01.F3': 'Does not state that new connectors/fetchers should include tests where practical.',
    'T02.F1': 'Generic advice to avoid cleanup does not identify doc-atlas clear-index or its bounded preview plan.',
    'T02.F2': 'Does not describe the all-local-index cleanup scope or preservation of configuration.',
    'T02.F3': 'Does not explain that the approved cleanup can be bound to plan_digest.',
    'T05.F1': 'Does not identify installed wheel, actual installer, stdio MCP, SQLite and MiniLM as the covered verification boundary.',
    'T05.F2': 'Does not distinguish that verification from autonomous OpenCode/model runs and token benchmarks.',
    'T10.F1': 'Does not describe reproducing one original user question through the real public API/CLI/MCP.',
    'T10.F2': 'Does not describe log-off and log-on attempts from identical initial states.',
    'T10.F3': 'Does not require two independent PASS results plus parity.',
    'T12.F1': 'Does not state that reads neither reconcile an index nor write to the repository.',
    'T12.F2': 'Does not identify the finite explicit docatlas.project-docs.yaml catalog requirement.',
    'T12.F3': 'Does not state that prepare_docs sync_project_docs without mutation performs no writes.',
    'T15.F1': 'Does not explain that OpenCode retains structuredContent/content but drops response _meta.',
    'T15.F2': 'Does not explain loss of the original source-packet and unresolvable response-local short references.',
    'T19.F1': 'Does not identify the doc-atlas qdrant group or its DocAtlas-owned local-process scope.',
    'T19.F2': 'Does not identify qdrant up or its pinned-binary download behavior.',
    'T19.F3': 'Does not identify qdrant down or stopping the docmancer-managed process.',
    'T19.F4': 'Does not identify qdrant status or its pid/port/url/alive reporting.',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def main():
    questions = {q['id']: q for q in load(FROZEN/'questions.json')['cases'] if q['id'] in CASES}
    assert all(q['split'] == 'dev' for q in questions.values())
    topic_ids = {q['topic_id'] for q in questions.values()}
    # Only selected dev rows are retained/inspected; no holdout task detail.
    gold = {t['topic_id']: t for t in load(FROZEN/'oracle.json')['topics'] if t['topic_id'] in topic_ids}
    witnesses = {w['fact_id']: w for w in load(FROZEN/'witness-audit.json')['facts'] if w['fact_id'] in ABSENT}
    results = []
    for corpus in ('L0', 'L2'):
        for case in CASES:
            base = RUN/corpus/'file-current'/case
            events = [json.loads(line) for line in base.with_suffix('.jsonl').read_text().splitlines()]
            session = load(base.with_suffix('.session.json'))['data']
            receipt = load(base.with_suffix('.receipt.json'))
            texts = [event['part']['text'] for event in events if event['type'] == 'text']
            final = texts[-1] if texts else ''
            steps = [event['part'] for event in events if event['type'] == 'step_finish']
            tools = [event['part'] for event in events if event['type'] == 'tool_use']
            # Bind the manual refusal grades to this failed-run class. This guard
            # is not a replacement for grading future successful answers.
            assert final and tools and all(t['state'].get('error') == 'Permission denied: external_directory' for t in tools)
            assert all(not t['state'].get('output') for t in tools)
            assert all(t['state'].get('metadata', {}).get('providerResult', {}).get('executed') is False for t in tools)
            usage = {key: sum(step['tokens'][key] for step in steps) for key in ('input', 'output', 'reasoning')}
            for key in ('read', 'write'):
                usage['cache_'+key] = sum(step['tokens']['cache'][key] for step in steps)
                assert usage['cache_'+key] == session['tokens']['cache'][key]
            assert all(usage[key] == session['tokens'][key] for key in ('input', 'output', 'reasoning'))
            usage.update(input_with_cache=usage['input']+usage['cache_read'], steps=len(steps),
                         tool_calls=len(tools), tool_errors=len(tools), successful_tool_calls=0,
                         executed_file_operations=0, retrieved_source_bytes=0)
            facts = []
            for fact in gold[questions[case]['topic_id']]['facts']:
                bound_witnesses = []
                for w in witnesses[fact['fact_id']]['occurrences'][corpus]:
                    source = CORPORA/(corpus+'-0')/'project'/w['path']
                    span = ''.join(source.read_text().splitlines(keepends=True)[w['line_start']-1:w['line_end']])
                    assert fact['quote'] in span
                    bound_witnesses.append({**w, 'source_sha256': sha(source), 'source_span': span})
                facts.append({**fact, 'answer_grade': 'FAIL', 'present': False,
                              'reason': ABSENT[fact['fact_id']], 'answer_evidence': None,
                              'citation_grade': 'FAIL', 'citation_reason': 'No citation supports this required fact; the answer abstains after denied source access.',
                              'source_witnesses': bound_witnesses, 'retrieved_witness': False})
            results.append({'corpus': corpus, 'case': case, 'question': questions[case], 'receipt': receipt,
                'model': session['model'], 'session_outcome': session.get('outcome'),
                'source_artifact_hashes': {base.name+suffix: sha(base.with_suffix(suffix))
                                         for suffix in ('.jsonl','.session.json','.receipt.json','.stderr')},
                'usage': usage, 'step_usage': [{'reason': s.get('reason'), 'tokens': s['tokens']} for s in steps],
                'tool_counts': dict(Counter(t['tool'] for t in tools)), 'tool_trace': tools,
                'event_errors': [e for e in events if e['type'] == 'error'],
                'final_answer': final, 'commentary': texts[:-1], 'facts': facts,
                'answer_pass': False, 'citations': [], 'citation_pass': False,
                'retrieval_status': 'not_executed_external_directory_denied',
                'comparison_valid': False,
                'manual_answer_assessment': 'Honest access-failure abstention, not a substantive answer. No required fact or supporting citation is supplied. Any suggested CONTRIBUTING.md is a request for a source, not a source citation. Generic cleanup caution is not a documented cleanup procedure.'})
    keys = list(results[0]['usage'])
    totals = {key: sum(r['usage'][key] for r in results) for key in keys}
    summary = {'sessions': len(results), 'fact_pass': 0, 'fact_total': sum(len(r['facts']) for r in results),
               'fact_citations_pass': 0, 'answers_pass': 0, 'sessions_without_retrieval': len(results),
               'comparison_valid': False, 'failure': 'All file operations denied by external_directory permission before execution.',
               'usage': totals, 'tool_counts': dict(sum((Counter(r['tool_counts']) for r in results), Counter())),
               'seconds_sum': sum(r['receipt']['seconds'] for r in results)}
    artifact = {'schema_version': 1, 'evaluation': 'manual final-answer and citation grading, dev only',
                'source_run': str(RUN), 'arm': 'file-current',
                'method': 'Read existing analyze_gap_agent_study.py for accounting boundaries. Independently inspected every final answer and tool failure; checked each frozen dev fact against its original witness source span. Reconciled step token totals with session totals. Exit 0/session succeeded is not answer success.',
                'scope': 'No holdout task details inspected. No production, calibration policy, agent runner, source document, question or oracle changes.',
                'usage_conventions': 'input is provider-reported uncached input; input_with_cache adds cache_read, matching historical analyzer. cache_write separately reported. output and reasoning are preserved as separate reported fields and are not summed to invent a new billable total. tool_calls counts attempted tool invocations; executed_file_operations counts provider executed=true, which is zero here. Empty tool output is not a token-free trajectory: error text is included in subsequent provider input accounting.',
                'comparability': 'Infrastructure-invalid baseline: do not compare these short refusal trajectories as token savings or retrieval/answering quality against a working candidate. Keep incurred usage in cost accounting. Both fresh baseline and candidate require accessible/prepared source environments before a fair paired comparison.',
                'frozen_artifact_sha256': {name: sha(FROZEN/name) for name in ('questions.json','oracle.json','witness-audit.json')},
                'summary': summary, 'sessions': results}
    (HERE/'baseline.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n')
    md = ['# Step 10 file-current baseline: infrastructure-invalid', '',
          '**All 16 sessions fail to answer: 0/46 required facts, 0/46 supporting fact citations.**',
          'Every attempted file operation was denied with `Permission denied: external_directory`; no source retrieval executed. Final answers explicitly abstain. Exit 0 and session `succeeded` do not establish answer quality.', '',
          'Do not use these short failure trajectories as a working baseline or claim token savings against them. Usage below is real incurred usage, reconciled between step events and session totals. No production/policy tuning was performed; only frozen dev labels and witnesses were inspected.', '',
          '## Actual usage', '', '```json', json.dumps(summary,indent=2), '```', '',
          'Output and reasoning are separate provider-reported fields; input-with-cache adds input and cache-read. Tool counts are attempts, not successful reads. No additional model or retrieval calls were made for this evaluation.', '',
          '| Corpus/case | Facts | Input | Cache read | Output | Reasoning | Tool errors/attempts |',
          '|---|---:|---:|---:|---:|---:|---:|']
    for r in results:
        u=r['usage'];md.append(f"| {r['corpus']}/{r['case']} | 0/{len(r['facts'])} | {u['input']} | {u['cache_read']} | {u['output']} | {u['reasoning']} | {u['tool_errors']}/{u['tool_calls']} |")
    for r in results:
        md += ['', f"## {r['corpus']}/{r['case']}", '', r['question']['question'], '', '### Actual final answer', '', r['final_answer'], '', '### Independent fact and citation grades', '']
        for f in r['facts']:
            locations=', '.join(f"{w['path']}:{w['line_start']}-{w['line_end']}" for w in f['source_witnesses'])
            md += [f"- **{f['fact_id']}: FAIL; citation FAIL.** {f['reason']} Source witness: `{locations}`. No supporting citation was supplied."]
        md += ['', 'Tools: '+', '.join(t['tool']+' → '+t['state']['error'] for t in r['tool_trace'])+'. No tool returned source text.']
    md += ['', '## Portability and limitations', '',
           '`baseline.json` embeds all final answers, manual per-fact reasons, relevant frozen source witness text/hash/coordinates, exact tool traces, per-step token accounting, session receipts, and hashes of original event/session/stderr files. It is reviewable without the temporary run directory. This artifact grades the observed failed baseline only; a repaired baseline and candidate need separate grading. No retrieval-quality failure is inferred from a permission-denied operation that never executed.', '']
    (HERE/'baseline.md').write_text('\n'.join(md))
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()

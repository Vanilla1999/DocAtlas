"""Offline source-coordinate assessment and lossless DTO-format counterfactuals."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    spec = importlib.util.spec_from_file_location('original_evaluator', args.repo / 'eval/prepared_model_comparison40/evaluate.py')
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    data = args.repo / 'eval/prepared_model_comparison40'
    questions = {c['id']: c for c in json.loads((data / 'questions.json').read_text())['cases']}
    gold = {c['id']: c for c in json.loads((data / 'gold_spans.json').read_text())['cases']}
    measured = json.loads((args.run / 'MEASUREMENTS.json').read_text())

    def cost(value):
        raw = json.dumps(value, ensure_ascii=False).encode()
        tokens = projection_token_count(raw)
        return dict(bytes=len(raw), codec_tokens=tokens, utf8_div4=math.ceil(len(raw)/4), cost=max(tokens, math.ceil(len(raw)/4)))

    def normalized(payload, per_document=False):
        result = deepcopy(payload)
        rows = result['sources']
        common = {k: v for k, v in rows[0].items() if k != 'snippet' and all(k in r and r[k] == v for r in rows)} if rows else {}
        result['source_defaults'] = common
        for row in rows:
            for k in common:
                del row[k]
        if per_document:
            # Share only actual equal fields within a literal path group. Never
            # replace per-window content hashes by a supposed document hash.
            paths = list(dict.fromkeys(r.get('path_or_url') for r in rows))
            table = []
            for i, path in enumerate(paths):
                members = [r for r in rows if r.get('path_or_url') == path]
                shared = {k: v for k, v in members[0].items() if k != 'snippet' and all(k in r and r[k] == v for r in members)}
                # A singleton does not benefit from a table and remains whole.
                if len(members) < 2:
                    continue
                table.append(dict(index=i, fields=shared))
                for row in members:
                    for k in shared:
                        del row[k]
                    row['source_group'] = i
            result['source_groups'] = table
        decoded = deepcopy(result)
        defaults = decoded.pop('source_defaults')
        table = {r['index']: r['fields'] for r in decoded.pop('source_groups', [])}
        decoded['sources'] = [{**defaults, **table.get(r.get('source_group'), {}),
                               **{k: v for k, v in r.items() if k != 'source_group'}} for r in decoded['sources']]
        assert decoded == payload
        return result

    output = []
    for case in measured['cases']:
        cid = case['case_id']
        events = json.loads((args.run / (cid + '-trace.json')).read_text())['events']
        preparation = json.loads((args.run / (cid + '-preparation.json')).read_text())
        prepared = dict(root=preparation['root'], sources={})
        for p in (data / 'sources' / questions[cid]['project_group']).rglob('*'):
            if not p.is_file():
                continue
            raw = p.read_bytes()
            text = raw.decode()
            offsets = [0]
            for line in text.splitlines(keepends=True):
                offsets.append(offsets[-1] + len(line))
            prepared['sources'][p.relative_to(data / 'sources' / questions[cid]['project_group']).as_posix()] = dict(
                raw=raw, content=text, sha256=hashlib.sha256(raw).hexdigest(), line_offsets=offsets, errors=[])
        stages = []
        targets = []
        wanted = set(case['diagnostic']['selected_whole_ids'])
        for event in events:
            if not event['stage'].endswith('.output') or 'rows' not in event:
                continue
            intervals, errors = {}, []
            if event['rows'] and 'public' in event['rows'][0]:
                verified, intervals, errors = evaluator._source_rows({'sources': [r['public'] for r in event['rows']]}, prepared)
                if event['stage'] == 'project_docs_context.output':
                    for index, (row, check) in enumerate(zip(event['rows'], verified), 1):
                        if row['public']['evidence_id'] in wanted:
                            targets.append(dict(evidence_id=row['public']['evidence_id'], rank=index,
                                row=row, independent_source_receipt=check))
            else:
                for row in event['rows']:
                    relative = row['source'].removeprefix(prepared['root'] + '/')
                    raw = prepared['sources'][relative]['content']
                    assert hashlib.sha256(row['text'].encode()).hexdigest() == row['text_sha256']
                    spans = evaluator._occurrences(raw, row['text'], 0, len(raw))
                    if len(spans) == 1:
                        intervals.setdefault(relative, []).extend(spans)
                    elif not spans:
                        errors.append('no_source_occurrence')
            stages.append(dict(stage=event['stage'], sequence=event['sequence'], count=event['count'], integrity_errors=errors,
                               gold=evaluator._gold(questions[cid], gold[cid], prepared, intervals)))
        ledger = next(e for e in events if e['stage'] == 'budget.ledger')
        for target in targets:
            eid = target['evidence_id']
            target['trials'] = [dict(cost=e['cost'], cap=e['cap'], selected_before=len(e['selected_ids']), over_cap=e['over_cap'])
                                for e in events if e['stage'] == 'budget.cost' and (e.get('option') or {}).get('evidence_id') == eid]
            target['omitted'] = eid in ledger['all_omitted_evidence_ids']
            target['reason'] = 'full_DTO_cost_exceeds_12000' if target['omitted'] else 'retained'
            snippet = target['row']['public']['snippet']
            target['upstream_occurrences'] = [dict(stage=e['stage'], sequence=e['sequence'], positions=[i+1 for i, r in enumerate(e['rows']) if r.get('text') == snippet])
                for e in events if e['stage'] in ('_search_rows.output', 'acquire_candidates.output', 'select_experimental_candidates.output')]
            target['admission'] = [dict(sequence=e['sequence'], accepted=e['accepted'], reason=e['reason'])
                for e in events if e['stage'] == 'admission' and e['candidate']['text'] == snippet]
        final = json.loads((args.run / (cid + '-on-public.json')).read_text())
        fmt = {}
        for label, representation in [('shared_request', normalized(final)), ('shared_request_and_document', normalized(final, True))]:
            fmt[label] = dict(measurement=cost(representation), exact_roundtrip=True,
                              compatible_without_decoder_change=False)
        compact = json.dumps(final, ensure_ascii=False, separators=(',', ':')).encode()
        compact_tokens = projection_token_count(compact)
        fmt['whitespace_only'] = dict(bytes=len(compact), codec_tokens=compact_tokens,
            utf8_div4=math.ceil(len(compact)/4), cost=max(compact_tokens, math.ceil(len(compact)/4)),
            json_semantic_compatibility=True, changes_actual_serializer=True)
        # Even the prefix THROUGH the last required row has a lower bound: raw
        # unescaped snippets alone. This does not prove no arbitrary format fits.
        projected = next(e for e in events if e['stage'] == 'project_docs_context.output')['rows']
        last_rank = max(t['rank'] for t in targets)
        prefix_text = ''.join(r['public']['snippet'] for r in projected[:last_rank]).encode()
        output.append(dict(case_id=cid, stages=stages, targets=targets, ledger=ledger,
            public_count=len(final['sources']), format_counterfactuals=fmt,
            prefix_through_last_target=dict(rank=last_rank, raw_snippet_bytes=len(prefix_text),
                standalone_codec_tokens=projection_token_count(prefix_text), note='Raw source text only; not full DTO and not impossibility proof'),
            final_field_standalone_costs={k: cost({k: v}) for k, v in final.items() if k != 'sources'}))
    args.output.write_text(json.dumps(dict(cases=output, product_calls=0, unchanged_original_evaluator=True), ensure_ascii=False, indent=2) + '\n')
    for c in output:
        print(c['case_id'], c['format_counterfactuals'], c['prefix_through_last_target'])


if __name__ == '__main__':
    main()

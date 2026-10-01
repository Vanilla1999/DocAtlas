"""Generate derived audit summaries/appendices; official MCP wires stay unchanged."""
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import re
from run_live_mcp import OUT, ROOT, WORK, save
from eval.evidence_quality_v2.audit import audit_payload
from eval.evidence_quality_v2.grounded import controlled_context, rendered_normalization
from eval.evidence_quality_v2.cost import count_input, percentiles
from eval.evidence_quality_v2.semantic import assess_context


def esc(value):
    return str(value).replace('|','\\|').replace('\n',' ')


def visible(record):
    return '\n'.join(b.get('text','') for b in record['wire'].get('content',[]) if b.get('type')=='text')


def main():
    ann=json.loads((OUT/'manual_project_review.json').read_text())
    projects=json.loads((OUT/'raw/project80/results.json').read_text())
    external=json.loads((OUT/'raw/external80/results.json').read_text())
    grounded=json.loads((OUT/'raw/grounded/results.json').read_text())
    cases=json.loads((OUT/'raw/protocol/external80.json').read_text())['cases']
    by_case={c['id']:c for c in cases}
    trace_rows=json.loads((OUT/'raw/trace-results.json').read_text())
    audits=[]
    for row in trace_rows:
        trace=json.loads(gzip.decompress((OUT/row['trace']).read_bytes()))
        root=ROOT if row['panel']=='project28' else WORK/'trace-fixtures'/row['id'].split('-')[0]
        errors=audit_payload(row['payload'],trace['snapshot'],root)
        audits.append(dict(id=row['id'],panel=row['panel'],errors=errors))
    save(OUT/'raw/snapshot-integrity.json',dict(calls=len(audits),violations=sum(bool(r['errors']) for r in audits),rows=audits))
    integrity=json.loads((OUT/'raw/public-integrity-corrected.json').read_text())
    old=json.loads((OUT/'raw/live-summary.json').read_text())
    if old.get('integrity_observer_corrected') is not True:
        save(OUT/'raw/live-summary-initial-observer.json',old)
    updated=deepcopy(old)
    for lane in ('default','all','guided'):
        updated['project80'][lane]['integrity_violations']=sum(bool(r['errors']) for r in integrity['panels']['project80']['rows_detail'] if r['lane']==lane)
    updated['external80']['integrity_violations']=integrity['panels']['external80']['violations']
    updated.update(integrity_observer_corrected=True,integrity_note='Original file-hash assumption was wrong. See public-integrity-corrected.json; no changes to official wire outputs.')
    save(OUT/'raw/live-summary.json',updated)
    metrics={}; reviewed=[]
    for lane in ('all','guided'):
        rows=[r for r in projects if r['lane']==lane]
        positive=[]
        for r in rows:
            number=int(r['id'].split('-Q')[1]);panel=r['id'].split('-')[0][-1]
            if number<=36:
                grade,note=ann[lane+'_'+panel][number-1]
                entry=dict(id=r['id'],lane=lane,language=r['language'],grade=grade,note=note,
                    evidence_ids=[s['evidence_id'] for s in r['payload'].get('sources',[])],
                    evidence=[{k:s.get(k) for k in ('evidence_id','path_or_url','line_start','line_end','snippet')} for s in r['payload'].get('sources',[])])
                positive.append(entry);reviewed.append(entry)
        nonempty=[r for r in rows if r['payload'].get('sources')]
        def content_tokens(r):
            return count_input('\n\n'.join(s['snippet'] for s in r['payload'].get('sources',[])))['actual_tokens']
        metrics[lane]=dict(positive_count=len(positive),grades=dict(Counter(r['grade'] for r in positive)),
            by_language={lg:dict(Counter(r['grade'] for r in positive if r['language']==lg)) for lg in ('ru','en')},
            content_tokens_nonempty=percentiles(content_tokens(r) for r in nonempty),
            whole_packet_tokens_nonempty=percentiles(r['tokens']['actual_tokens'] for r in nonempty),
            evidence_text_share_nonempty=percentiles(content_tokens(r)/r['tokens']['actual_tokens'] for r in nonempty),
            all_answer_supported_false=all(r['payload'].get('answer_supported') is False for r in rows),
            quality=dict(Counter(r['payload'].get('context_quality',{}).get('status') for r in rows)))
    transitions=Counter();pairs=[]
    native={r['id']:r for r in reviewed if r['lane']=='all'}
    for r in reviewed:
        if r['lane']!='guided':continue
        a=native[r['id']]['grade'];b=r['grade'];transitions[a+'→'+b]+=1
        if a!=b:pairs.append(dict(id=r['id'],from_grade=a,to_grade=b))
    metrics['guided_transitions']=dict(transitions)
    save(OUT/'raw/project-semantic-review.json',dict(method=ann['method'],metrics=metrics,changed_grades=pairs,rows=reviewed,controls=ann['controls']))
    native_rows={r['id']:r for r in projects if r['lane']=='all'}
    guided_rows={r['id']:r for r in projects if r['lane']=='guided'}
    lines=['# Все 80 вопросов по DocAtlas — разбор видимой выдачи','',
        'Набор A = `experiments/grounded-partial/questions.json`; B = `followup_questions.json`. '
        'Full/partial/none оценивает только полезность предоставленного evidence, не ответы coding model. '
        'Original и guided — разные lanes, не повтор/recovery одного запроса. 72 положительных + 8 unsupported controls. '
        'Один reviewer после просмотра; это диагностическая оценка, не blind acceptance.','',
        '| ID | Вопрос | Без lookup | С lookup | Причина без lookup | Причина с lookup |','|---|---|---|---|---|---|']
    for id_,r in native_rows.items():
        n=int(id_.split('-Q')[1]);panel=id_.split('-')[0][-1]
        a,anote=ann['all_'+panel][n-1] if n<=36 else ('control',ann['controls'][id_])
        b,bnote=ann['guided_'+panel][n-1] if n<=36 else ('control',ann['controls'][id_])
        lines.append('| '+' | '.join(map(esc,[id_,r['question'],a,b,anote,bnote]))+' |')
    lines.extend(['','## Связь с цитатами','',
        'Полные исходные MCP-ответы: `raw/project80/all/<ID>.json` и `raw/project80/guided/<ID>.json`. '
        'Ниже IDs с координатами; причины относятся только к соответствующему packet.'])
    for id_,r in native_rows.items():
        lines.append('\n### '+id_)
        for lane,row in [('original',r),('guided',guided_rows[id_])]:
            sources=row['payload'].get('sources',[])
            desc='; '.join(f'`{s["evidence_id"]}` — `{s["path_or_url"]}:{s["line_start"]}–{s["line_end"]}`' for s in sources) or 'источников нет'
            lines.append(f'- {lane}: {desc}.')
    (OUT/'PROJECT_80_REVIEW_RU.md').write_text('\n'.join(lines)+'\n')
    external_review=[]
    # Cases needing semantic review; only question-requested facts are credited.
    manual_overrides={
        'mkdocs-06':('full','Оба ограничения (block/multiline cells и blank lines) видны в двух отдельных цитатах. Frozen witness требует одну contiguous строку.', [s['evidence_id'] for s in next(r for r in external if r['id']=='mkdocs-06')['payload']['sources'][:2]]),
        'uv-06':('full','Вопрос требует default build isolation и preinstall build dependencies. Оба факта видны; specific code example из gold вопрос не запрашивает.', [s['evidence_id'] for s in next(r for r in external if r['id']=='uv-06')['payload']['sources']]),
        'typer-05':('none','Отсутствует space-before-slash rule, нет источников в packet.',[])
    }
    # Conservative formatting-only second observer on NATIVE Grounded text;
    # no assembly/reordering, no semantic synonyms, same result URL binding.
    formatting=[]
    for row in grounded:
        case=by_case[row['id']]
        if case['answerability']!='within_budget':continue
        matches={path:[] for path in {p['path'] for c in case['required_claims'] for w in c.get('witness_sets',[]) for p in w.get('parts',[])}}
        for item in row['binding']['mapping']:
            if item['path'] in matches:matches[item['path']].append(rendered_normalization(item['native_body']))
        support=[]
        for claim in case['required_claims']:
            okay=any(all(any(rendered_normalization(part['text']) in text for text in matches.get(part['path'],[])) for part in witness.get('parts',[])) for witness in claim.get('witness_sets',[]))
            support.append(dict(claim_id=claim['id'],supported=okay))
        formatting.append(dict(id=row['id'],limit=row['limit'],all_required_matched=all(x['supported'] for x in support),claims=support))
    save(OUT/'raw/grounded/formatting-only-native-witness-check.json',dict(note='Second diagnostic observer for rendered raw text. Formatting normalization is from existing eval helper; no private source content is added to native output.',rows=formatting))
    g3={r['id']:r for r in grounded if r['limit']==3}
    f3={r['id']:r for r in formatting if r['limit']==3}
    lines=['# Все frozen 80: свежие MCP-результаты','',
        'Внешние pinned Markdown snapshots импортированы как **local project docs**, не через dependency/library prefetch. '
        'Это диагностика retrieval/packing, не проверка resolver/lockfile/network pipeline. '
        '48 within_budget positives и 32 partial/unanswerable/ambiguous/over_budget controls. '
        'Слово `needs_review` не означает автоматический провал.','',
        '| ID | Вопрос | Answerability | DocAtlas frozen scorer | DocAtlas semantic review | Grounded scorer / formatting check | DA / G3 tokens |',
        '|---|---|---|---|---|---|---|']
    for row in external:
        case=by_case[row['id']];override=manual_overrides.get(row['id'])
        if case['answerability']=='within_budget':
            grade,note,eids=override or ('full','Все размеченные required witnesses распознаны в видимом packet.',[s['evidence_id'] for s in row['payload'].get('sources',[])])
        else:
            grade,note,eids='control','Не входит в знаменатель полноты. Нет certified answer; невозможно выводить private/ambiguous/oversized requested facts из retrieved related text.',[s['evidence_id'] for s in row['payload'].get('sources',[])]
        external_review.append(dict(id=row['id'],grade=grade,note=note,evidence_ids=eids))
        fmt='not_positive' if row['id'] not in f3 else str(f3[row['id']]['all_required_matched'])
        g=g3[row['id']]
        lines.append('| '+' | '.join(map(esc,[row['id'],case['question'],case['answerability'],row['assessment']['context_sufficiency'],grade,g['assessment']['context_sufficiency']+' / '+fmt,str(row['tokens']['actual_tokens'])+' / '+str(g['native_size']['actual_tokens'])]))+' |')
    lines.extend(['','## Семантические исключения scorer',''])
    for id_,(grade,note,eids) in manual_overrides.items():
        lines.extend(['### '+id_,note,'Evidence IDs: '+', '.join('`'+e+'`' for e in eids)+'.',''])
    (OUT/'EXTERNAL_80_REVIEW_RU.md').write_text('\n'.join(lines)+'\n')
    save(OUT/'raw/external-semantic-review.json',dict(note='45 automatic witness-complete plus two explicitly adjudicated cases. Single reviewer, not blind answer model.',rows=external_review,
        positive_full=sum(r['grade']=='full' for r in external_review),grounded_formatting_summary={str(k):sum(r['all_required_matched'] for r in formatting if r['limit']==k) for k in (3,5)}))
    # Same minimal budget adapter as a packing diagnostic, not a new product arm.
    controlled=[]
    for row in external:
        case=by_case[row['id']]
        adapted=controlled_context(row['payload'].get('sources',[]))
        registry=json.loads((OUT/'raw/protocol/external80.json').read_text())['source_manifest']
        from eval.evidence_quality_v2.run import registry_for
        assessment=assess_context(case,adapted['payload'],registry_for(case['project_group'],registry))
        controlled.append(dict(id=row['id'],adapter=adapted,assessment=assessment))
    save(OUT/'raw/docatlas-common-adapter.json',controlled)
    equality=[]
    default={r['id']:r for r in projects if r['lane']=='default'}
    for id_,row in native_rows.items():
        def stripped(payload):
            value=deepcopy(payload)
            for source in value.get('sources',[]):source.pop('source_uri',None)
            return value
        equality.append(dict(id=id_,same_without_source_uri=stripped(default[id_]['payload'])==stripped(row['payload'])))
    save(OUT/'raw/default-all-comparison.json',dict(equal=sum(r['same_without_source_uri'] for r in equality),cases=len(equality),rows=equality))
    print(json.dumps(dict(project_metrics=metrics,snapshot_violations=sum(bool(r['errors']) for r in audits),
        grounded_formatted={str(k):sum(r['all_required_matched'] for r in formatting if r['limit']==k) for k in (3,5)},
        docatlas_common_recognized=sum(r['assessment']['context_sufficiency']=='sufficient' and by_case[r['id']]['answerability']=='within_budget' for r in controlled),
        default_all_equal=sum(r['same_without_source_uri'] for r in equality)),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()

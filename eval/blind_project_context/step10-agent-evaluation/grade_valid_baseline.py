"""Transcribe independent manual final-answer grading of completed file sessions.

Grades are specific to the inspected /terra-step10-prepared file-current
answers. They are not keyword inference or a scorer for future answers.
"""
import hashlib
import json
from pathlib import Path
import re

from account_sessions import account

HERE = Path(__file__).resolve().parent
CORPORA = Path('/tmp/opencode/step8-corpora2')
ROOT = Path('/tmp/opencode/terra-step10-prepared')

# One exact answer excerpt for each oracle fact in order, independently read.
EXCERPTS = {
 ('L0','T01-en'): ['`feat/<topic>` or `fix/<description>`', 'Run the full test suite before opening the PR', 'Include tests for new connectors or fetchers where practical.'],
 ('L0','T01-ru'): ['`feat/<тема>` или `fix/<описание>`', 'До открытия PR запустите полный набор тестов', 'Для новых коннекторов или источников данных добавьте тесты там, где это практически возможно.'],
 ('L2','T01-en'): ['`feat/<topic>` or `fix/<description>`', 'Run the full test suite.', 'If you add a connector or fetcher, include tests where practical.'],
 ('L2','T01-ru'): ['`feat/<topic>` или `fix/<description>`', 'До открытия PR запустить полный набор тестов.', 'Для новых коннекторов или fetcher’ов добавить тесты там, где это практически возможно.'],
 ('L0','T02-ru'): ['Без `--apply` она только показывает план.', 'сохраняя исходники проекта, `docatlas.yaml`, конфигурацию и посторонние файлы.', 'Примените именно проверенный план:'],
 ('L2','T02-ru'): ['По умолчанию `clear-index` ничего не удаляет: применение требует `--apply`.', 'сохраняя исходники проекта, `docatlas.yaml`, конфигурацию и посторонние файлы.', 'передав его `plan_digest`'],
 ('L0','T05-ru'): ['установленный wheel, реальный project-installer, stdio MCP, SQLite и MiniLM', 'не автономные запуски OpenCode с моделью и не тесты расхода токенов'],
 ('L2','T05-ru'): ['установленный wheel, настоящий проектный установщик, stdio MCP, SQLite и MiniLM', 'не автономные запуски OpenCode с моделью и не бенчмарки расхода токенов'],
 ('L0','T10-ru'): ['один и тот же исходный пользовательский вопрос через настоящий публичный API, CLI или MCP', 'logging off и on', 'Два одинаковых неверных ответа не означают PASS'],
 ('L2','T10-ru'): ['один и тот же пользовательский вопрос через настоящий публичный API, CLI или MCP', 'logging off и on', 'Два одинаковых неверных ответа не считаются PASS'],
 ('L0','T12-ru'): ['Чтение само по себе не обновляет индекс и не меняет репозиторий.', 'В `docatlas.project-docs.yaml` документы перечисляются по буквальным относительным путям.', 'без `mutation` ничего не записывает'],
 ('L2','T12-ru'): ['Сервер не генерирует и не коммитит официальную документацию проекта.', 'явно перечисленные относительными путями в `docatlas.project-docs.yaml`', 'Сам по себе `prepare_docs(action="sync_project_docs")` ничего не записывает'],
 ('L0','T15-en'): ['adapter drops response `_meta`', 'the original source packet would be lost and the response’s short references would no longer resolve'],
 ('L2','T15-en'): ['adapter drops response `_meta`', 'the original packet is lost and the short references in the response cannot be resolved'],
 ('L0','T19-ru'): ['группа **`doc-atlas qdrant`**', '`doc-atlas qdrant up` — скачать при необходимости и запустить Qdrant в фоне.', '`doc-atlas qdrant down` — остановить управляемый процесс.', '`doc-atlas qdrant status` — показать состояние, включая PID, порт, URL, работоспособность и версию'],
 ('L2','T19-ru'): ['группа команд **`doc-atlas qdrant`**', '`doc-atlas qdrant up` — скачать закреплённый бинарный файл при необходимости', '`doc-atlas qdrant down` — остановить управляемый процесс', '`doc-atlas qdrant status` — показать PID, порт, URL, состояние процесса'],
}
REASONS = {
 'T01.F1': 'States both feat/ and fix/ branch patterns; translated placeholders preserve the convention.',
 'T01.F2': 'Requires the full test suite before opening the PR; in L2-en the introductory sentence supplies the timing.',
 'T01.F3': 'Requires tests for new connectors/fetchers where practical; Russian L0 source-provider wording is a faithful contextual paraphrase.',
 'T02.F1': 'Names clear-index, distinguishes preview from --apply, and tells the user to review a bounded explicit plan before deletion.',
 'T02.F2': 'Explains the global/shared local-index scope and expressly preserves configuration, contrasting clear-index with broader clear.',
 'T02.F3': 'Binds execution to the reviewed plan_digest, including a --plan-digest example and stale-plan refusal.',
 'T05.F1': 'Explicitly lists installed wheel, actual installer, stdio MCP, SQLite and MiniLM.',
 'T05.F2': 'Explicitly excludes autonomous OpenCode/model execution and token benchmarking from the verification claim.',
 'T10.F1': 'Reproduces one original user question through real public API/CLI/MCP, with real components.',
 'T10.F2': 'Requires log-off/on runs from identical initial index/cache/permissions/consent states.',
 'T10.F3': 'Requires independent checking of both outcomes and parity; explicitly rejects two identical wrong answers as PASS.',
 'T12.F1': 'Explicitly states reads do not update/reconcile the index or change the repository.',
 'T12.F2': 'Requires explicit literal-path catalog membership and rejects implicit discovery by filenames/directories/links.',
 'T12.F3': 'States that bare sync_project_docs does not write; confirmed mutation/source bindings are required.',
 'T15.F1': 'PARTIAL: correctly states response _meta is dropped, but does not state that structuredContent AND content are retained. Citation availability cannot fill omitted final-answer facts.',
 'T15.F2': 'Explicitly connects losing the original source packet to unresolvable response-local short references.',
 'T19.F1': 'Identifies the local doc-atlas qdrant lifecycle group and the managed-process boundary in the surrounding bullets.',
 'T19.F2': 'Identifies qdrant up as downloading the pinned binary and starting the managed process.',
 'T19.F3': 'Identifies qdrant down as stopping the managed process.',
 'T19.F4': 'Identifies qdrant status and its PID/port/URL/process-state reporting.',
}


def cited_ranges(answer):
    """Extract displayed path/line citations, retaining link-target differences."""
    result=[]
    for match in re.finditer(r'\[([^\]\n]+)\](?:\(([^)]+)\))?', answer):
        label,target=match.groups()
        for piece in label.split(';'):
            citation=re.search(r'([\w./-]+\.(?:md|yaml))(?::|,\s*строки\s*)([\d\s,–—-]+)',piece)
            if not citation:
                continue
            path,ranges=citation.groups()
            spans=[]
            for item in ranges.strip().split(','):
                span=re.fullmatch(r'\s*(\d+)(?:[–—-](\d+))?\s*',item)
                if span:
                    a,b=span.groups();spans.append([int(a),int(b or a)])
            result.append({'path':path,'ranges':spans,'displayed':match[0],'link_target':target})
    return result


def observed_lines(row, project):
    seen={}; anomalies=[]
    for tool in row['tool_trace']:
        state=tool['state'];output=state.get('output',''); current=None
        if tool['tool']=='read' and state.get('status')=='completed':
            candidate=Path(state['input']['path'])
            if candidate.is_file() and candidate.is_relative_to(project):
                current=candidate.relative_to(project).as_posix()
        for line in output.splitlines():
            if tool['tool']=='grep' and line.endswith(':') and line.startswith(str(project)+'/'):
                current=line[len(str(project))+1:-1]
            pattern=r'^(\d+): ?(.*)$' if tool['tool']=='read' else r'^\s+Line (\d+): ?(.*)$'
            found=re.match(pattern,line)
            if current and found:
                number,body=found.groups();number=int(number)
                source=(project/current).read_text().splitlines()
                if number<1 or number>len(source) or body!=source[number-1]:
                    anomalies.append({'path':current,'line':number,'tool_text':body})
                else:
                    seen.setdefault(current,set()).add(number)
    return seen,anomalies


def citation_specs(corpus,topic,index):
    if topic=='T01':return [('CONTRIBUTING.md',61+index,61+index)]
    if topic=='T02':return [[('docs/index-cleanup.md',3,6)],[('docs/index-cleanup.md',64,67),('docs/index-cleanup.md',3,4)],[('docs/index-cleanup.md',35,39)]][index]
    if topic=='T05':return [('docs/PROJECT_BINDING.md',75 if index==0 else 79,75 if index==0 else 79)]
    if topic=='T10':return [('docs/main-flow-evaluation.md',[19,22,23][index],[19,22,23][index])]
    if topic=='T12':
        if index==0:return [('docs/mcp-docs-server.md',84,85)] if corpus=='L0' else []
        if index==1:return [('docs/project-docs-mcp-workflow.md',25,28)]
        return [('docs/mcp-docs-server.md',89,90)] if corpus=='L0' else [('docs/project-docs-mcp-workflow.md',63,65)]
    if topic=='T15':return [('docs/opencode-compact-text.md',41,41)] if index==0 else [('docs/opencode-compact-text.md',44,45)]
    if topic=='T19':return [('wiki/Commands.md',[106,110,111,112][index],[106,110,111,112][index])]
    raise ValueError(topic)


def main():
    accounting=account(ROOT,arm_filter='file-current')
    assert len(accounting['sessions'])==16
    frozen=HERE.parent
    questions={q['id']:q for q in json.loads((frozen/'questions.json').read_text())['cases'] if q['id'] in {r['case'] for r in accounting['sessions']}}
    assert all(q['split']=='dev' for q in questions.values())
    topics={q['topic_id'] for q in questions.values()}
    gold={t['topic_id']:t for t in json.loads((frozen/'oracle.json').read_text())['topics'] if t['topic_id'] in topics}
    allfacts={f['fact_id'] for t in gold.values() for f in t['facts']}
    witnesses={w['fact_id']:w for w in json.loads((frozen/'witness-audit.json').read_text())['facts'] if w['fact_id'] in allfacts}
    for row in accounting['sessions']:
        corpus,case=row['corpus'],row['case'];topic=questions[case]['topic_id']
        project=CORPORA/(corpus+'-0')/'project'
        answer=row['final_answer'];citations=cited_ranges(answer)
        seen,anomalies=observed_lines(row,project)
        assert not anomalies,anomalies
        row.update(question=questions[case],citations=citations,source_text_anomalies=anomalies,
                   observed_source_lines={p:sorted(v) for p,v in seen.items()},facts=[])
        for i,fact in enumerate(gold[topic]['facts']):
            factid=fact['fact_id']; excerpt=EXCERPTS[corpus,case][i]
            assert excerpt in answer,(corpus,case,factid)
            partial=topic=='T15' and i==0 or corpus=='L2' and topic=='T12' and i==0 or corpus=='L0' and topic=='T19' and i==1
            reason=REASONS[factid]
            if corpus=='L2' and factid=='T12.F1':reason='PARTIAL: forbids generating/committing documentation, but does not state that reads never reconcile the index and never write to the repository. Readiness/mutation discussion does not supply this read-path guarantee.'
            if corpus=='L0' and factid=='T19.F2':reason='PARTIAL: gives qdrant up download/start behavior but omits that the downloaded binary is pinned; the cited source includes this qualifier.'
            evidence=[]
            for path,a,b in citation_specs(corpus,topic,i):
                source=project/path;lines=source.read_text().splitlines(keepends=True)
                cited=any(c['path']==path and all(any(lo<=n<=hi for lo,hi in c['ranges']) for n in range(a,b+1)) for c in citations)
                retrieved=all(n in seen.get(path,set()) for n in range(a,b+1))
                assert cited and retrieved,(corpus,case,factid,path,a,b,cited,retrieved)
                evidence.append({'path':path,'line_start':a,'line_end':b,'text':''.join(lines[a-1:b]),
                    'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'cited_in_final':cited,'observed_in_tool_output':retrieved})
            original=[]
            for witness in witnesses[factid]['occurrences'][corpus]:
                path=witness['path'];a,b=witness['line_start'],witness['line_end']
                text=''.join((project/path).read_text().splitlines(keepends=True)[a-1:b])
                assert fact['quote'] in text
                original.append({**witness,'text':text,'observed_in_tool_output':all(n in seen.get(path,set()) for n in range(a,b+1))})
            row['facts'].append({**fact,'answer_grade':'PARTIAL' if partial else 'PASS','binary_pass':not partial,
                'answer_excerpt':excerpt,'reason':reason,'citation_grade':'PASS' if evidence else 'FAIL',
                'citation_reason':'Displayed source citation covers independently checked supporting source lines, actually observed in the tool output. This does not complete any omitted answer qualifier.' if evidence else 'No citation presents the missing read-path guarantee; a documentation-mutation restriction is not the same fact.',
                'citation_evidence':evidence,'frozen_witnesses':original})
        row['grading_status']='independent manual final-answer and per-fact citation review complete'
        row['answer_pass']=all(f['binary_pass'] for f in row['facts'])
        row['required_fact_citation_pass']=all(f['citation_grade']=='PASS' for f in row['facts'])
        row['retrieval_status']='successful_real_file_reads_or_grep'
        # Multi-range visible labels may expose more than their clickable anchor.
        row['citation_presentation_notes']=[c['displayed'] for c in citations if c['link_target'] and len(c['ranges'])>1]
    facts=[f for row in accounting['sessions'] for f in row['facts']]
    accounting.update(evaluation='fresh valid baseline, manual dev-only answer/citation grading',
        grading_contract='Semantic paraphrases count, but all material qualifiers in each frozen required fact must appear in the final answer for binary PASS. PARTIAL counts as zero, with exact omitted qualifier recorded. A citation to complete source text does not repair omitted answer content. Citation support is graded separately and can PASS for a partial answer. Alternative independently checked source passages may support the same fact.',
        grading_scope='Required facts/citations only, not exhaustive verification of every additional sentence. Multi-range citation labels are used as displayed; narrower clickable anchor targets are noted separately.',
        prior_invalid_baseline='baseline.json / baseline.md and failed-attempts.json are historical denied-access/setup attempts; excluded from this valid baseline.',
        frozen_artifact_sha256={name:hashlib.sha256((frozen/name).read_bytes()).hexdigest() for name in ['questions.json','oracle.json','witness-audit.json']})
    accounting['summary'].update(facts_pass=sum(f['binary_pass'] for f in facts),facts_total=len(facts),
        facts_partial=sum(f['answer_grade']=='PARTIAL' for f in facts),citations_supported=sum(f['citation_grade']=='PASS' for f in facts),
        answers_pass=sum(r['answer_pass'] for r in accounting['sessions']),sessions_with_retrieval=16,
        comparison_valid=True,seconds_sum=sum(r['receipt']['seconds'] for r in accounting['sessions']))
    (HERE/'baseline-valid.json').write_text(json.dumps(accounting,ensure_ascii=False,indent=2)+'\n')
    md=['# Fresh valid file baseline: independent final-answer review','',
        'Source: `/tmp/opencode/terra-step10-prepared/{L0,L2}/file-current`. All 16 completed sessions used real permitted file reads/search. Historical denied-access baseline remains separate.','',
        '## Result','',json.dumps(accounting['summary'],indent=2),'',accounting['grading_contract'],'',
        'Four partial facts: both T15 answers omit retention of structuredContent/content; L2 T12 omits the no-reconcile/no-repository-write read guarantee; L0 T19 omits the pinned-binary qualifier. These are final-answer omissions even where the relevant source was retrieved and cited.','',
        '| Corpus/case | Facts | Supported fact citations | Input | Cache read | Output | Reasoning | Tools |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in accounting['sessions']:
        u=r['usage'];md.append(f"| {r['corpus']}/{r['case']} | {sum(f['binary_pass'] for f in r['facts'])}/{len(r['facts'])} | {sum(f['citation_grade']=='PASS' for f in r['facts'])}/{len(r['facts'])} | {u['input']} | {u['cache_read']} | {u['output']} | {u['reasoning']} | {u['top_level_tool_calls']} |")
    for r in accounting['sessions']:
        md += ['',f"## {r['corpus']}/{r['case']}",'',r['question']['question'],'','### Actual final answer','',r['final_answer'],'','### Required facts and citations','']
        for f in r['facts']:
            md += [f"- **{f['fact_id']}: {f['answer_grade']}; citation {f['citation_grade']}.** {f['reason']} Answer excerpt: {f['answer_excerpt']}"]
        if r['citation_presentation_notes']:
            md += ['','Citation presentation: some displayed labels list multiple ranges while the clickable fragment points only to the first. Supporting displayed ranges were checked independently; do not interpret this as exact clickable-range parity.']
    md += ['','## Accounting and evidence boundary','',
           'Step input/cache/output/reasoning totals reconcile exactly with session metadata. Input-with-cache is input plus cache-read, consistent with the previous analyzer. Output and reasoning are not added as a new billing metric. Tool calls are actual recorded top-level invocations. Completion and exit 0 were not used as answer grades.',
           'The JSON includes final answers, exact tool traces, all step usage, input-artifact hashes, inspected supporting source excerpts/coordinates/hashes, frozen witness excerpts, and per-fact reasons. Only the authorized dev cases were reviewed. No questions, sources, labels, policy, production code or agent runner changed. No extra agent/model calls were made for grading.',
           'Source-output checks verify actual numbered read/grep lines against frozen files rather than assuming a requested read range was delivered. Required facts may be supported by independently verified equivalent source passages rather than only the original oracle location. Additional non-required advice is not exhaustively graded.','']
    (HERE/'baseline-valid.md').write_text('\n'.join(md))
    print(json.dumps(accounting['summary'],indent=2))


if __name__=='__main__':main()

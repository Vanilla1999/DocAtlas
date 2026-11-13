"""SEALED authoring record; do not open until variants frozen. Refuses refreezing."""
from pathlib import Path
import json
import hashlib
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
H = lambda b: hashlib.sha256(b).hexdigest()
# Manually authored questions and complete source-witness obligations, before execution.
DATA = [
('F01','dev','docs/development/python-module-size-policy.md',
 'What hard size bound applies to hand-written Python modules, what files does its gate scan or exclude, and what is required if a module crosses it?',
 'Какой жёсткий предел размера действует для написанных вручную Python-модулей, какие файлы проверка охватывает или исключает и что требуется при превышении?',
 [(5,5,'Hard physical-line bound; hand-written production/evaluation/test scope; not a quality score.'),(21,23,'Untracked files included; only environment/build/cache exclusions; pre-merge split; all temporary-waiver conditions and current absence.')],['T01'],
 'Module-size enforcement and waiver policy, not the old PR submission checklist.'),
('F02','dev','docs/development/python-module-size-policy.md',
 'When splitting a Python module, what boundaries and target size are recommended, and what compatibility duties apply to public imports and documented monkeypatch seams?',
 'Какие границы и целевой размер рекомендуются при разделении Python-модуля и какие обязанности совместимости действуют для публичных импортов и документированных точек monkeypatch?',
 [(9,11,'Practical target; responsibility not arbitrary splitting; naming caveat; stable imports; facade re-export; focused new logic; preserve or explicitly replace documented seams.')],['T01'],
 'Architecture decomposition and import/seam compatibility are absent from old PR gold; related development domain is acknowledged.'),
('F03','dev','docs/support-surface-policy.md',
 'Does the support inventory promise a migration window for removed surfaces, is the Python import namespace a deprecated alias, and how must public services gain supported status?',
 'Обещает ли реестр поддержки переходный период для удалённых интерфейсов, является ли пространство имён Python устаревшим псевдонимом и как публичные сервисы получают статус поддерживаемых?',
 [(18,22,'Current release only; explicit future-policy exception; no retired migration claims; distribution/CLI versus current import namespace; service registration and explicit tier decision.')],['T22'],
 'Support lifecycle and service-inventory admission, not MCP runtime settings.'),
('F04','dev','docs/support-surface-policy.md',
 'Under the support failure budgets, which failures block a release and how must an advanced-provider outage affect local Docs health? Include the Qdrant default-store exception and live-suite status.',
 'Согласно бюджетам отказов поддержки, какие сбои блокируют релиз и как отказ продвинутого провайдера должен влиять на здоровье локального Docs? Укажите исключение для хранилища Qdrant по умолчанию и статус live-наборов.',
 [(26,30,'Every failure-budget bullet: core blockers, scoped advanced degradation/local availability, maintenance availability exclusions, current default-store exception, cross-tier security/storage blocks, advisory live versus required offline.')],['T07','T19'],
 'Release health and outage isolation, not general security guarantees or Qdrant commands.'),
('F05','dev','docs/support-surface-policy.md',
 'What is the documented dependency-placement decision for Task 29 versus Task 24, including retained core dependencies, extras, and the prerequisites for moving Qdrant/FastEmbed?',
 'Каково документированное решение о размещении зависимостей для Task 29 и Task 24: что остаётся в core, что относится к extras и каковы условия переноса Qdrant/FastEmbed?',
 [(47,53,'No current Task 29 core change; migration condition on retained core; browser/crawler and hosted extras; conditional Qdrant/FastEmbed move with installer/default-fallback tests; USPTO existing versus future dependencies.')],['T19','T24'],
 'Packaging dependency boundaries, not Qdrant commands or pack source formats.'),
('F06','dev','docs/sdk-delivery-budgets.md',
 'How is the formatted SDK context budget measured, what is excluded from that measurement, and what happens to nonfitting windows, whitespace, zero, negative, and None budgets?',
 'Как измеряется бюджет форматированного SDK-контекста, что не входит в измерение и что происходит с неумещающимися окнами, пробелами, нулевым, отрицательным и None-бюджетом?',
 [(9,13,'Entire formatted-string formula including paths/titles/escaping/separators; approximate units, no tokenizer guarantee; external instructions/questions excluded.'),(17,23,'Corrected versus previous behavior; source whitespace and XML caveat; omit whole windows and continue in order without cropping; possibly empty despite get_chunks; zero/negative/None semantics.')],['T09','T20'],
 'SDK formatted-delivery arithmetic and boundary values, not project fragment admission or retrieval controls; expansion deliberately excluded.'),
('F07','holdout','docs/release-identity.md',
 'For the recorded existing-project PyPI publisher mismatch, where must the publisher be configured, which exact identity fields must match, and why is a pending publisher or a different environment insufficient?',
 'Для зафиксированного несовпадения PyPI publisher существующего проекта где следует настроить publisher, какие точные поля идентичности должны совпасть и почему pending publisher или другое environment не подходят?',
 [(81,96,'Existing-project Publishing location, not account-level pending publisher; all four exact fields; environment generally optional but must match this workflow.')],[],
 'External package-publisher identity remediation absent from all old topics.'),
('F08','holdout','docs/RELEASE_CHECKLIST.md',
 'What is the reviewed release controller sequence from release-request PR to publication, what can actually trigger publication, and when does human environment approval authorize it?',
 'Какова последовательность работы проверенного release controller от PR запроса релиза до публикации, что может запустить публикацию и когда человеческое одобрение environment её разрешает?',
 [(44,46,'Reviewed PR; required-ci on exact resulting main commit; unchanged main; create/idempotently verify immutable annotated tag; canonical dispatch; all artifact jobs prerequisite and environment-protection condition for human approval; dispatch-only, not tags/PRs.')],['T01'],
 'Release-controller state/authorization sequence, not contributor PR checklist; PR vocabulary is not the obligation.'),
('F09','holdout','docs/RELEASE_CHECKLIST.md',
 'Which gates are required to promote DocAtlas to Stable, is Context7 parity always a prerequisite, and what maturity remains when only artifact/release checks are green?',
 'Какие условия нужны для повышения DocAtlas до Stable, всегда ли паритет с Context7 обязателен и какая зрелость сохраняется, если зелёные только проверки артефактов/релиза?',
 [(83,90,'All P0/P1/P2 clauses including residual risk, installed frozen model benchmark, value or unsupported/wrong-version reduction and trajectory cost; separate parity protocol and conditional prerequisite; Beta despite artifact green.')],['T04','T05'],
 'Conjunctive maturity promotion policy, not evaluation-document locations or OpenCode verification coverage; domain proximity acknowledged.'),
('F10','holdout','docs/change-aware-docs.md',
 'In a docs-impact report, what distinguishes updated, review_required, and missing, and when does its normally informational CI report become blocking?',
 'Чем в отчёте docs-impact отличаются updated, review_required и missing и когда обычно информационный отчёт CI становится блокирующим?',
 [(24,30,'All three statuses with maintained-document/recognized-module conditions; PR job summary; informational default and opt-in fail-on-missing.')],['T23'],
 'Change-impact triage/report policy, not refetching registered documentation sources.'),
('F11','holdout','docs/change-aware-docs.md',
 'What does the docs-impact authoring_brief instruct the host model to include or verify, and what limits prevent advisory review or an unaccepted patch from becoming accepted documentation truth?',
 'Что authoring_brief в docs-impact предписывает модели-хосту включить или проверить и какие ограничения не дают рекомендательному обзору или непринятому патчу стать принятой истиной документации?',
 [(3,3,'Advisory inspection only; no autonomous generation/modification.'),(16,16,'Allowed files/headings, code/config/test verification, missing evidence, forbidden invented claims, no DocAtlas Markdown writes.'),(36,36,'Map is not correctness proof; read selected docs and propose reviewable diff; rejected or merely proposed patch must not sync as accepted truth.')],['T12'],
 'Host authoring-brief content and accepted-patch boundary, not catalog/read retrieval. Shared no-write principle acknowledged; brief and acceptance semantics are new.'),
('F12','holdout','docs/capabilities.md',
 'After a supported project lockfile changes a dependency from A to B, what evidence may a new query use, what happens if B is unavailable or ambiguous, and what are the cache, host re-query, and validation limits?',
 'После смены зависимости с A на B в поддерживаемом lockfile проекта какие свидетельства допустимы новому запросу, что происходит при недоступной или неоднозначной B и каковы ограничения кэша, повторного запроса хоста и валидации?',
 [(35,43,'Reread metadata; A ineligible but retained for other/historical use; matching B or actionable fail-closed request; no ambiguous latest; host re-query/no retroactive revocation; Pub between-call coverage not atomic/universal ecosystems; limited external coverage and explicit-source/unsupported result.')],['T23','T24'],
 'Lockfile eligibility transition and temporal validation, not source refresh command or pack formats.'),
]

def put(name, obj):
    p = HERE / name
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def main():
    if (HERE/'questions.json').exists() or (HERE/'manifest.json').exists():
        raise SystemExit('Frozen artifacts exist: never regenerate after outputs.')
    rev = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    paths = sorted({x[2] for x in DATA})
    sources, texts = [], {}
    for path in paths:
        b = subprocess.check_output(['git','show',f'{rev}:{path}'],cwd=ROOT)
        p = HERE/'corpus/project'/path
        p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f: f.write(b)
        texts[path] = b.decode('utf-8')
        sources.append({'path':path,'frozen_path':'corpus/project/'+path,'sha256':H(b),'bytes':len(b),'source_revision':rev,'git_blob':subprocess.check_output(['git','rev-parse',f'{rev}:{path}'],cwd=ROOT,text=True).strip()})
    put('corpus/project/docatlas.project-docs.yaml',{'schema_version':1,'code_files':[],'documentation_languages':{p:['en'] for p in paths},'documents':[{'path':p,'role':'other','scope':'project','description':'Frozen repository documentation: '+p,'authority':'source_of_truth','status':'active','impact':'track'} for p in paths]})
    cases,topics,audit = [],[],[]
    for fid,split,path,en,ru,groups,old,why in DATA:
        for lang,q in [('ru',ru),('en',en)]:
            c={'id':fid+'-'+lang,'topic_id':fid,'split':split,'lang':lang,'question':q}
            if lang=='ru': c['search_question']=en
            cases.append(c)
        lines=texts[path].splitlines(keepends=True)
        facts=[]
        for i,(a,b,obligation) in enumerate(groups,1):
            quote=''.join(lines[a-1:b]).rstrip('\n')
            start=sum(map(len,lines[:a-1]))
            assert texts[path][start:start+len(quote)]==quote
            facts.append({'fact_id':f'{fid}.F{i}','obligation':obligation,'quote':quote,'path':path,'line_start':a,'line_end':b,'char_start':start,'char_end':start+len(quote),'source_sha256':H(texts[path].encode()),'required':True})
        topics.append({'topic_id':fid,'split':split,'answerable':True,'negative_kind':None,'path':path,'complete_answer_rule':'Every obligation and all qualifications required. Witness coverage certifies retrieval delivery, not answer correctness.','facts':facts})
        audit.append({'family_id':fid,'split':split,'nearest_old_topics':old,'independence_rationale':why})
    put('questions.json',{'schema_version':1,'state':'FINAL_FROZEN_DO_NOT_EDIT','holdout_policy':'DO_NOT_OPEN_UNTIL_VARIANTS_FROZEN','corpus':'FRESH17','cases':cases})
    put('oracle.json',{'schema_version':2,'state':'SEALED_DO_NOT_OPEN_UNTIL_VARIANTS_FROZEN','questions_sha256':H((HERE/'questions.json').read_bytes()),'line_convention':'1-based inclusive; char offsets zero-based half-open Unicode; source SHA256 exact UTF-8 bytes','topics':topics})
    put('overlap-audit.sealed.json',{'state':'SEALED_DO_NOT_OPEN_UNTIL_VARIANTS_FROZEN','method':'All old questions and gold read to exclude semantic families, not merely words. No outputs or scores consulted. Separate corpus because exposed L0 heavily covers MCP/retrieval operations; independent repository documents, not an independent repository.','old_questions_sha256':H((ROOT/'eval/blind_project_context/questions.json').read_bytes()),'old_oracle_sha256':H((ROOT/'eval/blind_project_context/oracle.json').read_bytes()),'families':audit,'limitations':['Same repository and author; no claim of unseen pretraining or Lead exposure.','Sibling decisions share documents: do not treat 12 families as 12 independent domains or ru/en as independent samples.','All answerable; no retrieval or answerability negatives.','Policies may be historical/planned: judge frozen documented claims, not current implementation truth.']})
    put('manifest.json',{'schema_version':1,'state':'FINAL_FROZEN','corpus_id':'FRESH17','source_repository':'local DocAtlas repository','source_revision':rev,'source_method':'Exact git show REV:path bytes; not dirty working-tree text','license':'Existing repository terms; modest internal copies, no external material','counts':{'families':12,'dev_families':6,'holdout_families':6,'cases':24,'documents':len(paths),'obligation_groups':sum(len(t['facts']) for t in topics)},'documents':sources,'catalog_sha256':H((HERE/'corpus/project/docatlas.project-docs.yaml').read_bytes()),'questions_sha256':H((HERE/'questions.json').read_bytes()),'oracle_sha256':H((HERE/'oracle.json').read_bytes()),'overlap_audit_sha256':H((HERE/'overlap-audit.sealed.json').read_bytes()),'author_record_sha256':H(Path(__file__).read_bytes()),'old_corpus_builder_sha256':H((ROOT/'eval/blind_project_context/corpus.py').read_bytes()),'construction_activity':{'inference_calls':0,'api_calls':0,'tests_run':0,'outputs_or_scores_read':0},'seal_rule':'Holdout questions, oracle, author record and overlap audit must not be opened by implementation Lead until variant code/config/policy hashes frozen. Whole questions.json read exposes holdout; use dev-filtered adapter.'})
    m=json.loads((HERE/'manifest.json').read_text())
    print(json.dumps({k:m[k] for k in ('counts','questions_sha256','oracle_sha256')},indent=2))

if __name__=='__main__': main()

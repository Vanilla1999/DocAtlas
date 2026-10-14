"""One-use, exact-parent maintenance recipe; never retained in candidate history."""
from pathlib import Path
import ast, collections, hashlib, json, subprocess, sys, zipfile
import xml.etree.ElementTree as ET

BASE = 'c35aabe21397fb378d29eb26bb58d5ac6fceb622'
assert subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip() == BASE
R = Path.cwd()
def read(p): return (R/p).read_text()
def write(p,s): (R/p).write_text(s)
def replace(p,old,new):
    s=read(p)
    assert old in s, (p,old[:100])
    write(p,s.replace(old,new))
with zipfile.ZipFile(sys.argv[1]) as z:
    raw=z.read('core-tests-3.12.xml')
roster=[]
for c in ET.fromstring(raw).iter('testcase'):
    cls=c.attrib['classname']; parts=cls.split('.')
    paths=['/'.join(parts[:i])+'.py' for i in range(len(parts),0,-1)]
    p=next(p for p in paths if (R/p).exists())
    name=c.attrib['name']
    status=next((s for s in ['failure','error','skipped'] if c.find(s) is not None),'passed')
    roster.append(dict(path=p,name=name,nodeid=p+'::'+name,function=name.split('[')[0],status=status))
assert collections.Counter(x['status'] for x in roster)=={'passed':1435,'failure':102,'skipped':10}

p='eval/evidence_quality_v2/observer.py'
s=read(p).replace('    from docmancer.docs.application import docs_context_projection as projection\n','').replace('    app = getattr(service, "unified_context", service)\n','')
s=s.replace('    rank_fn = projection._facet_aware_candidates\n    fragments_fn = projection._qualified_fragments\n    expand_fn = projection._expand_selected_snippets\n','')
a=s.index('    def capture_rank(');b=s.index('    with (patch.object(',a);s=s[:a]+s[b:]
s=s.replace('          patch.object(service.project_docs, "query_project_docs", capture_query),\n          patch.object(projection, "_facet_aware_candidates", capture_rank),\n          patch.object(projection, "_qualified_fragments", capture_fragments),\n          patch.object(projection, "_expand_selected_snippets", capture_expand)):', '          patch.object(service.project_docs, "query_project_docs", capture_query)):')
s=s.replace('"unobserved_transitions": ["query_window: distinguish lifecycle, cap and budget only with additional evidence"]','''"retired_stages": ["rankings", "qualified_fragments", "expansions"],
              "finalization_observation": deepcopy((bounded.get("projection_observation") or {}).get(
                  "returned_core_diagnostics", {}).get("context_flow", {})),
              "unobserved_transitions": [
                  "Legacy semantic ranking/fragments/expansion are retired, not empty successful stages.",
                  "query_window: distinguish lifecycle, cap and budget only with additional evidence",
                  "finalization_observation is bounded; inspect omission/error counts before attribution",
              ]''')
write(p,s)
p='tests/evidence_quality_v2/test_measurement.py'
replace(p,'        assert actual==before','''        after=call_docs_tool_payload('get_docs_context',args,service)
        assert actual==before==after
        assert any('Deploy the release only after approval.' in row['snippet'] for row in actual['sources'])
        assert trace['observer_counts'] == {'retrieval_calls': 1, 'validation_calls': 1}
        assert trace['retired_stages'] == ['rankings', 'qualified_fragments', 'expansions']
        assert all(not trace['stages'][stage] for stage in trace['retired_stages'])
        flow=trace['finalization_observation']
        assert flow['observation'] == 'recorded'
        assert flow['event_count'] == flow['recorded_events'] + flow['omitted_events']
        assert flow['diagnostic_error_count'] == flow['serialization_omitted_events'] == 0
        assert not hasattr(service, '_same_call_diagnostics_observer')
        assert (project/'docs/deploy.md').read_bytes() == b'# Deployment\\n\\nDeploy the release only after approval.\\n' ''')

p='eval/project_context_quality_v2_protocol.py'
replace(p,'LOCK_PATH = CORPUS_DIR / "protocol.lock.json"','LOCK_PATH = CORPUS_DIR / "protocol.lock.json"\nCATALOG_PATH = CORPUS_DIR / "catalog.frozen.yaml"')
replace(p,'(ROOT / "docatlas.project-docs.yaml").read_text(encoding="utf-8")','CATALOG_PATH.read_text(encoding="utf-8")')
replace(p,'("catalog", ROOT / "docatlas.project-docs.yaml")','("catalog", CATALOG_PATH)')
replace(p,'    ) for row in negatives))','    ) for row in negatives), catalog_path=CATALOG_PATH)')
p='scripts/_project_docs_self_host_fixture.py'
replace(p,'def self_host_fixture(origin: Path):','def self_host_fixture(origin: Path, *, catalog_path: Path | None = None):')
replace(p,'                catalog = read_project_docs_catalog(root)','''                if catalog_path is not None:
                    # Inputs select a preregistered corpus; no question/gold data enters here.
                    selected = Path(catalog_path).absolute().relative_to(origin)
                    files = {row["path"]: row for row in provenance["files"]}
                    if selected.as_posix() not in files:
                        raise ValueError("frozen catalog must be a tracked member of the origin")
                    frozen = (root / selected).read_bytes()
                    if _digest(frozen) != files[selected.as_posix()]["original_sha256"]:
                        raise ValueError("frozen catalog bytes changed in mirror")
                    original = (root / CATALOG_FILENAME).read_bytes()
                    (root / CATALOG_FILENAME).write_bytes(frozen)
                    provenance["catalog_delta"] = {
                        "source_path": selected.as_posix(), "path": CATALOG_FILENAME,
                        "original_sha256": _digest(original), "frozen_sha256": _digest(frozen),
                        "scope": "isolated_mirror_only",
                    }
                    files[CATALOG_FILENAME]["mirror_sha256"] = _digest(frozen)
                    provenance["mirror_manifest_sha256"] = _json_digest(provenance["files"])
                catalog = read_project_docs_catalog(root)''')
replace(p,'"catalog_sha256": files[CATALOG_FILENAME]["original_sha256"],','"catalog_sha256": _digest((root / CATALOG_FILENAME).read_bytes()),')
p='scripts/run_project_docs_self_host_gate.py'
replace(p,'def _historical_paths() -> set[str]:','def _historical_paths(catalog_path: Path | None = None) -> set[str]:')
replace(p,'catalog = yaml.safe_load((REPO_ROOT / "docatlas.project-docs.yaml").read_text(encoding="utf-8")) or {}','catalog = yaml.safe_load((catalog_path or REPO_ROOT / "docatlas.project-docs.yaml").read_text(encoding="utf-8")) or {}')
replace(p,'    negative_cases: tuple[str | LiveCase, ...] = NEGATIVE_CASES,\n','    negative_cases: tuple[str | LiveCase, ...] = NEGATIVE_CASES,\n    catalog_path: Path | None = None,\n')
replace(p,'    historical_paths = _historical_paths()\n    with self_host_fixture(REPO_ROOT) as fixture:','    historical_paths = _historical_paths(catalog_path)\n    with self_host_fixture(REPO_ROOT, **({"catalog_path": catalog_path} if catalog_path is not None else {})) as fixture:')
p='tests/test_diagnostic_labels.py'
replace(p,'"tests/task_level/test_actionability.py::test_active_task33_protocol_has_public_actionability_contract",','"tests/test_public_surface_integration.py::test_public_cli_and_cold_stdio_contract_without_implicit_preparation",\n            "--collect-only",')
p='tests/test_project_docs_self_host_fixture.py'
write(p,read(p)+'''

def test_frozen_catalog_only_changes_isolated_prepared_membership(tmp_path):
    origin, documents = _checkout(tmp_path)
    catalog = yaml.safe_load(documents['docatlas.project-docs.yaml'])
    catalog['documents'] = [row for row in catalog['documents'] if row['path'] == 'docs/rules.md']
    frozen = yaml.safe_dump(catalog, sort_keys=False).encode()
    target = origin / 'eval/catalog.frozen.yaml'
    target.write_bytes(frozen)
    _git(origin, 'add', 'eval/catalog.frozen.yaml')
    _git(origin, 'commit', '-m', 'independent frozen catalog fixture')
    before_head = _git(origin, 'rev-parse', 'HEAD')
    with fixture_module.self_host_fixture(origin, catalog_path=target) as fixture:
        assert (fixture.root / 'docatlas.project-docs.yaml').read_bytes() == frozen
        assert fixture.mutation['catalog_sha256'] == hashlib.sha256(frozen).hexdigest()
        assert [row['path'] for row in fixture.mutation['documents']] == ['docs/rules.md']
        assert fixture.verify_cold_read(_cold_read(fixture))
        fixture.prepare()
        assert fixture.provenance['preparation']['indexed_paths'] == ['docs/rules.md']
        result = _cold_read(fixture)
        assert result['sources'] and {row['path_or_url'] for row in result['sources']} == {'docs/rules.md'}
        assert any('requires explicit preparation before a member write.' in row['snippet'] for row in result['sources'])
        assert all(row['snippet'] in RULES.decode() for row in result['sources'])
        assert result['answer_supported'] is False and result['edit_ready'] is False
        delta = fixture.provenance['catalog_delta']
        assert delta['scope'] == 'isolated_mirror_only'
        assert delta['frozen_sha256'] == hashlib.sha256(frozen).hexdigest()
    assert fixture.provenance['origin_unchanged_after_calls'] is True
    assert _git(origin, 'rev-parse', 'HEAD') == before_head
    assert {p: (origin / p).read_bytes() for p in documents} == documents
    assert target.read_bytes() == frozen
''')
whole={
 'tests/docs/test_visible_support_units.py':'removed private semantic delivery-unit implementation',
 'tests/docs/test_admission_pipeline_invariants.py':'private requalification with fabricated/cropped carriers, not public retrieval',
 'tests/test_dictionary_exit_read_packet_residuals.py':'synthetic selector/projector unit checks',
 'tests/test_dictionary_exit_selector_visibility.py':'synthetic selector unit checks',
 'tests/test_nl_dictionary_removal_packet_contract.py':'synthetic packet/validator unit checks',
 'tests/test_nl_dictionary_removal_consumer_contract.py':'synthetic candidate/SDK carrier unit checks',
}
partial={
 'tests/docs/test_contiguous_seed_envelope.py':['test_envelope_keeps_every_byte_in_the_gap_and_original_occurrences','test_single_seed_does_not_trigger_arbitrary_neighbor_expansion','test_envelope_must_not_erase_an_inherited_forbidden_gap'],
 'tests/docs/test_support_retention_integration.py':['test_same_origin_upgrade_survives_three_source_cap_after_required_lookups','test_projector_uses_prepared_snapshot_without_source_io'],
 'tests/test_retrieval_features.py':['test_hierarchical_two_stage_filters_to_top_docs','test_hierarchical_degraded_result_preserves_stage_failures','test_hierarchical_auto_enables_above_threshold'],
 'tests/test_sqlite_ranking_truth.py':['test_lexical_match_trace_distinguishes_strict_and_weak_or_fallback','test_and_candidates_do_not_suppress_a_more_useful_or_candidate','test_or_union_half_query_false_proof_is_rejected_downstream','test_or_fallback_requires_exact_terms_and_half_the_query'],
 'tests/evidence_quality_v2/test_measurement.py':['test_frozen_replay_uses_actual_prepared_projector_input'],
 'tests/test_action_packet_v4_delivery_consumers.py':['test_v4_failure_text_delivery_and_ambiguous_channel_rejection','test_newline_endpoint_convention_handles_trailing_newline_and_unknown_absolute_position'],
}
retired=[]
for p in set(whole)|set(partial):
    s=read(p);tree=ast.parse(s);edits=[]
    for n in tree.body:
        if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) or not n.name.startswith('test_'):continue
        if p not in whole and n.name not in partial[p]:continue
        rows=[r for r in roster if r['path']==p and r['function']==n.name]
        assert rows and not any(r['status']=='skipped' for r in rows),(p,n.name)
        reason=whole.get(p,'obsolete heuristic or private replay contract; no production-fix credit')
        for r in rows:retired.append({**r,'reason':reason})
        edits.append((min([n.lineno]+[d.lineno for d in n.decorator_list])-1,n.end_lineno))
    lines=s.splitlines(keepends=True)
    for a,b in sorted(edits,reverse=True):lines[a:b]=[]
    write(p,''.join(lines))
p='tests/docs/test_contiguous_seed_envelope.py';s=read(p)
n=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name=='_seed')
ls=s.splitlines(keepends=True);del ls[n.lineno-1:n.end_lineno];write(p,''.join(ls))
assert collections.Counter(r['status'] for r in retired)=={'failure':21,'passed':25}
removed_keys={r['path']+'::'+r['function'] for r in retired}
changed=set(subprocess.check_output(['git','diff','--name-only'],text=True).splitlines())
mods={p for p in changed if p.startswith('tests/') and p.endswith('.py')}
for p in R.glob('tests/diagnostic_labels*.json'):
    before=p.read_text();m=json.loads(before)
    m['node_overrides']={k:v for k,v in m['node_overrides'].items() if k.split('[')[0] not in removed_keys}
    for mod in set(m['module_node_hashes'])&mods:
        names=set()
        for n in ast.parse(read(mod)).body:
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_'):names.add(mod+'::'+n.name)
            if isinstance(n,ast.ClassDef) and n.name.startswith('Test'):
                for f in n.body:
                    if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)) and f.name.startswith('test_'):names.add(mod+'::'+n.name+'::'+f.name)
        if names:m['module_node_hashes'][mod]=hashlib.sha256('\n'.join(sorted(names)).encode()).hexdigest()
        else:m['module_labels'].pop(mod,None);m['module_node_hashes'].pop(mod,None)
    if json.loads(before)!=m:p.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
# No permission to reinterpret questions/answers or update the independent expected hash.
lock=json.loads(read('eval/project_context_quality_v2/protocol.lock.json'))
expected=lock['files']['catalog']
assert expected=='e06ca717d17a76a536d3918e6085424250651dedccfe3ce20bd0bc514b17b77f'
revs=subprocess.check_output(['git','rev-list',BASE,'--','docatlas.project-docs.yaml'],text=True).splitlines()
found=None
for rev in revs:
    result=subprocess.run(['git','show',rev+':docatlas.project-docs.yaml'],capture_output=True)
    if result.returncode==0 and hashlib.sha256(result.stdout).hexdigest()==expected:
        found=(rev,result.stdout);break
assert found, 'No historical catalog matches the independent lock; refuse hash rewriting'
(R/'eval/project_context_quality_v2/catalog.frozen.yaml').write_bytes(found[1])
frozen_receipt={'schema_version':1,'source_commit':found[0],'source_path':'docatlas.project-docs.yaml','catalog_sha256':expected,'protocol_lock_sha256':hashlib.sha256((R/'eval/project_context_quality_v2/protocol.lock.json').read_bytes()).hexdigest(),'restoration':'exact historical bytes; root catalog and all gold/acceptance inputs unchanged'}
write('v2plan/pr211-execution/STEP1_FROZEN_CATALOG_20261014.json',json.dumps(frozen_receipt,indent=2)+'\n')
p='.github/workflows/source-native-integration.yml'
replace(p,'            --junitxml="$RUNNER_TEMP/source-native-results/integration.xml"','            tests/evidence_quality_v2/test_measurement.py \\\n            tests/test_project_docs_self_host_fixture.py::test_frozen_catalog_only_changes_isolated_prepared_membership \\\n            --junitxml="$RUNNER_TEMP/source-native-results/integration.xml"')
manifest={'schema_version':1,'base_sha':BASE,'baseline_core_run':38544755488,'baseline_core_python':'3.12','baseline_core_counts':{'passed':1435,'failed':102,'skipped':10},'baseline_junit_sha256':hashlib.sha256(raw).hexdigest(),'retired':sorted(retired,key=lambda r:r['nodeid']),'retired_counts':dict(collections.Counter(r['status'] for r in retired)),'new_integration_scenarios':['tests/test_project_docs_self_host_fixture.py::test_frozen_catalog_only_changes_isolated_prepared_membership'],'scope':'Preparation only. Runtime selection/budgeting, sufficiency, models and gold expectations unchanged. Retired failures are not fixed product defects.'}
write('v2plan/pr211-execution/STEP1_TEST_MIGRATION_20261014.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
write('v2plan/pr211-execution/STEP1_PREPARATION_20261014_RU.md','''# PR211: подготовка измерений до исправления выбора контекста

Исходный head: `c35aabe21397fb378d29eb26bb58d5ac6fceb622`.
Изменения ограничены тестами, evaluator и его изолированными fixtures.
Runtime selection/budget/sufficiency/model code и main не изменяются.

Удалены31 test-function /46 core-cases:21 FAIL и25 PASS. Это retirement
отменённых/private/synthetic проверок, не21 исправление продукта. Список,
основания и hash базового JUnit: STEP1_TEST_MIGRATION_20261014.json.
Общие helpers для оставшихся consumers и все исходные SKIP сохранены.

Observer использует текущие acquisition/query/projector границы и существующую
ограниченную finalization-трассу. Старые ranking/fragments/expansion помечены
retired, а не успешно пройденными пустыми стадиями. Старый private replay
удалён; существующий prepare/MCP/SQLite сценарий проверяет off/on/off, факт,
один retrieval/validation и восстановление observer. Один новый интеграционный
сценарий проверяет frozen-каталог через Git mirror, cold consent, реальную
SQLite подготовку, публичную выдачу и неизменность origin.

V2 получает отдельный catalog.frozen.yaml: точные исторические байты с прежним
hash независимого lock. Root catalog, вопросы, gold, locks и floors не меняются.
Замена применяется только к изолированному mirror, записывается в provenance
и проверяется перед реальной подготовкой. Исходная версия и hashes приведены
в STEP1_FROZEN_CATALOG_20261014.json.

Subprocess-проверка pytest-selector указывает на существующий публичный
сценарий и проверяет collection, не повторяя его продуктовый runtime.
Ожидаемый core roster1547-46+1=1502; требуется собственная CI collection.
Общая историческая цель−40% имеет baseline8291: повторная−40% от остатка не
требуется. Весь остаточный набор не объявляется построчно переклассифицированным
по этому ограниченному manifest. Новых unit-тестов нет.

V40/P03/E01/negative-case критерии не меняются. Завершённый25-case отчёт V2
означает работоспособное измерение, а не прохождение quality floors.
Результаты конкретного candidate SHA сохраняются отдельно в Actions.
''')
for p in subprocess.check_output(['git','diff','--name-only'],text=True).splitlines():
    q=R/p
    if q.suffix=='.py':q.write_text('\n'.join(line.rstrip() for line in q.read_text().rstrip().splitlines())+'\n')
for p in R.rglob('*.py'):
    if '.git' not in p.parts:ast.parse(p.read_bytes(),filename=str(p))
protected=['docmancer','docatlas.project-docs.yaml','eval/project_context_quality_v2/cases.json','eval/project_context_quality_v2/protocol.lock.json','eval/project_context_quality_v2/migration-crosswalk.json','eval/project_context_quality_v2/diagnostic.json','eval/heuristic_removal']
subprocess.run(['git','diff','--exit-code','--',*protected],check=True)
print('Prepared source-native measurement migration:',manifest['retired_counts'],'frozen catalog from',found[0])

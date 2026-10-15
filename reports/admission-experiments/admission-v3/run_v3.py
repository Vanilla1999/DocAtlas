"""Coordinator-only real public MCP/SQLite V3 driver; never import private oracle."""
from contextlib import ExitStack
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
REPO = Path('/tmp/opencode/docatlas-compact-review')
V2 = ROOT.parent / 'admission-selection-v2'
OLD = ROOT.parent / 'admission-full-20261012'
sys.path.insert(0, str(REPO))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


v2 = None
host = None
ORIGINAL_ENV = dict(os.environ)
ledger = {'prepares': 0, 'context_attempts': 0, 'host_requests': 0, 'model_forwards': 0, 'errors': []}
START = None


def save(name, value):
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')


def budget():
    if time.monotonic() - START > 7200:
        raise RuntimeError('Runtime ceiling')
    if sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()) > 4 * 1024**3:
        raise RuntimeError('Artifact ceiling')
    save('LEDGER.json', ledger)


def extra_integrity(payload, snapshot, documents):
    errors, ids = [], set()
    for item in payload.get('sources') or []:
        sid = item.get('evidence_id')
        if not sid or sid in ids:
            errors.append('duplicate_or_missing_evidence_id')
        ids.add(sid)
        original = (snapshot.get(sid) or {}).get('source') or {}
        material = {'path': original.get('path') or original.get('source') or original.get('url') or original.get('source_url'),
                    'section': original.get('heading_path') or original.get('title'),
                    'content': original.get('content') or original.get('display_text'),
                    'snippet': original.get('snippet') or original.get('code'),
                    'version': original.get('version_binding') or original.get('version') or original.get('requested_version')}
        if item.get('content_sha256') != v2.digest(material) or item.get('authority') != 'source_of_truth':
            errors.append('public_envelope_hash_or_source_authority')
        ref = original.get('_reference_evidence') or {}
        text = documents.get(item.get('path_or_url'), '')
        a, b = ref.get('char_start'), ref.get('char_end')
        snippet = item.get('snippet') or ''
        if type(a) is not int or type(b) is not int or not snippet:
            errors.append('missing_snippet_coordinate_operand')
            continue
        positions, cursor = [], a
        while (pos := text.find(snippet, cursor, b)) >= 0:
            end = pos + len(snippet)
            positions.append([text.count('\n', 0, pos) + 1,
                              text.count('\n', 0, end) + (0 if snippet.endswith('\n') else 1)])
            cursor = pos + 1
        if [item.get('line_start'), item.get('line_end')] not in positions:
            errors.append('declared_snippet_lines')
    return errors


def public(case, arm, fixture, admission):
    budget()
    service, project, documents, generation, env = fixture
    env = dict(env)
    for key in ('DOCATLAS_EXPERIMENT_ADMISSION', 'DOCATLAS_EXPERIMENT_QUERY_CONDITION'):
        env.pop(key, None)
    env.update(admission)
    before = v2.state(service, project)
    result = {'case_id': case['id'], 'question': case['question'], 'split': case['split'], 'arm': arm,
              'request': {'question': case['question'], 'project_path': str(project), 'scope': 'project'},
              'status': 'STARTED', 'state_before': before, 'admission_environment': admission}
    rows = []
    def observe(question, pool, excluded, original):
        pool_rows = [v2.window(c) for c in pool]
        for row in pool_rows:
            ref = row['metadata'].get('_reference_evidence') or {}
            a, b = row['span']
            text = documents.get(row['path'])
            scope = row['binding'].get('scope') or {}
            if (text is None or ref.get('raw_document') != text or ref.get('text') != row['text']
                    or type(a) is not int or type(b) is not int or not 0 <= a < b <= len(text)
                    or text[a:b] != row['text'] or row['binding'].get('content_sha256') != sha256(text.encode()).hexdigest()
                    or scope.get('snapshot_id') != generation or scope.get('version') != ''
                    or scope.get('project_id') != 'local:' + sha256(str(project).encode()).hexdigest()):
                raise RuntimeError('SOURCE_POLICY_DEFECT: pool binding/allowlist')
        rows.append({'question': question, 'pool': pool_rows,
                     'complete_candidates': [v2.window(c) for c in original],
                     'excluded': [{'candidate': v2.window(c), 'reason': reason, 'original_ordinal': i}
                                  for c, reason, i in excluded], 'selected_indices': None})
        return None
    ledger['context_attempts'] += 1
    if ledger['context_attempts'] > 80:
        raise RuntimeError('Context ceiling')
    save('public/' + case['id'] + '_' + arm + '.json', result)
    save('LEDGER.json', ledger)
    start = time.monotonic()
    try:
        with patch.dict(os.environ, env, clear=True), v2.experimental_candidate_selector(observe):
            payload, snapshot = v2._call_with_snapshot(result['request'], service)
        result.update(payload=payload, validation_snapshot=snapshot, pools=rows, status='EXECUTED',
                      state_after=v2.state(service, project), elapsed_seconds=time.monotonic() - start)
        result['integrity_errors'] = v2.integrity(payload, snapshot, documents, project, generation)
        result['integrity_errors'] += extra_integrity(payload, snapshot, documents)
        if any(payload.get(key) is not False for key in ('answer_supported', 'answer_available', 'edit_ready')):
            result['integrity_errors'].append('unexpected_or_missing_authority_flags')
        if before != result['state_after']:
            result['integrity_errors'].append('read_state_changed')
        if result['integrity_errors']:
            raise RuntimeError('SOURCE_POLICY_DEFECT: ' + repr(result['integrity_errors']))
    except Exception as exc:
        result.update(status='BLOCKED', error=repr(exc), elapsed_seconds=time.monotonic() - start)
        ledger['errors'].append({'case_id': case['id'], 'arm': arm, 'error': repr(exc)})
        raise
    finally:
        save('public/' + case['id'] + '_' + arm + '.json', result)
        save('LEDGER.json', ledger)
    return result


def generate(case, arm, result, system_prompt, model_input):
    budget()
    if ledger['host_requests'] >= 40:
        raise RuntimeError('Host ceiling')
    ledger['host_requests'] += 1
    save('LEDGER.json', ledger)
    messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': v2.canonical(model_input)}]
    with patch.dict(os.environ, ORIGINAL_ENV, clear=True):
        receipt = host.invoke(ROOT / 'host' / (case['id'] + '_' + arm), messages,
                              {'case_id': case['id'], 'arm': arm, 'public_result_sha256': v2.digest(result),
                               'system_prompt_sha256': sha256(system_prompt.encode()).hexdigest()}, 180)
    if receipt['execution'] != 'EXECUTED':
        raise RuntimeError('Host unavailable/completion UNKNOWN; no retry or substitute')
    return receipt


def sources(result):
    return [{'source_id': s['evidence_id'], 'text': s['snippet'],
             'provenance': {k: s[k] for k in ('path_or_url', 'scope', 'version_binding', 'line_start',
                                              'line_end', 'project_identity', 'authority') if k in s}}
            for s in (result['payload'].get('sources') or [])]


def main():
    global START, v2, host
    if (ROOT / 'RUN_RECEIPT.json').exists():
        raise RuntimeError('Consumed run cannot be repeated')
    config = json.loads((ROOT / 'EXECUTION_CONFIG.json').read_text())
    if not config['frozen_files']:
        raise RuntimeError('Empty execution freeze')
    # Contract/input/code hashes frozen by coordinator; oracle not imported.
    for path, expected in config['frozen_files'].items():
        if sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Frozen file changed: ' + path)
    START = time.monotonic()
    save('RUN_RECEIPT.json', {'status': 'STARTED', 'config': config, 'timestamp_unix': time.time()})
    v2 = load('v2_reused_runtime', V2 / 'run_public.py')
    host = load('existing_host', OLD / 'B_host_runner.py')
    corpus = json.loads(Path(config['corpus_file']).read_text())
    cases = json.loads(Path(config['cases_file']).read_text())
    corpus = corpus.get('documents', corpus) if isinstance(corpus, dict) else corpus
    cases = cases.get('cases', cases) if isinstance(cases, dict) else cases
    groups = {}
    for doc in corpus:
        group = doc.get('document_group', doc.get('project'))
        groups.setdefault(group, {})[doc['path']] = doc.get('content', doc.get('text'))
    for group, documents in config.get('additional_documents', {}).items():
        groups[group] = documents
    cases += config.get('additional_cases', [])
    fixtures = {}
    captures = {}
    with ExitStack() as stack:
        for group, documents in groups.items():
            budget()
            root = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='docatlas-v3-', dir='/tmp')))
            project = root / 'project'
            v2.write_project(project, documents)
            service, cfg = stack.enter_context(v2.isolated_service(root / 'state'))
            ledger['prepares'] += 1
            if ledger['prepares'] > 8:
                raise RuntimeError('Prepare ceiling')
            save('LEDGER.json', ledger)
            save('prepares/' + group + '.json', {'status': 'STARTED', 'project': str(project)})
            prepared = v2.index_project(service, cfg, project)
            prepared['status'] = 'EXECUTED'
            save('prepares/' + group + '.json', prepared)
            expected_paths = sorted(documents)
            actual_hashes = {row['path']: row['content_sha256'] for row in prepared['documents']}
            if (prepared['expected_paths'] != expected_paths or prepared['indexed_paths'] != expected_paths
                    or prepared['excluded_or_failed_paths'] or prepared['unexpected_paths']
                    or actual_hashes != {p: sha256(t.encode()).hexdigest() for p, t in documents.items()}
                    or prepared['catalog_sha256'] != sha256((project / 'docatlas.project-docs.yaml').read_bytes()).hexdigest()):
                raise RuntimeError('SOURCE_POLICY_DEFECT: partial/mismatched preparation')
            fixtures[group] = (service, project, documents, prepared['generation_id'], dict(os.environ))
            save('bindings/' + group + '.json', {'project': str(project), 'generation': prepared['generation_id'],
                 'source_scope': 'project', 'source_version': 'unversioned',
                 'document_hashes': {p: sha256(t.encode()).hexdigest() for p, t in documents.items()}})
        # Sequential admission comparison first, unchanged ranking/presentation.
        for case in cases:
            group = case.get('document_group', case.get('project'))
            for arm, env in config['admission_arms'].items():
                captures[(case['id'], arm)] = public(case, arm, fixtures[group], env)
        save('PUBLIC_COMPLETION.json', {'ledger': ledger, 'runtime_seconds': time.monotonic() - START})
        for case in cases:
            if case['id'] not in config['host_case_ids']:
                continue
            for arm in config.get('per_case_host_arms', {}).get(case['id'], config['host_admission_arms']):
                result = captures[(case['id'], arm)]
                generate(case, arm, result, (OLD / 'HOST_PROMPT_RU.txt').read_text(),
                         {'question': case['question'], 'sources': sources(result)})
        if config.get('citation_case_ids'):
            adapter = load('citation_adapter', ROOT / 'citation_adaptation.py')
            for case in cases:
                if case['id'] in config['citation_case_ids']:
                    parent_arm = config.get('citation_parent_by_case', {}).get(case['id'], config['citation_parent_arm'])
                    result = captures[(case['id'], parent_arm)]
                    group = case.get('document_group', case.get('project'))
                    binding = json.loads((ROOT / 'bindings' / (group + '.json')).read_text())
                    assembly_start = time.monotonic()
                    packet = adapter.prepare_packet(result, binding)
                    assembly_seconds = time.monotonic() - assembly_start
                    save('citation/' + case['id'] + '_packet.json', packet)
                    generate(case, 'Citation', result, adapter.GENERATOR_PROMPT_RU,
                             packet['model_input'])
                    answer = (ROOT / 'host' / (case['id'] + '_Citation') / 'answer.raw.txt').read_bytes()
                    reconstruction_start = time.monotonic()
                    extraction = adapter.extract_quotes(answer, packet)
                    reconstruction_seconds = time.monotonic() - reconstruction_start
                    save('citation/' + case['id'] + '_extracted.json', extraction)
                    adapter.save_artifacts(ROOT / 'citation' / case['id'], answer, extraction)
                    save('citation/' + case['id'] + '_cost.json', {'assembly_seconds': assembly_seconds,
                         'reconstruction_seconds': reconstruction_seconds, 'parent_arm': parent_arm,
                         'public_result_sha256': v2.digest(result), 'same_source_content_as_base_host': True})
    save('COMPLETION.json', {'status': 'COMPLETED', 'ledger': ledger, 'runtime_seconds': time.monotonic() - START})


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        save('BLOCKER.json', {'error': repr(exc), 'ledger': ledger,
                             'runtime_seconds': time.monotonic() - START if START else None})
        raise

"""FRESH17 real run_unit adapter. No oracle access; sequential checked-store reuse only."""
from pathlib import Path
import argparse
import asyncio
import fcntl
import gzip
import hashlib
import importlib.util
import json
import shutil
import sys

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parents[1]
ROOT = HERE.parents[3]
FLOOR = 1024 ** 3
CATALOG = 'docatlas.project-docs.yaml'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inventory(root):
    require(root.is_dir() and not root.is_symlink(), 'missing/linked snapshot root')
    result = {}
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(), 'symlinks forbidden in checked snapshot')
        if path.is_file():
            result[path.relative_to(root).as_posix()] = digest(path)
        else:
            require(path.is_dir(), 'special files forbidden in checked snapshot')
    return result


def verify_project(project, manifest):
    expected = {item['path']: item['sha256'] for item in manifest['documents']}
    expected[CATALOG] = manifest['catalog_sha256']
    require(inventory(project) == expected, 'project membership/bytes differ from frozen inventory')
    # Semantic confirmation on top of the byte seal: the frozen catalog itself
    # must declare exactly English for every frozen document.
    import json as _json
    catalog = _json.loads((project / CATALOG).read_text(encoding='utf-8'))
    require(catalog.get('schema_version') == 1, 'unexpected frozen catalog schema')
    languages = catalog.get('documentation_languages')
    require(isinstance(languages, dict) and set(languages) == set(expected) - {CATALOG},
            'frozen catalog language coverage differs from frozen documents')
    require(all(value == ['en'] for value in languages.values()),
            'frozen catalog must declare exactly English for every frozen document')


def disk_guard(path):
    while not path.exists():
        path = path.parent
    require(shutil.disk_usage(path).free >= FLOOR, 'less than 1 GiB free; run refused')


def compact(out):
    """Verified exact-file cleanup only; never recursively remove any directory."""
    registry = []
    for folder in ('payloads', 'logs'):
        for path in sorted((out / folder).rglob('*')):
            if not path.is_file() or path.suffix == '.gz':
                continue
            require(not path.is_symlink() and path.resolve().is_relative_to(out), 'unsafe artifact path')
            expected, size = digest(path), path.stat().st_size
            target = path.with_name(path.name + '.gz')
            require(not target.exists(), 'archive already exists')
            with path.open('rb') as source, target.open('xb') as raw:
                with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as archive:
                    shutil.copyfileobj(source, archive, 1024 * 1024)
            h, count = hashlib.sha256(), 0
            with gzip.open(target, 'rb') as archive:
                for block in iter(lambda: archive.read(1024 * 1024), b''):
                    h.update(block); count += len(block)
            require(h.hexdigest() == expected and count == size, 'archive verification failed')
            registry.append({'path': str(path.relative_to(out)), 'archive': str(target.relative_to(out)),
                             'sha256': expected, 'bytes': size, 'archive_sha256': digest(target)})
            (out / 'compression.json').write_text(json.dumps(registry, separators=(',', ':')) + '\n')
            require(path.resolve().is_relative_to(out) and digest(path) == expected, 'artifact changed before cleanup')
            path.unlink()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--split', choices=['dev', 'holdout'], required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--reuse-work', action='store_true')
    p.add_argument('--source-tree', type=Path, default=ROOT)
    p.add_argument('--env-json', type=Path, required=True)
    p.add_argument('--variants-frozen', type=Path)
    a = p.parse_args()
    m = json.loads((HERE / 'manifest.json').read_text())
    require(digest(HERE / 'questions.json') == m['questions_sha256'], 'question hash mismatch')
    verify_project(HERE / 'corpus/project', m)
    if a.split == 'holdout' and (a.variants_frozen is None or not a.variants_frozen.is_file()):
        p.error('holdout requires pre-existing variant freeze receipt')
    if a.variants_frozen is not None:
        require(a.variants_frozen.read_bytes().strip(), 'empty freeze receipt')
    cases = [c for c in json.loads((HERE / 'questions.json').read_text())['cases'] if c['split'] == a.split]
    require(cases, 'empty selected split')
    extra = json.loads(a.env_json.read_text())
    require(isinstance(extra, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in extra.items()),
            'env-json must map names to strings')
    # Explicitly reject unknown knobs: no arbitrary transport, path, source or observer injection.
    allowed = {
        'DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH', 'DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT',
        'DOCATLAS_CONTEXT_COMPRESSION', 'DOCATLAS_MCP_TEXT_FALLBACK', 'DOCATLAS_MCP_COMPACT_TEXT',
        'DOCATLAS_EXPERIMENT_QWEN_STUDY', 'DOCATLAS_EXPERIMENT_PAIRED_QWEN',
        'DOCATLAS_EXPERIMENT_DELIVERY_MAX_TOKENS', 'DOCATLAS_EXPERIMENT_QWEN_SELECTION_MODE',
        'DOCATLAS_EXPERIMENT_QWEN_STUDY_PRUNING', 'DOCATLAS_EXPERIMENT_QWEN_STUDY_UNITS',
        'DOCATLAS_EXPERIMENT_QWEN_STUDY_UNIT_GUARD',
    }
    require(not (set(extra) - allowed), 'unreviewed environment key; freeze/review allowlist first')
    enums = {
        'DOCATLAS_EXPERIMENT_QWEN_SELECTION_MODE': {'control', 'no_stop', 'no_redundancy', 'relative'},
        'DOCATLAS_EXPERIMENT_QWEN_STUDY_PRUNING': {'control', 'off', 'body_union'},
        'DOCATLAS_EXPERIMENT_QWEN_STUDY_UNITS': {'control', 'competing_rows'},
        'DOCATLAS_EXPERIMENT_QWEN_STUDY_UNIT_GUARD': {'off', 'conservative'},
        'DOCATLAS_EXPERIMENT_QWEN_STUDY': {'0', '1'},
        'DOCATLAS_EXPERIMENT_PAIRED_QWEN': {'0', '1'},
    }
    for key, values in enums.items():
        require(key not in extra or extra[key] in values, 'unknown variant setting: ' + key)
    budget = extra.get('DOCATLAS_EXPERIMENT_DELIVERY_MAX_TOKENS')
    require(budget is None or (budget.isdecimal() and int(budget) > 0), 'invalid delivery budget')
    a.out = a.out.resolve(); a.work = a.work.resolve(); a.source_tree = a.source_tree.resolve()
    require(not a.out.exists(), 'out must be a new path')
    require(not a.out.is_relative_to(a.work) and not a.work.is_relative_to(a.out), 'out/work must be disjoint')
    require(not a.work.is_relative_to(HERE) and not HERE.is_relative_to(a.work), 'work must not contain frozen inputs')
    disk_guard(a.out); disk_guard(a.work)
    if not a.reuse_work:
        require(not a.work.exists(), 'cold work must be new; use --reuse-work for prepared work')
        a.work.mkdir(parents=True)
    require(a.work.is_dir(), 'reuse work missing')
    # Stable advisory lock spans validation, server lifetime and snapshot recording.
    with (a.work / '.fresh-run.lock').open('a+b') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            p.error('shared work is in use; concurrent variants forbidden')
        root = a.work / ('FRESH17-' + a.split)
        seal = a.work / ('snapshot-' + a.split + '.json')
        if a.reuse_work:
            require(seal.is_file(), 'no successful first-prepare snapshot receipt')
            baseline = json.loads(seal.read_text())
            require(baseline['manifest_sha256'] == digest(HERE / 'manifest.json'), 'snapshot manifest mismatch')
            require(baseline['work'] == str(a.work), 'snapshot moved: source identity would change')
            verify_project(a.work / 'corpora/FRESH17/project', m)
            verify_project(root / 'project', m)
            require(inventory(root) == baseline['files'], 'prepared store/settings snapshot changed')
        else:
            shutil.copytree(HERE / 'corpus/project', a.work / 'corpora/FRESH17/project')
            baseline = None
        a.out.mkdir(parents=True); (a.out / 'logs').mkdir()
        # Generated-only artifact destinations, never caller-controlled corpus/gold paths.
        extra['DOCATLAS_EXPERIMENT_PAIRED_CACHE'] = str(a.work / 'paired-cache')
        extra['DOCATLAS_EXPERIMENT_PAIRED_TRACE'] = str(a.out / 'logs/paired.jsonl.gz')
        sys.path.insert(0, str(HARNESS)); sys.path.insert(0, str(a.source_tree))
        spec = importlib.util.spec_from_file_location('fresh_public_runner', HARNESS / 'run.py')
        runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
        unit = {'name': 'FRESH17-' + a.split, 'corpus': 'FRESH17', 'scan_deadline': None, 'cases': cases}
        receipt = {'schema_version': 2, 'corpus': 'FRESH17', 'split': a.split,
                   'manifest_sha256': digest(HERE / 'manifest.json'), 'questions_sha256': m['questions_sha256'],
                   'environment_sha256': digest(a.env_json), 'environment': extra,
                   'variant_freeze_sha256': digest(a.variants_frozen) if a.variants_frozen else None,
                   'run_unit_sha256': digest(HARNESS / 'run.py'), 'adapter_sha256': digest(Path(__file__)),
                   'source_tree': str(a.source_tree), 'work': str(a.work), 'reuse_work': a.reuse_work,
                   'expected_case_ids': [c['id'] for c in cases], 'observer': False, 'portions': 1,
                   'status': 'incomplete', 'units': []}
        try:
            result = asyncio.run(runner.run_unit(unit, a.out, a.work, a.source_tree, False, extra,
                                                reuse=a.reuse_work, portions=1))
            receipt['units'] = [result]
            verify_project(root / 'project', m)
            files = inventory(root)
            if baseline is not None:
                require(files == baseline['files'], 'run changed prepared snapshot; comparison invalid')
            else:
                baseline = {'schema_version': 1, 'manifest_sha256': receipt['manifest_sha256'],
                            'work': str(a.work), 'files': files}
                seal.write_text(json.dumps(baseline, sort_keys=True, separators=(',', ':')) + '\n')
            receipt['snapshot_sha256'] = digest(seal)
            receipt['status'] = 'complete'
        finally:
            # Failed calls remain execution failures, with saved partial journals, never semantic negatives.
            (a.out / 'run.json').write_text(json.dumps(receipt, ensure_ascii=False, separators=(',', ':')) + '\n')
            compact(a.out)


if __name__ == '__main__':
    main()

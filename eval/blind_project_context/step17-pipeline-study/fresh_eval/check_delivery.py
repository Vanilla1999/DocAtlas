"""Offline frozen witness coverage only. Opens oracle ONLY when explicitly run after freeze."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def covered(intervals, begin, end):
    reach = begin
    for a, b in sorted(intervals):
        if a > reach:
            break
        reach = max(reach, b)
        if reach >= end:
            return True
    return False


def payload_bytes(root, relative):
    path = (root / relative).resolve()
    require(path.is_relative_to(root), 'payload outside run')
    if path.is_file():
        return path.read_bytes()
    archive = path.with_name(path.name + '.gz')
    require(archive.resolve().is_relative_to(root), 'archive outside run')
    with gzip.open(archive, 'rb') as stream:
        return stream.read()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('run', type=Path)
    p.add_argument('--variants-frozen', type=Path, required=True)
    a = p.parse_args()
    require(a.variants_frozen.read_bytes().strip(), 'empty freeze receipt')
    a.run = a.run.resolve()
    m = json.loads((HERE / 'manifest.json').read_text())
    require(sha(HERE / 'questions.json') == m['questions_sha256'], 'question hash mismatch')
    require(sha(HERE / 'oracle.json') == m['oracle_sha256'], 'oracle hash mismatch')
    docs = {}
    for item in m['documents']:
        path = HERE / item['frozen_path']
        require(sha(path) == item['sha256'], 'frozen source hash mismatch')
        docs[item['path']] = path.read_bytes().decode('utf-8')
    gold = {t['topic_id']: t for t in json.loads((HERE / 'oracle.json').read_text())['topics']}
    questions = {c['id']: c for c in json.loads((HERE / 'questions.json').read_text())['cases']}
    # Production codecs ONLY decode transport; witness placement below is independent.
    sys.path.insert(0, str(ROOT))
    from docmancer.docs.application.context_assembly import decode_context
    from docmancer.docs.application.section_compression import expand_sections
    import tiktoken
    encoding = tiktoken.get_encoding('o200k_base')  # unavailable encoding => fail, no estimate substitution
    run = json.loads((a.run / 'run.json').read_text())
    require(run['manifest_sha256'] == sha(HERE / 'manifest.json'), 'run manifest mismatch')
    require(run['questions_sha256'] == m['questions_sha256'], 'run questions mismatch')
    require(run['split'] in ('dev', 'holdout'), 'unknown split')
    require(run.get('variant_freeze_sha256') == sha(a.variants_frozen), 'run/freeze receipt mismatch')
    expected = {k for k, v in questions.items() if v['split'] == run['split']}
    require(set(run['expected_case_ids']) == expected and len(run['expected_case_ids']) == len(expected),
            'selected cases mismatch')
    require(run.get('observer') is False and run.get('portions') == 1, 'wrong execution endpoint')
    records = [r for u in run['units'] for r in u['records']]
    by_id = {}
    for record in records:
        require(record.get('case_id') in expected, 'unexpected case record')
        by_id.setdefault(record['case_id'], []).append(record)
    results = []
    for cid in sorted(expected):
        errors, spans = [], {}
        metrics = {'utf8_bytes': None, 'o200k_tokens': None, 'charged_tokens': None}
        matches = by_id.get(cid, [])
        if len(matches) != 1:
            errors.append('missing_record' if not matches else 'duplicate_records')
        else:
            record = matches[0]
            try:
                raw = payload_bytes(a.run, record['payload'])
                require(hashlib.sha256(raw).hexdigest() == record['payload_sha256'], 'payload hash mismatch')
                text = raw.decode('utf-8')
                tokens = len(encoding.encode(text, disallowed_special=()))
                metrics = {'utf8_bytes': len(raw), 'o200k_tokens': tokens,
                           'charged_tokens': max(tokens, (len(raw) + 3) // 4)}
                require(record.get('utf8_bytes') == len(raw), 'payload byte count mismatch')
                require(type(record.get('is_error')) is bool, 'missing error flag')
                if record['is_error']:
                    errors.append('mcp_is_error')
                require(not record.get('portions'), 'unexpected continuation: endpoint is one portion')
                payload = json.loads(text)
                require(isinstance(payload, dict), 'payload not object')
                if not payload.get('sources'):
                    rows = []
                elif payload.get('context_format'):
                    decoded = decode_context(payload).get('sources', [])
                    rows = [(r['path'], r['line_start'], r['line_end'], r['text']) for r in decoded]
                else:
                    decoded = expand_sections(payload).get('sources', [])
                    rows = [(r.get('path_or_url'), r.get('line_start'), r.get('line_end'),
                             r.get('snippet') or r.get('text') or '') for r in decoded]
                for path, start, end, row_text in rows:
                    if path not in docs or type(start) is not int or type(end) is not int or not isinstance(row_text, str):
                        errors.append('invalid_source_or_span'); continue
                    lines = docs[path].splitlines(keepends=True)
                    if not row_text or not 1 <= start <= end <= len(lines):
                        errors.append('invalid_source_or_span'); continue
                    region = ''.join(lines[start-1:end]); offset = sum(map(len, lines[:start-1]))
                    first = region.find(row_text)
                    if first < 0 or region.find(row_text, first+1) >= 0:
                        errors.append('missing_or_ambiguous_literal_row'); continue
                    spans.setdefault(path, []).append((offset+first, offset+first+len(row_text)))
            except (OSError, ValueError, TypeError, KeyError, IndexError, EOFError):
                errors.append('invalid_or_missing_payload')
                spans = {}
        if run.get('status') != 'complete':
            errors.append('incomplete_run')
        facts = []
        for f in gold[questions[cid]['topic_id']]['facts']:
            require(hashlib.sha256(docs[f['path']].encode()).hexdigest() == f['source_sha256'], 'witness source mismatch')
            require(docs[f['path']][f['char_start']:f['char_end']] == f['quote'], 'witness span mismatch')
            facts.append({'fact_id': f['fact_id'], 'delivered': covered(spans.get(f['path'], []), f['char_start'], f['char_end'])})
        require(facts, 'empty obligation groups')
        results.append({'case_id': cid, 'topic_id': questions[cid]['topic_id'],
                        'language': 'ru' if questions[cid].get('search_question') else 'en', 'facts': facts,
                        'required_groups': len(facts), 'delivered_groups': sum(f['delivered'] for f in facts),
                        'anomalies': sorted(set(errors)), **metrics,
                        'all_witnesses_delivered': all(f['delivered'] for f in facts) and not errors})
    families = {}
    for result in results:
        families.setdefault(result['topic_id'], []).append(result['all_witnesses_delivered'])
    print(json.dumps({'schema_version': 2, 'metric': 'literal_witness_delivery_only',
                      'semantic_answer_correctness': 'NOT_MEASURED',
                      'checker_sha256': sha(Path(__file__)), 'manifest_sha256': sha(HERE / 'manifest.json'),
                      'questions_sha256': m['questions_sha256'], 'oracle_sha256': m['oracle_sha256'],
                      'run_sha256': sha(a.run / 'run.json'), 'split': run['split'],
                      'expected_cases': len(expected), 'present_cases': len(by_id),
                      'passed_cases': sum(r['all_witnesses_delivered'] for r in results),
                      'required_groups': sum(r['required_groups'] for r in results),
                      'delivered_groups': sum(r['delivered_groups'] for r in results),
                      'languages': {lang: {'cases': sum(r['language'] == lang for r in results),
                                           'passed': sum(r['language'] == lang and r['all_witnesses_delivered'] for r in results)}
                                    for lang in ('ru', 'en')},
                      'families': {key: {'cases': len(values), 'all_witnesses_delivered': all(values)}
                                   for key, values in families.items()},
                      'source_hash_boundary': 'Exact frozen bytes and literal spans; not all server provenance metadata.',
                      'cases': results}, ensure_ascii=False, separators=(',', ':')))


if __name__ == '__main__':
    main()

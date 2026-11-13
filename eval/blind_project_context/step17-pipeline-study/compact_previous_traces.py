#!/usr/bin/env python3
"""One-shot, explicit step16 trace compaction; preserve and verify ALL bytes.

Never walks/deletes arbitrary directories. Only eight named completed-campaign
traces are eligible. Exact MCP payloads, score caches, models and stores untouched.
"""
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT = Path('/home/viadmin/.local/share/docatlas-eval/step16/paired-campaign')
NAMES = tuple(f'{arm}-{budget}' for budget in (12000, 6000, 3000, 1500) for arm in ('A', 'B'))
LEDGER = ROOT / 'COMPACTION_RECEIPT.json'
OMIT = frozenset(('raw_rows', 'raw_snapshots', 'normalized_rows', 'normalized_snapshots'))
CHUNK = 4 * 1024 * 1024


def utc():
    return datetime.now(timezone.utc).isoformat()


def signature(path):
    s = path.stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns


def save(receipt):
    with LEDGER.open('w', encoding='utf-8') as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())


def main():
    assert ROOT.resolve(strict=True) == ROOT and not ROOT.is_symlink()
    assert not LEDGER.exists(), 'one-shot ledger already exists; inspect before resuming'
    # Complete preflight and exact resolved-target verification BEFORE any delete.
    for name in NAMES:
        p = ROOT / (name + '.jsonl')
        assert p.is_file() and not p.is_symlink() and p.resolve(strict=True) == p
        assert p.parent == ROOT
        assert not Path(str(p) + '.gz').exists()
        assert not (ROOT / (name + '.index.jsonl.gz')).exists()
        run = json.loads((ROOT / name / 'run.json').read_text())
        assert len(run['records']) == 96
        print('CONFIRMED_TARGET', p, p.stat().st_size, flush=True)
    receipt = {'schema': 'verified-lossless-trace-compaction-v1', 'started_utc': utc(),
               'root': str(ROOT), 'status': 'running', 'files': [],
               'free_bytes_before': shutil.disk_usage(ROOT).free,
               'preserved': 'all decompressed trace bytes; exact MCP payloads, run/score reports, caches and stores untouched',
               'index_omitted_fields': sorted(OMIT)}
    save(receipt)
    for name in NAMES:
        p = ROOT / (name + '.jsonl')
        dst = Path(str(p) + '.gz')
        index = ROOT / (name + '.index.jsonl.gz')
        assert shutil.disk_usage(ROOT).free > 1024 ** 3, 'need >1GiB available before next archive'
        before = signature(p)
        raw_hash = hashlib.sha256()
        with p.open('rb') as src, dst.open('xb') as raw_archive:
            with gzip.GzipFile(fileobj=raw_archive, mode='wb', compresslevel=6, mtime=0) as out:
                while chunk := src.read(CHUNK):
                    raw_hash.update(chunk)
                    out.write(chunk)
            raw_archive.flush()
            os.fsync(raw_archive.fileno())
        assert signature(p) == before, 'source changed during compression'
        restored_hash, restored_bytes, events, stages = hashlib.sha256(), 0, Counter(), Counter()
        with gzip.open(dst, 'rb') as restored, index.open('xb') as raw_index:
            with gzip.GzipFile(fileobj=raw_index, mode='wb', compresslevel=6, mtime=0) as out_index:
                for line in restored:
                    restored_hash.update(line)
                    restored_bytes += len(line)
                    record = json.loads(line)
                    events[record.get('event', 'unknown')] += 1
                    if record.get('event') == 'pool_manifest':
                        stages[record.get('stage', 'unknown')] += 1
                    brief = {k: v for k, v in record.items() if k not in OMIT}
                    out_index.write((json.dumps(brief, ensure_ascii=False, separators=(',', ':')) + '\n').encode())
            raw_index.flush()
            os.fsync(raw_index.fileno())
        assert restored_hash.digest() == raw_hash.digest(), 'decompressed SHA mismatch'
        assert restored_bytes == before[2], 'decompressed size mismatch'
        assert stages.get('raw_checked') == 96 and stages.get('post_prune') == 96 and stages.get('eligible') == 96
        # Verify compact index is readable and preserves every event.
        with gzip.open(index, 'rb') as inp:
            assert sum(1 for line in inp if json.loads(line)) == sum(events.values())
        entry = {'original_path': str(p), 'archive_path': str(dst), 'index_path': str(index),
                 'original_bytes': before[2], 'archive_bytes': dst.stat().st_size,
                 'index_bytes': index.stat().st_size, 'uncompressed_sha256': raw_hash.hexdigest(),
                 'events': dict(events), 'stages': dict(stages), 'verified_utc': utc(),
                 'status': 'verified_archive_original_present'}
        receipt['files'].append(entry)
        save(receipt)  # Durable evidence exists before removal.
        assert p.resolve(strict=True) == ROOT / (name + '.jsonl') and not p.is_symlink()
        assert signature(p) == before, 'source changed before removal'
        print('VERIFIED_DELETE', str(p), 'sha256', raw_hash.hexdigest(), flush=True)
        p.unlink()  # Explicit allowlist target verified twice; only redundant original.
        entry['status'] = 'verified_archive_original_removed'
        entry['freed_bytes'] = before[2] - dst.stat().st_size - index.stat().st_size
        save(receipt)
        print('COMPACTED', name, 'freed_bytes', entry['freed_bytes'], flush=True)
    receipt.update(status='completed', completed_utc=utc(),
                   total_freed_bytes=sum(r['freed_bytes'] for r in receipt['files']),
                   free_bytes_after=shutil.disk_usage(ROOT).free)
    save(receipt)
    print(json.dumps({'status': receipt['status'], 'total_freed_bytes': receipt['total_freed_bytes']}), flush=True)


if __name__ == '__main__':
    main()

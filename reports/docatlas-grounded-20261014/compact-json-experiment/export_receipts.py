"""Preserve complete stdio/client receipts with per-file SHA-256; no calls."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    run = Path(sys.argv[1])
    report = Path(__file__).resolve().parent
    names = ('FREEZE.json', 'MEASUREMENTS.json', 'EVIDENCE_AUDIT.json')
    for name in names:
        (report / name).write_bytes((run / name).read_bytes())
    paths = [p for p in sorted(run.rglob('*')) if p.is_file() and p.name not in names]
    manifest = {p.relative_to(run).as_posix(): dict(bytes=p.stat().st_size, sha256=sha(p.read_bytes())) for p in paths}
    target = report / 'receipts.tar.xz'
    with tarfile.open(target, 'w:xz') as archive:
        for path in paths:
            archive.add(path, arcname=path.relative_to(run).as_posix())
    with tarfile.open(target) as archive:
        assert set(archive.getnames()) == set(manifest)
        for name, receipt in manifest.items():
            raw = archive.extractfile(name).read()
            assert len(raw) == receipt['bytes'] and sha(raw) == receipt['sha256']
    (report / 'RECEIPTS_ARCHIVE.json').write_text(json.dumps(dict(
        archive_bytes=target.stat().st_size, archive_sha256=sha(target.read_bytes()), files=manifest,
        verified=True, included='Full trials/traces, actual client TextContent bytes and MCP results, oracle and preparation receipts'), indent=2) + '\n')
    print(f'Archived {len(paths)} files, {target.stat().st_size} bytes; all hashes verified.')


if __name__ == '__main__':
    main()

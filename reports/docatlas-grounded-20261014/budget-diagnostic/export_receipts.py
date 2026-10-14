"""Export small receipts plus one lossless archive; no product calls."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import zipfile


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    repo, run, research, ci = map(Path, sys.argv[1:])
    report = Path(__file__).resolve().parent
    for name in ('FREEZE.json', 'MEASUREMENTS.json', 'BOUNDARY_ASSESSMENT.json'):
        (report / name).write_bytes((run / name).read_bytes())
    (report / 'PRIMARY_SOURCES.json').write_bytes((research / 'SOURCES.json').read_bytes())
    assessment_path = ci / 'source-native-v40/assessment/CASE_RESULTS.json'
    assessed = json.loads(assessment_path.read_bytes())
    wheel_path = ci / 'candidate-wheel/doc_atlas-1.3.2-py3-none-any.whl'
    with zipfile.ZipFile(wheel_path) as wheel:
        mismatched = [name for name in wheel.namelist() if name.startswith('docmancer/') and not name.endswith('/')
                      and digest(wheel.read(name)) != digest((repo / name).read_bytes())]
    assert not mismatched
    receipt = dict(run_url='https://github.com/Vanilla1999/DocAtlas/actions/runs/38552651643',
        artifact_id=11887353099, artifact_name='source-native-v40-a011c7298f0731455799de2b19b4b7bb304876e8',
        head=(ci / 'source-native-v40/head.txt').read_text().strip(),
        assessment_sha256=digest(assessment_path.read_bytes()), wheel_sha256=digest(wheel_path.read_bytes()),
        all_ci_wheel_product_files_match_checkout=True,
        counts={key: dict(passed=sum(c['native'].get(key) is True for c in assessed['cases']),
                         assessed=sum(c['native'].get(key) is not None for c in assessed['cases']))
                for key in ('strict_positive_pass', 'strict_partial_documented_pass', 'strict_negative_empty_source_pass')},
        exposed_cases=[c for c in assessed['cases'] if c['case_id'] in ('V40-P03', 'V40-E01')])
    (report / 'CI_V40_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    paths = [(p, 'run/' + p.name) for p in run.iterdir() if p.is_file() and p.name not in
             ('FREEZE.json', 'MEASUREMENTS.json', 'BOUNDARY_ASSESSMENT.json')]
    paths += [(p, 'primary/' + p.name) for p in research.iterdir() if p.is_file() and '-plain.' not in p.name]
    paths += [(ci / 'source-native-v40' / name, 'ci/' + name) for name in
              ('FROZEN_RUN.json', 'WORKER.json', 'SUMMARY.json', 'assessment.log', 'runtime.log', 'integration.xml')]
    archive_path = report / 'receipts.tar.xz'
    with tarfile.open(archive_path, 'w:xz') as archive:
        for p, name in paths:
            archive.add(p, arcname=name)
    manifest = {name: dict(bytes=p.stat().st_size, sha256=digest(p.read_bytes())) for p, name in paths}
    with tarfile.open(archive_path) as archive:
        for name, expected in manifest.items():
            assert digest(archive.extractfile(name).read()) == expected['sha256']
    (report / 'RECEIPTS_ARCHIVE.json').write_text(json.dumps(dict(archive_sha256=digest(archive_path.read_bytes()),
        archive_bytes=archive_path.stat().st_size, files=manifest, verified=True,
        omitted_duplicate='BoundaryObserver writes call-1.json per instance; use unique per-case trace files, not overwritten scratch boundaries'), indent=2) + '\n')
    print('Archive bytes:', archive_path.stat().st_size)
    print('CI:', receipt['counts'])


if __name__ == '__main__':
    main()

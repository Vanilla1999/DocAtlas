"""Replay the viewed four-question skill smoke fixture; no model inference.

Run from the repository root with frozen dependencies and PYTHONHASHSEED=0.
Saved historical answers are not substituted for new model generations.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

from .baseline_probe import environment, run, write_report
from .pilot_io import evidence_blocks

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    fixture = HERE / 'skill_smoke'
    protocol = json.loads((fixture / 'protocol.json').read_text())
    original_freeze = json.loads((fixture / 'freeze.json').read_text())
    specs = original_freeze['sources']
    for scope, source in protocol['sources'].items():
        url = (f"https://raw.githubusercontent.com/{protocol['source_repository']}/"
               f"{protocol['source_commit']}/{source}")
        with urlopen(url, timeout=40) as response:
            raw = response.read()
        entry = specs[scope]['sources'][0]
        if sha256(raw) != entry['sha256']:
            raise ValueError(f'Source bytes differ from frozen run: {scope}')
        dest = out / 'corpora' / scope / entry['path']
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    paths = [fixture / 'protocol.json', Path(__file__), REPO / 'uv.lock',
             REPO / 'docmancer/templates/skill.md']
    hashes = {str(p.relative_to(REPO)): sha256(p.read_bytes()) for p in paths}
    write_report(out / 'freeze.json', {
        'created_before_first_handler_call': datetime.now(timezone.utc).isoformat(),
        'sha256': hashes, 'sources': specs, 'environment': environment(),
        'independent_holdout': False, 'answer_generation': 'NOT_RUN',
    })
    for task in protocol['tasks']:
        observed = run(out / 'corpora' / task['scope'], specs[task['scope']], {
            'question': task['question'], 'lookup_queries': [task['lookup']],
        })
        write_report(out / f"{task['id']}-raw.json", observed)
        if observed['status'] != 'EXECUTED':
            raise RuntimeError('Handler/audit failure; retained, not a retrieval miss')
        write_report(out / f"{task['id']}-packet.json", {
            'question': task['question'],
            'evidence': evidence_blocks(observed['payload']),
        })
        print(task['id'], observed['status'], observed['budget_tokens'], flush=True)
    if hashes != {str(p.relative_to(REPO)): sha256(p.read_bytes()) for p in paths}:
        raise RuntimeError('Inputs changed during replay')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

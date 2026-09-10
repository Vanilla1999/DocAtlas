"""Read-only same-environment path control for the observed baseline Q10 drift."""
from pathlib import Path
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ['EXPERIMENT_OUT'])
OUT.mkdir(parents=True, exist_ok=True)
BASE = Path(os.environ['BASELINE_ROOT']).resolve()
ALT = BASE.parent / 'direct-question-baseline'
SHA = 'e179471527e009c88f77acbdaeeeeb8ad1c8d316'
if not ALT.exists():
    subprocess.run(['git', '-C', str(ROOT), 'worktree', 'add', '--detach', str(ALT), SHA], check=True)
corpus = json.loads((ROOT / 'eval/direct_docatlas_questions_15/cases.json').read_text())
corpus['cases'] = [c for c in corpus['cases'] if c['id'] == 'Q10']
cp = OUT / 'q10-corpus.json'
cp.write_text(json.dumps(corpus))
script = (ROOT / 'eval/direct_docatlas_questions_15/audit_first_loss.py').read_text()
script = script.replace('connection.close()', 'report["product_brief_index_rows"] = [r for r in index_rows if r["source_path"] == "docs/DOCMANCER_PRODUCT_BRIEF.md"]\n            connection.close()')
script = script.replace('"status": payload.get("status"),', '"raw_payload": payload,\n                    "status": payload.get("status"),')
observer = OUT / 'q10-path-observer.py'
observer.write_text(script)
summary = []
for engine, code in [('baseline', BASE), ('current', ROOT)]:
    for variant, project in [('short', BASE), ('previous', ALT)]:
        name = engine + '-' + variant
        env = dict(os.environ, DOCATLAS_CODE_ROOT=str(code), DOCATLAS_OFFLINE='1', DOCATLAS_AUTO_VECTORS='0')
        result = subprocess.run([sys.executable, str(observer), '--project-root', str(project), '--corpus', str(cp), '--output', str(OUT / (name + '.json'))], cwd=code, env=env, text=True, capture_output=True, timeout=180)
        (OUT / (name + '.log')).write_text(result.stdout + '\nSTDERR\n' + result.stderr)
        if result.returncode:
            raise RuntimeError(name + ' failed; see log')
        report = json.loads((OUT / (name + '.json')).read_text())
        q = report['results'][0]
        row = {'engine': engine, 'code_root': str(code), 'project_path': str(project), 'project_head': report['project_head'], 'question': q['question'], 'visible_facts': q['visible_fact_count'], 'total_facts': len(q['facts']), 'source_hashes': report['summary']['source_hashes'], 'first_loss_counts': report['summary']['first_loss_counts'], 'indexed_brief_chunks': len(report['product_brief_index_rows'])}
        summary.append(row)
        print(json.dumps(row), flush=True)
(OUT / 'q10-path-summary.json').write_text(json.dumps(summary, indent=2) + '\n')

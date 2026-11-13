import json
import shutil
import subprocess
from pathlib import Path
import importlib.util

OUT=Path('/tmp/opencode/terra-step8')
addition='''
Operational clarification for this diagnostic:
1. After language preflight, make the first get_docs_context call with the original question and no lookup_queries. If the question is Russian and the declared corpus contains English, include search_question as a complete meaning-preserving English translation, not keywords. Preserve exact literals.
2. Inspect whether each aspect of the user's question has evidence. If a specific fact is missing, briefly state the gap. When a next portion is offered, request that portion with exactly the same question, translation, lookups and scope and the issued token. Keep prior evidence. Stop as soon as the answer is sufficient, no continuation remains, a portion supplies no useful new evidence, or your 12-step budget is reached. Do not read a fixed number of portions.
3. For a remaining gap after useful continuation stops, start a new first portion with the SAME original question and two lookup_queries: a full paraphrase in the documentation language and its keywords. Do not add expected answers or independent subquestions. An issued bounded source read can be used when a returned source is clearly relevant. Do not treat candidate counts or status=ok as completeness.
'''
for corpus in ('L0','L2'):
    config=json.loads((OUT/corpus/'docatlas/opencode.json').read_text())
    config['agents']['measure']['system']+=addition
    dest=OUT/corpus/'clarified'
    dest.mkdir(exist_ok=True)
    (dest/'opencode.json').write_text(json.dumps(config,ensure_ascii=False,indent=2))
# Reuse only the runner function; prevent its top-level execution.
source=Path('/tmp/opencode/run_terra_review.py').read_text()
source=source[:source.index('with concurrent.futures.ThreadPoolExecutor')]
ns={'__name__':'diagnostic_runner'}
exec(compile(source,'run_terra_review.py','exec'),ns)
from concurrent.futures import ThreadPoolExecutor
cases=json.loads((OUT/'cases.json').read_text())
jobs=[(c,'clarified',q) for c in ('L0','L2') for q in cases if q['id'] in ('T01-ru','T12-ru')]
with ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(ns['run'],jobs))

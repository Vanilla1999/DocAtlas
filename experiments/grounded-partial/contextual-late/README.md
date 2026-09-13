# Contextual BM25 × Late Chunking, bounded sufficiency screening

Read PROTOCOL_RU.md and RESULT_RU.md. This experiment reuses the pinned, genuine model scores and question-blind descriptions in research-suite; no model downloads or inference are required. It introduces no production dependency. The four lanes differ only in sparse contextualization and dense chunk encoding. Sufficient Context is an offline evaluation principle, not a deployed autorater or an oracle-driven retrieval policy.

From repository root using the existing project Python environment:

```bash
python experiments/grounded-partial/research-suite/restore.py
python -m pytest experiments/grounded-partial/contextual-late/test_factorial.py experiments/grounded-partial/semantic-selection/test_evaluate.py -q
python experiments/grounded-partial/hypothesis5/no_network.py experiments/grounded-partial/research-suite/verify_baseline.py
python experiments/grounded-partial/hypothesis5/no_network.py experiments/grounded-partial/research-suite/evaluate.py --input /tmp/docatlas-research-input --output /tmp/docatlas-contextual-late-recheck --embeddings /tmp/docatlas-embedding-output-v2/rankings.json --contexts /tmp/docatlas-contextual-final/contexts.json --hybrid-factorial-only
python experiments/grounded-partial/hypothesis5/no_network.py experiments/grounded-partial/contextual-late/analyze.py --evaluation /tmp/docatlas-contextual-late-recheck --output /tmp/docatlas-contextual-late-report
```

Use a fresh evaluation output path. `restore.py` restores only frozen development inputs, never the20-case holdout. The analyzer checks reproduction of all80 historical hybrid control outputs and records exact final payloads, paired changes, and three-way sufficient/needs_review/insufficient assessments. Frozen gold is not modified. `results/questions.json` is the human-readable source of every question and all four delivered MCP-shaped payloads. These are projector replays, not a new live MCP-server or answer-agent test.

The post-hoc starlette order probe contains its exact original input and both outputs. Reproduce its only intervention after restoring the inputs:

```python
import json, lzma
from copy import deepcopy
from pathlib import Path
from docmancer.docs.application.docs_context_projection import project_docs_context

probe = json.loads(lzma.decompress(Path('experiments/grounded-partial/contextual-late/results/starlette-order-probe.json.xz').read_bytes()))
for swap in (False, True):
    retrieval = deepcopy(probe['original']['input'])
    if swap:
        retrieval['context_pack'][0], retrieval['context_pack'][1] = retrieval['context_pack'][1], retrieval['context_pack'][0]
    payload, snapshot = project_docs_context(retrieval=retrieval)
    expected = probe['swapped' if swap else 'original']['payload']
    spans = lambda p: [(s['path_or_url'], s['snippet']) for s in p.get('sources', [])]
    assert spans(payload) == spans(expected)
    print(swap, spans(payload))
```

This swap diagnoses sensitivity to candidate ordering on one exposed case. It is not part of the four retrieval lanes and cannot be credited as a product improvement.

# Research suite: XProvence, Late Chunking, Contextual Retrieval

Read PROTOCOL_RU.md, AMENDMENTS.md and RESULT_RU.md together. The original preregistration is preserved; amendments identify implementation corrections and CPU feasibility changes before the corresponding retrieval results were inspected. No production code or frozen annotations are changed.

Final models: XProvence multilingual reranker/pruner; Jina v3 with upstream task instruction prefixes and task adapters; Qwen2.5-0.5B-Instruct official Q8_0 GGUF for question-blind context generation. The Qwen experiment does not reproduce Anthropic's model quality. English Provence weights and the Sufficient Context paper's LLM autorater are not separately run. Sufficient Context is applied as a stage-by-stage evaluation principle using unchanged frozen witnesses.

Python3.12 environment used: torch2.6.0+cpu, transformers4.51.3, sentencepiece0.2.0, spacy3.8.7, xx_sent_ud_sm3.8.0, einops0.8.1, peft0.15.2, llama-cpp-python0.3.35. Use the repository's dependencies as well. The spaCy model wheel is pinned at `https://github.com/explosion/spacy-models/releases/download/xx_sent_ud_sm-3.8.0/xx_sent_ud_sm-3.8.0-py3-none-any.whl`. Model code and immutable revisions are pinned in bootstrap_models.py and input-code-identity.json. Model weights are not committed. XProvence model card reports CC-BY-NC-ND4.0; Jina v3 reports CC-BY-NC4.0; deployment suitability requires separate consideration.

From repository root, with this environment's Python:

```bash
python experiments/grounded-partial/research-suite/restore.py
python experiments/grounded-partial/hypothesis5/no_network.py experiments/grounded-partial/research-suite/verify_baseline.py
python experiments/grounded-partial/hypothesis5/no_network.py experiments/grounded-partial/research-suite/evaluate.py --input /tmp/docatlas-research-input --output /tmp/research-recheck --xprovence /tmp/docatlas-xprovence-output-v2/rows.json --embeddings /tmp/docatlas-embedding-output-v2/rankings.json --context-embeddings /tmp/docatlas-context-embedding-final/rankings.json --contexts /tmp/docatlas-contextual-final/contexts.json
python experiments/grounded-partial/research-suite/analyze.py --evaluation /tmp/research-recheck
```

Recompute model inference if needed (bootstrap is explicitly online; inference is offline):

```bash
python experiments/grounded-partial/research-suite/bootstrap_models.py
python experiments/grounded-partial/hypothesis5/no_network.py experiments/grounded-partial/research-suite/xprovence.py --input experiments/grounded-partial/semantic-selection/results/candidates.jsonl --output /tmp/xprovence-recompute
python experiments/grounded-partial/hypothesis5/no_network.py experiments/grounded-partial/research-suite/embed.py --input /tmp/docatlas-research-input --output /tmp/embeddings-recompute
python experiments/grounded-partial/hypothesis5/no_network.py experiments/grounded-partial/research-suite/contextualize_gguf.py --input /tmp/docatlas-research-input --output /tmp/contexts-recompute
python experiments/grounded-partial/hypothesis5/no_network.py experiments/grounded-partial/research-suite/embed.py --input /tmp/docatlas-research-input --output /tmp/context-embeddings-recompute --contexts /tmp/contexts-recompute/contexts.json --base /tmp/embeddings-recompute/vectors.npz
```

prepare.py documents initial extraction from the pinned index; restore.py provides its exact saved output without rebuilding an index. Source snippets remain literal originals. Generated descriptions affect retrieval only, never citations or gold. BM25 is a small controlled experiment (k1=1.2,b=.75), not a claim to reproduce native SQLite FTS; hybrid uses fixed RRF k=60.

Replay feeds newly retrieved original spans through the existing projector and retags the fixed query plan. It is not a full native handler integration. Its unmodified-pool control is essential: retagging itself changes one case. Source-only packets are explicitly separate, bounded diagnostics; they do not implement a safe production admission policy. Top-k completeness is not proof that all top-k content fits800 tokens. Pruned fragment counts are not original candidate counts; compare x_rank_top5 to the entire retained x_rank_pruned_top5 set.

`pilots/` records superseded torch contextualization and its cache check, solely to explain the performance amendments. They are not used for the final index. No weak/live answer-generating model was tested; preprocessing sees documents and chunks only. No holdout tuning is permitted.

The raw archive includes full rankings/scores and exact final snapshots, but not large embedding vector arrays; recompute embeddings to regenerate those arrays. Six source-coverage counterexample tests are in `semantic-selection/test_evaluate.py`. `x-pruning-manual-review.json` is explicitly post-hoc, before packing, and does not replace frozen gold. `NEXT_SMALL_STEP_RU.md` separates measurement repair from the next admission experiment.

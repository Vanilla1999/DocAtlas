# Mini / budget: 40-question public integration comparison

This experiment compares two opt-in candidate selectors on the prepared,
source-valid original project read. It stops at the actual public context DTO,
before an answer generator. The complete historical V40 corpus is reused: it is
an exposed repeated measurement, not a new blind holdout. See `CORPUS_RU.md` for
source commits, licenses and limitations of the unchanged historical oracle.

## Host configuration

Both modes use the same live checked native pool, source policy and downstream
validators. The selector cannot create evidence, source authority, query credit
or a sufficient answer. The default is unchanged when the selector is unset.
The options are host environment configuration, never request fields.

```bash
export DOCATLAS_EXPERIMENT_ADMISSION=source_valid_candidates_v1
export DOCATLAS_EXPERIMENT_PREPARED_PARENTS=1
export DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS=12000
export DOCATLAS_EXPERIMENT_SELECTOR_TOP_K=2
export DOCATLAS_EXPERIMENT_SELECTOR=budget
```

Enable the prepared-parent option **before indexing** to save the derived
structure. Normal live source checks still run for each read. `budget` takes the
first two already checked native candidates in existing order and does not load
the optional neural runtime.

To choose with the same model as V2, prepare the optional runtime and pinned
assets once, outside the document corpus and index:

```bash
uv venv .venv-mini
uv pip install --python .venv-mini/bin/python torch==2.10.0+cpu \
  --index https://download.pytorch.org/whl/cpu
uv pip install --python .venv-mini/bin/python -e '.[dev,reranker-mini]'
hf download cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 \
  config.json model.safetensors sentencepiece.bpe.model special_tokens_map.json \
  tokenizer.json tokenizer_config.json \
  --revision 1427fd652930e4ba29e8149678df786c240d8825 \
  --local-dir /absolute/model-assets/mini
export DOCATLAS_EXPERIMENT_MINI_PATH=/absolute/model-assets/mini
export DOCATLAS_EXPERIMENT_SELECTOR=mini
```

Queries never download weights. The six local files must match the pinned hashes.
Mini uses CPU FP32, eight intra-operation threads, raw logits and stable original
index ties. Inter-operation threads are host-owned; the experiment sets them to
one, matching V2, and records the actual runtime. Model loading is lazy and
resident; a host may call `preload_mini_runtime(path)` to measure it separately.

When the pool has at most `top_k` candidates, Mini records `not_needed` and makes
no forward. When **any full question/window pair exceeds 512 Mini tokens**, it
records `budgetfallback_overflow` and chooses the budget result for that whole
pool before any forward. It never silently truncates a native source window.
Missing assets, invalid configuration and inference errors are explicit errors.
Mini is not an abstention or sufficiency classifier; there is no score cutoff.

## Reproduce the bounded comparison

Use new output and workspace directories for every attempt. A failed attempt is
retained, never overwritten. The runtime workspace must be outside this checkout.
For sandboxed hosts without `/tmp`, set `TMPDIR` to an existing private directory.

```bash
PYTHONHASHSEED=0 .venv-mini/bin/python -m eval.prepared_model_comparison40.run \
  --model-path /absolute/model-assets/mini \
  --run-dir /absolute/reports/attempt-01 \
  --work-dir /absolute/isolated-runtime/attempt-01
.venv-mini/bin/python -m eval.prepared_model_comparison40.evaluate \
  --run-dir /absolute/reports/attempt-01 \
  --corpus-dir /absolute/DocAtlas/eval/prepared_model_comparison40
```

The driver executes five real `prepare_docs` operations and 80 public
`get_docs_context` calls. It alternates arm order across the 40 cases, retains
the same generation within each pair, checks unchanged source files and SQLite
state, and records actual native pools and full public JSON. It never supplies
gold, answerability labels or expected spans to retrieval or Mini. This is an
installed-package, in-process public MCP integration, not a stdio client test.

Outputs distinguish exact frozen-span delivery, the strict negative empty-source
contract, source integrity, selection opportunities, overflow and actual model
work. Full answer quality and answer citation accuracy need a separate generator
experiment. Timing includes the optional copied observer receipts and enabled
trace; cold preparation is reported separately. A shared resident process cannot
measure the memory difference between standalone model-free and model modes.

New implementation files, all questions, gold and sources are hashed before the
first product call and checked unchanged afterward. The runner and independent
offline evaluator are kept separate so expected answers cannot affect selection.

# Q6 selection and delivery profiles

This is a development diagnostic of the ordinary 12,000-token joint-selection
path. It is not a new production policy, a blind benchmark, or a proof of final
answer quality. Product code and defaults are unchanged from main `420e2192`.

[Results (RU)](RESULTS_RU.md) · [Independent review (RU)](REVIEW_RU.md) ·
[Public evidence manifest](evidence/manifest.json)

Read [the frozen protocol](PROTOCOL_RU.md) before running. The independent
source quotations are in `oracle.json`; `FREEZE_MANIFEST.json` pins all 19
documents, their original catalog, the question and the oracle. The corpus
manifest was recorded before the first MCP call and subsequently copied into
the checked-in freeze file. The probe refuses a different corpus or oracle.

## Prepare an isolated installation

From this checkout, using Python 3.12 and a writable directory outside the
repository:

```bash
Q6_WORKSPACE=$(mktemp -d)
UV_PROJECT_ENVIRONMENT="$Q6_WORKSPACE/venv" uv sync --frozen --no-dev --no-install-project
uv build --wheel --out-dir "$Q6_WORKSPACE/wheels"
uv pip install --python "$Q6_WORKSPACE/venv/bin/python" --no-deps "$Q6_WORKSPACE"/wheels/*.whl
```

For the three MiniLM lanes, explicitly provision the six pinned assets listed
in `docmancer/docs/application/experimental_selection_modes.py` and their exact
SHA-256 values. The model is
`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, revision
`1427fd652930e4ba29e8149678df786c240d8825`. Install the optional runtime used
in this report:

```bash
uv pip install --python "$Q6_WORKSPACE/venv/bin/python" \
  --index https://download.pytorch.org/whl/cpu torch==2.10.0
uv pip install --python "$Q6_WORKSPACE/venv/bin/python" \
  transformers==4.57.1 safetensors==0.8.0 sentencepiece==0.2.1
```

Set `Q6_MODEL_DIR` to the absolute directory containing those six verified files.
The probe never downloads a model. Its server uses offline mode and the
production local-only, hash-checking loader. The six verified files total
492,745,974 bytes; model preparation is separate from query measurements.

## Reproduce the profile comparison

The initial preparation copies the exact catalog, descriptions, scope and
authority. Every subsequent command reuses that same prepared store. Each
command makes one real public `get_docs_context` call; the first also makes
one explicit `prepare_docs` call. Do not run multiple lanes simultaneously
against this work directory.

```bash
"$Q6_WORKSPACE/venv/bin/python" -I eval/q6_section_context/probe.py \
  --work "$Q6_WORKSPACE/work" --out "$Q6_WORKSPACE/runs/compact-observed" \
  --profile compact --mode lexical --observe
"$Q6_WORKSPACE/venv/bin/python" -I eval/q6_section_context/probe.py \
  --work "$Q6_WORKSPACE/work" --out "$Q6_WORKSPACE/runs/compact-plain" \
  --profile compact --mode lexical --compare-to "$Q6_WORKSPACE/runs/compact-observed"
"$Q6_WORKSPACE/venv/bin/python" -I eval/q6_section_context/probe.py \
  --work "$Q6_WORKSPACE/work" --out "$Q6_WORKSPACE/runs/canonical-observed" \
  --profile canonical --mode lexical --observe
"$Q6_WORKSPACE/venv/bin/python" -I eval/q6_section_context/probe.py \
  --work "$Q6_WORKSPACE/work" --out "$Q6_WORKSPACE/runs/canonical-plain" \
  --profile canonical --mode lexical --compare-to "$Q6_WORKSPACE/runs/canonical-observed"
```

Both profiles use `DOCATLAS_MCP_TEXT_FALLBACK=1` and disable section compression.
`compact` also sets `DOCATLAS_MCP_COMPACT_TEXT=1`, retaining default adaptive
Context Assembly. `canonical` leaves the compact flag unset. There is no
change to the 12,000 limit, source admission or retrieval. These are different
wire profiles; do not attribute a profile difference to a new ranker.

## Compare scoring inputs inside one profile

Run these once, after preserving the canonical baseline:

```bash
for Q6_MODE in mini body contextual; do
  "$Q6_WORKSPACE/venv/bin/python" -I eval/q6_section_context/probe.py \
    --work "$Q6_WORKSPACE/work" --out "$Q6_WORKSPACE/runs/canonical-$Q6_MODE" \
    --profile canonical --mode "$Q6_MODE" --model-dir "$Q6_MODEL_DIR" --observe
done
```

`mini` is the existing joint MiniLM route. `body` and `contextual` install the
explicit evaluation-only scorer from `contextual_relevance.py` in a dedicated
MCP worker. They reuse the production complete fit-first MiniLM scorer and
preserve all checked source rows, eligibility, grouping, MMR, costs, final
budgeting and source checks. `contextual` adds only source-exact ancestor
introductions and the owning heading, separately qualified under the live
read's provenance. Context is not returned as new evidence.

The clean ablation is **body versus contextual**. Comparing existing `mini`
with `body` also changes batching, sigmoid implementation and handling of long
input; it is not solely a truncation ablation. Neither score is answer coverage.

The worker never reads `oracle.json`. The parent independently checks actual
delivered source bytes, line spans, source bindings, scope, authority, version,
read-only state and literal source quotations after receiving the MCP reply.
Optional observation records the same real acquisition and selection calls.
Every response must satisfy the original token/UTF-8 proxy ceiling.

## Inspect or re-score without another product call

`--out` must be a new directory. Raw replies, observations, process settings,
source manifests, index state and call ledgers are saved there. A summary
failure does not erase the original reply or the call count.

```bash
"$Q6_WORKSPACE/venv/bin/python" -I eval/q6_section_context/probe.py \
  --rescore "$Q6_WORKSPACE/runs/canonical-observed"
```

`--rescore` performs no new MCP/model calls. Keep original raw evidence private
to the local diagnostic environment: it contains absolute runtime paths and
source continuation capabilities. The public `evidence/` package contains
explicitly selected review data and hashes, with original source text preserved.
It does not contain replayable capabilities or model weights.

Named regression cases are `main-flow-Q1`, `main-flow-Q9` and `T01-en`. They are
development controls on the same frozen 19-document corpus. The unpublished
historical no-answer Q10 was not reconstructed and is not claimed as checked.

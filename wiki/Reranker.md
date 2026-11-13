# Experimental Qwen reranker (pinned, opt-in)

DocAtlas ships a pinned, opt-in evidence scorer built on
**Qwen/Qwen3-Reranker-0.6B** @ `e61197ed45024b0ed8a2d74b80b4d909f1255473`.
It re-scores the checked candidate pool for `get_docs_context` and enables the
`no_redundancy` selection mode. This is an **experimental** mode: the measured
metric is literal witness delivery; semantic answer correctness is not claimed.

The default lexical path never touches these dependencies — you only need this
page if you explicitly enable the paired Qwen scoring.

## Requirements (pinned contract)

The scorer enforces an exact runtime contract on every call; any deviation is a
hard error, not a warning:

| Component | Pinned value |
|---|---|
| Model | `Qwen/Qwen3-Reranker-0.6B` @ `e61197ed…` (9 files, exact SHA-256) |
| torch | `2.10.0+cu128` (CUDA 12.8 build) |
| GPU | CUDA capability **12.0** — Blackwell (RTX 50xx) only |
| transformers / tokenizers / safetensors | `4.57.1` / `0.22.2` / `0.8.0` |
| Precision / attention / batch | bfloat16, sdpa, batch 1 |

Other GPUs are intentionally unsupported in this pinned experiment; there is no
CPU fallback and no lexical fallback when scoring fails — the call fails loudly.

## Step 1 — prepare the model assets

```bash
doc-atlas reranker prepare ~/.docatlas/reranker-qwen3
```

Downloads the pinned revision from Hugging Face (~1.2 GB), verifies every file
against the pinned SHA-256 (including the remote LFS/Git object identity) and
writes the `provenance.json` manifest the scorer requires. No CUDA is needed at
preparation time. Re-running into a non-empty directory is refused; a failed
run cleans up its partial directory.

> Network note: weight downloads follow Hugging Face redirects to its CDN
> (`us.aws.cdn.hf.co`). If your network blocks that host, prepare the assets on
> a machine that can reach it and copy the directory over; `reranker check`
> verifies it locally.

## Step 2 — check readiness

```bash
doc-atlas reranker check ~/.docatlas/reranker-qwen3
```

Reports assets, every pinned runtime dimension (expected vs actual), the GPU
found, and the enabling environment. Exit code is non-zero until everything
matches; `--json` emits the full report.

If the runtime mismatches, install the pinned GPU stack into the tool
environment, for example:

```bash
uv tool install --force --with torch==2.10.0+cu128 \
  --index-url https://download.pytorch.org/whl/cu128 \
  --with transformers==4.57.1 --with tokenizers==0.22.2 --with safetensors==0.8.0 \
  doc-atlas
```

(The PyPI extra `reranker-mini` installs the CPU torch wheel for development
runs; it does **not** satisfy the pinned GPU runtime.)

## Step 3 — enable the mode

Set these in the MCP server environment (e.g. the agent's MCP config `env`):

| Variable | Value |
|---|---|
| `DOCATLAS_EXPERIMENT_PAIRED_QWEN` | `1` |
| `DOCATLAS_EXPERIMENT_QWEN_STUDY` | `1` |
| `DOCATLAS_EXPERIMENT_QWEN_SELECTION_MODE` | `no_redundancy` |
| `DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH` | absolute path to the prepared directory |
| `DOCATLAS_EXPERIMENT_PAIRED_CACHE` | absolute cache directory (recommended; otherwise every call re-scores) |

Guards: do **not** set `DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT=1`; a native
context token budget must be set; leave pool pruning/units settings at their
controls. `doc-atlas doctor` includes a `reranker` check group whenever
`DOCATLAS_EXPERIMENT_PAIRED_QWEN=1` is set.

## Cost and expectations

The reranker roughly doubles charged context tokens versus the lexical default
while delivering more required witnesses (see the step17 pipeline study). It is
a study arm, not a claim that Qwen scoring "beats" ordinary search: the control
arm is paired Qwen `R−D`, and semantic correctness was not measured.

## See also

- `doc-atlas reranker check --json` — machine-readable readiness report
- [Troubleshooting](./Troubleshooting.md)
- [Configuration](./Configuration.md)

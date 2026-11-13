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
| GPU | Exact CUDA compute capability **12.0** (for example GeForce RTX 50xx and some RTX PRO Blackwell GPUs) |
| transformers / tokenizers / safetensors | `4.57.1` / `0.22.2` / `0.8.0` |
| Precision / attention / batch | bfloat16, sdpa, batch 1 |

This is a frozen experimental runtime, not a general Qwen hardware requirement
or a claim that every GPU with that capability has been tested. A marketing
label such as "Blackwell" is not sufficient; other CUDA capabilities, CPU and
macOS are unsupported by this profile. The ordinary lexical path is independent
of this restriction. There is no CPU or lexical fallback when opted-in scoring
fails: the call fails and the profile must be repaired or explicitly disabled.

## Step 1 — prepare the model assets

```bash
doc-atlas reranker prepare ~/.docatlas/reranker-qwen3
```

Downloads the pinned revision from Hugging Face (~1.2 GB), verifies every file
against the pinned SHA-256 (including the remote LFS/Git object identity) and
writes the `provenance.json` manifest the scorer requires. No CUDA is needed at
preparation time. Use an absolute destination in a trusted, user-owned parent
directory. Symlink destinations (including dangling links), non-directories and
non-empty directories are refused. Downloads go to a private sibling staging
directory; only fully verified assets are published. Failure or Ctrl-C cleans
up only that operation's staging directory, never the destination or files
another process added there. A forced kill can leave a private staging directory;
an interruption after publication can leave a complete verified destination.
The parent directory must not be concurrently replaced by an untrusted process.

The manifest is a reproducibility receipt, not a signed download attestation.
Acceptance depends on the hashes pinned in the installed package and the actual
file bytes, not on trusting a supplied `provenance.json` alone.

> Network note: weight downloads follow Hugging Face redirects to its CDN
> (`us.aws.cdn.hf.co`). If your network blocks that host, prepare the assets on
> a machine that can reach it and copy the directory over; `reranker check`
> verifies it locally.

## Step 2 — check readiness

```bash
doc-atlas reranker check ~/.docatlas/reranker-qwen3
```

Reports assets, every pinned runtime dimension (expected vs actual), the GPU
found, and the validity of the **current process's** experimental configuration.
`--json` exposes `assets_ready`, `runtime_compatible`, `profile_valid`, `enabled`
and `inference_checked`. `ready` means that these preflight checks passed; it is
not proof that the model can load, fit in GPU memory or finish a forward pass.
`inference_checked` is false: this command never downloads or runs the model.
Exit code is non-zero for a failed preflight. Before Step 3, a successful check
can still report `enabled=false`.

The check does not discover or validate a different environment stored inside
Claude Code/OpenCode/Codex configuration. Run it again with the same variables
as the actual MCP server after enabling the profile. Request-specific native
scope/budget binding is still validated by the real MCP call.

For dependency-version mismatches on compatible hardware, install the pinned
stack into the tool environment. Keep PyPI as the default index and add the
named PyTorch CUDA index; do **not** replace PyPI with the PyTorch index using
`--index-url`. This recipe needs a recent uv with named `--index` support.

Use the exact package source under validation. The published-version example
below uses the current package version; for a source/release-candidate build,
replace it with the absolute path to that candidate's wheel. Do not silently
replace an unpublished candidate with a different package from PyPI.

```bash
DOCATLAS_RERANKER_SOURCE="doc-atlas==1.3.2"
uv tool install --force --with torch==2.10.0+cu128 \
  --index pytorch=https://download.pytorch.org/whl/cu128 \
  --default-index https://pypi.org/simple \
  --with transformers==4.57.1 --with tokenizers==0.22.2 --with safetensors==0.8.0 \
  "$DOCATLAS_RERANKER_SOURCE"
```

Then re-run `doc-atlas reranker check` and inspect every actual version. This
command cannot fix unsupported GPU capability or a missing driver. For missing
or invalid model assets, use `reranker prepare` with a new safe destination;
reinstalling torch does not repair assets. No package-install command downloads
the Qwen weights or enables the profile automatically.

The `reranker-mini` extra does **not guarantee** this pinned stack. In particular,
`torch==2.10.0` does not mean a CPU wheel: index/platform selection determines
the build, and the extra's other ranges are not the exact experimental pins.

## Step 3 — enable the mode

Set these in the MCP server environment (e.g. the agent's MCP config `env`):

| Variable | Value |
|---|---|
| `DOCATLAS_EXPERIMENT_PAIRED_QWEN` | `1` |
| `DOCATLAS_EXPERIMENT_QWEN_STUDY` | `1` |
| `DOCATLAS_EXPERIMENT_QWEN_SELECTION_MODE` | `no_redundancy` |
| `DOCATLAS_CONTEXT_COMPRESSION` | `off` (prevents the separate MiniLM route, including implicit activation by a model directory) |
| `DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH` | absolute path to the prepared directory |
| `DOCATLAS_EXPERIMENT_PAIRED_CACHE` | absolute cache directory (recommended; otherwise every call re-scores) |

Guards: do **not** set `DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT=1`; leave pool
pruning/units settings at their controls. Eligible native project/module reads
use the normal delivery ceiling unless a valid lower
`DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS` is configured. An unset override is not
a missing-budget error; ineligible request scope still fails in the actual call.
`doc-atlas doctor` includes a `reranker` check group whenever
`DOCATLAS_EXPERIMENT_PAIRED_QWEN=1` is set in its process environment.
Keep `DOCATLAS_CONTEXT_COMPRESSION=off` explicit: if it is unset, an existing
`DOCATLAS_MINILM_MODEL_DIR` can activate the separate MiniLM section compressor.
Combining that route with paired Qwen is a configuration error, not a fallback.

After editing the client configuration, restart its MCP server. Run the check
and doctor under that same environment, then perform one real documentation
read. A preflight is not an inference or final-answer-quality test.

## Disable the profile and return to lexical defaults

Remove the profile's `DOCATLAS_EXPERIMENT_PAIRED_QWEN`,
`DOCATLAS_EXPERIMENT_QWEN_STUDY`, `DOCATLAS_EXPERIMENT_QWEN_SELECTION_MODE`,
`DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH` and optional
`DOCATLAS_EXPERIMENT_PAIRED_CACHE` entries from the MCP server configuration.
Also remove any study-only pruning/units/unit-guard overrides you added and
restore any experimental budget override to its previous value. Do not leave
the study or selection-mode flags behind: turning off only `PAIRED_QWEN` can
leave an invalid profile. Restart the MCP server and perform a documentation
read. A shell `unset` alone does not change an existing client's MCP config.
This is an explicit return to the default profile, not an automatic fallback;
it does not delete the prepared model or cache.
For the lexical default, keep `DOCATLAS_CONTEXT_COMPRESSION=off`, especially
if a MiniLM directory remains configured for a different experiment.

## Cost and expectations

In the frozen step17 study, `no_redundancy` used roughly 2–2.5 times the charged
context tokens of the **paired Qwen `R−D` control** while delivering more required
literal witnesses on that study's exam. That is not a measured comparison with
the lexical default, a general quality guarantee or a final-answer accuracy
result. The study did not measure semantic correctness of generated answers.

## See also

- `doc-atlas reranker check --json` — machine-readable readiness report
- [Troubleshooting](./Troubleshooting.md)
- [Configuration](./Configuration.md)

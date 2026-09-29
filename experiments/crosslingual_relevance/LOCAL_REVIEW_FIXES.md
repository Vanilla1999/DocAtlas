# Task 44: local review corrections

Base: `84938ab25c096257a7ad6af5f39b9d364e67b8e9`.
These changes repair the experiment; they do **not** fix Typer's real-model score,
activate rescue in production, or validate the archived threshold on new tasks.
`M2B_THRESHOLD = 0.7453` is unchanged. No `docmancer/` production source, dependency
lock, original M1.5 manifest/pool, archived result, or `protocol_v3.lock.json` changed.
The original HANDOFF and logs remain historical, not results of this corrected runner.

## Corrections

* `scorer_runtime.py`: finite and typed execution limits; finite cosine in [-1,1];
  an explicit unbounded **finite** contract can be chosen for logits. One cooperative
  stage deadline includes cumulative time. Cached proven scores survive the work
  cap with a visible degraded/cache event. This does not interrupt native inference.
* `context_rescue.py`: only the original lexical rejection is rescued; prior
  source/identity/reference/subject vetoes remain. No evidence is discarded merely
  for having fewer than 80 characters. This changes scorer eligibility and requires
  fresh evaluation. Context-only admission still creates no answer/edit authority.
  Nested installations fail; unrelated threads/tasks do not inherit the question.
  The global patch remains an isolated experimental harness, NOT a serving API.
* Bindings now contain full text/question hashes, actual scorer fingerprint when
  available, a hash of the archived calibration specification, and source coordinates.
  A specification digest does not retrospectively prove historical model bytes.
* `evaluation_v2.py`: canonical relative path, coordinates, text and available hash
  binding are checked separately from policy and relevance. Complete packets require
  ALL required claims; each claim may have alternative canonical witnesses. A word,
  file name, or one-line overlap is not a fact. Unjudged blocks are not false positives.
* `evaluation_claims_v2.json`: a NEW external review rubric. It does not rewrite the
  frozen M1.5 gold. Exact witness clauses are intentionally conservative; alternative
  semantic presentations require explicit adjudication, not silent normalization of
  CLI literals. Evaluation claims are never supplied to real retrieval/scoring.
* M2 ranks the entire pool before attaching judgments. Ties use content/path hashes,
  not gold-first input order. The report says **known-positive recall**, separates
  hit-rate from recall, and preserves unjudged pairs. Zero observed errors on a
  small calibration set is not a transferable zero-FPR guarantee.
* Both M4 entry points and M5/M6 use the external canonical claim evaluator. M4
  reports first individually complete witness hit-rate, not file overlap. M5 no
  longer probes a hand-picked gold window and mistakes it for pipeline input.
* M6 defaults to a REAL scorer. `--oracle-plumbing` is explicit and its rows are never
  model-quality evidence. These already inspected tasks are not a new blind holdout.
  Policy errors use the native audit; absence from gold is not a policy violation.
* New outputs are exclusive UUID-named files under `review_runs/`; archived reports
  are never overwritten. Raw requests, packets, pipeline traces and opt-in scorer
  inputs are retained for diagnosis. Treat these local records as private if future
  experiments use private documents; do not publish them automatically.
* MPNet requires a LOCAL file manifest: actual weight/config/tokenizer hashes,
  dependency versions and runtime tokenizer settings. Retrieval and scoring use
  the same loaded object. Used/full token counts and offsets make truncation visible.
  No model downloads are triggered by the corrected runners. A missing lock fails
  before loading. CPU provider/one thread/mean pooling/dimension 768 are explicit.

## TDD execution in this local revision

Recorded before their implementations: scorer 20 assertion failures/4 passes;
metrics 10/1; real-oracle/loader controls 4/0; adapter 2/2; step2 3/1. The adapter's
first attempt included a test-double keyword-signature error; its separate log is
retained and NOT counted as a product RED. Thirty additional controls had no claim
of independent RED history. Final focused run: **77 new cases + 56 native neighbors
= 133 passes**. Five disabled-mechanism mutations reproduce assertion failures.
No existing product test assertions were removed, skipped or weakened.

A fresh ordinary SQLite/handler lexical control still returns 0/2 facts for mixed
and Russian Typer and 2/2 for English, without citation errors. This is not a neural
run. MPNet weights are unavailable in this environment; no new real MPNet/M2/M4/M5/M6
quality or cross-encoder result is claimed. Full repository CI was not rerun.

## How to run after exporting model files

Prepare a standalone local directory containing the actual FastEmbed MPNet files
(including `onnx/model.onnx`, tokenizer/config files). Do not use the model directory
for the manifest. Internal or external symlink escapes must be exported as files.

```bash
python -m experiments.crosslingual_relevance.model_manifest \
  --model-dir /absolute/model-export \
  --output /absolute/locks/mpnet.json
export DOCATLAS_RELEVANCE_MODEL_DIR=/absolute/model-export
export DOCATLAS_RELEVANCE_MODEL_MANIFEST=/absolute/locks/mpnet.json
# Only supply --revision when the immutable publisher commit is actually known.

python -m pytest -q experiments/crosslingual_relevance/tests
python -m experiments.crosslingual_relevance.run
python -m experiments.crosslingual_relevance.m4_dense_candidates --max-sections-per-source 2
python -m experiments.crosslingual_relevance.m4_step2_handler --max-sections-per-source 2
python -m experiments.crosslingual_relevance.m5_real_scorer --max-sections-per-source 2
python -m experiments.crosslingual_relevance.m6_holdout --max-sections-per-source 2
# Repeat separately with 20 to measure the previous pilot's changed candidate cap.
# --oracle-plumbing is ONLY a labelled mechanism control, never a model benchmark.
```

Both small and pilot caps are recorded. Inputs, used tokenizer offsets, scores,
qualification decisions and final quotes can now be joined by hashes. Fixing the
measurement does not license tuning the threshold to Typer. Choose a scorer and a
new separately versioned calibration only after inspecting actual inputs and hard
negatives; keep the old protocol and negative results intact.

# H1: semantic ordering on a frozen candidate pool

Research-only; no production dependencies or public API changes. Read PLAN_RU.md and AMENDMENT_01.md before interpreting results. The local cross-encoder does not generate answers.

## Reproduction

Use the DocAtlas environment with its normal pinned dependencies plus CPU torch 2.6.0, transformers 4.51.3 and sentencepiece 0.2.0. Download BAAI/bge-reranker-v2-m3 at revision 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e into a separate model directory. Run inference without outbound network access; the existing Linux wrapper uses libseccomp.

Commands below run from the repository root. PYTHON is an executable in the prepared environment; FIXTURE is the original frozen80 native fixture (corpus, state SQLite snapshots, rows.json and ingest records). OUT must be a new directory; MODEL is the downloaded model directory. Prefer /tmp for SQLite/WAL state.

```bash
$PYTHON experiments/grounded-partial/hypothesis5/no_network.py experiments/grounded-partial/semantic-selection/export.py --fixture "$FIXTURE" --output "$OUT/baseline"
$PYTHON experiments/grounded-partial/hypothesis5/no_network.py experiments/grounded-partial/semantic-selection/score.py --input "$OUT/baseline/candidates.jsonl" --model "$MODEL" --output "$OUT/scores"
$PYTHON experiments/grounded-partial/hypothesis5/no_network.py experiments/grounded-partial/semantic-selection/evaluate.py --baseline "$OUT/baseline" --scores "$OUT/scores" --output "$OUT/evaluation"
$PYTHON experiments/grounded-partial/hypothesis5/no_network.py experiments/grounded-partial/semantic-selection/downstream.py --fixture "$FIXTURE" --baseline "$OUT/baseline" --scores "$OUT/scores" --output "$OUT/downstream"
```

The baseline identity must match all80 original path/snippet pairs and yield 33/48. The scorer receives only question, opaque keys, source header and original text. Its input hash must match during evaluation. Model/tokenizer hashes and cold/warm inference timings are retained separately.

The standalone top-k diagnostic measures source-bound union coverage, not final DTO sufficiency. Native downstream diagnostics only reorder existing candidates; all normal qualification and projection checks still execute. They report any unscored candidates from altered auxiliary calls rather than pretending that call topology is fixed.

Holdout20 was authored and hashed before H1 scores were evaluated. It is opened for comparative scoring only if a single candidate clears the preregistered selection criterion. Artificial full-document reproduction questions are budget stress controls. The holdout contains upstream RST sources, preserved verbatim with licenses; format limitations must not be hidden by rewriting them.

## Verification

```bash
$PYTHON -m pytest -q experiments/grounded-partial/semantic-selection/test_evaluate.py
```

Tests check union coverage, omission of exceptions, source and occurrence isolation, scorer truncation and rejection of fabricated spans. This is experimental measurement validation, not a new full production CI claim.

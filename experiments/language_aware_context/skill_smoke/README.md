# Evidence-completeness skill smoke test

Four newly authored questions were run through the real lexical handler on
`637c91e7edb142d4bc490f0718ef32cd537c22cf`, with Python 3.12.3, frozen `uv.lock`,
`PYTHONHASHSEED=0`, 800 DTO tokens, three sources and two sections/source.
Python 3.13.0 documentation is pinned to CPython commit
`60403a5409ff2c3f3b07dd2ca91a7a3e096839c7`. Raw RST bytes are indexed under `.md`
fixture paths, without rendering or conversion; this is an ingestion limitation.

The questions, queries, rubric, source hashes and local skill were frozen before
the first handler call. Plans and actual answers were authored by GPT-6 Astra in
the same interactive session as the review. This is not an independent judge,
a pinned model API evaluation, a skill-on/off experiment or a profile A/B test.
The four questions are now viewed development examples, not a reusable holdout.

## Original run

| Task | Final packet | Actual saved answer | DTO tokens |
|---|---|---|---:|
| `fresh-01`: absolute vs resolve, `..` and symlinks | sufficient | both sides supported, S1/S2 | 798 |
| `fresh-02`: wait_for cancellation and total timeout | sufficient | cancellation plus explicit logical implication, S1 | 797 |
| `fresh-03`: shielded task vs cancelled caller | partial | generic cancellation only, S2; missing shield behavior named | 791 |
| `fresh-04`: universal numeric cancellation latency | insufficient | abstention; no invented number or universal negative | 798 |

Two of three substantive questions have complete evidence and complete answers.
The other answer is explicitly partial. The unsupported-number control receives
one correct abstention, not a fourth complete answer. All three cited answers use
present blocks supporting their claims; no unsupported additions were found by
the same-author review. Do not turn these self-assessments into independent
model-quality scores. All four handler audits passed; answer/edit flags stayed
false. No query or rubric was edited after execution.

For `fresh-02`, the visible version note says wait_for waits for cancellation
after timeout. The rubric permits the inference that total time can exceed the
timeout; requiring a verbatim phrase after seeing the packet would move the goal
posts. Full source inspection after saving answers confirmed the inference.
For `fresh-03`, no candidate-level first-loss diagnosis is claimed.

## Evidence and provenance

The committed `protocol.json`, `freeze.json`, four `*-packet.json` files and
`answers.json` are byte-for-byte copies of the original run, not reconstructed
outputs. `original_run.py.txt` and `original_skill.md` preserve the actual local
runner and skill whose hashes occur in that freeze. Absolute paths in the freeze
are historical provenance, not portable execution instructions. The repository
skill now uses concise, semantically phrased guidance rather than treating a
single contested example as a universal grading rule.

- Original freeze SHA-256:
  `98c0dec0ce81032a1ac39e6f9d53fa710646b333111ec7c076999908dc88bd25`.
- Saved answers SHA-256:
  `2b6ec0a0af22508ac7ac0e79a1b61851ba86271317ce9237eb05a73a747f18b0`.
- Original raw traces (~89 MB) remain in the audit workspace
  `/tmp/opencode/docmancer-fresh-test`; they are not included in Git. Do not claim
  that a later replay is those exact historical traces.

## Portable replay

```sh
uv sync --frozen --extra dev --python 3.12
DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 PYTHONHASHSEED=0 \
  .venv/bin/python -m experiments.language_aware_context.skill_smoke_run \
  --output /tmp/skill-smoke-new-run
```

Use a new output directory. The runner downloads the two pinned official source
files, verifies their original SHA-256, freezes current inputs, and retains all
raw handler objects/traces and final blocks. It does **not** run an answer model,
copy old answers into new results or automatically grade semantic sufficiency.
The language-flow workflow runs this replay and uploads its traces alongside the
paired regression evidence. A replay does not create new independent tasks.

## What remains before activation

Freeze a genuinely new dataset and rubric with an independent reviewer; compare
skill-on/off or planner A/B/E under controlled conditions, retaining actual model
messages and answers. Locate losses with raw objects before blaming packing.
No MPNet/BGE, profile delivery or ordering hook is activated by this smoke test.

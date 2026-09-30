# Language-aware context experiment — draft

Base: `main` at `58c7f37c2a5ef686bcd6562abbade91ba94e347a`.
Branch: `experiment/language-aware-context`.

This is a separate, additive experiment. It does not merge or cherry-pick
`task-44-cross-lingual-retrieval`, activate retrieval changes, change the MCP
surface, or modify P0/v3. No MPNet/BGE inference is introduced.

## What exists

- [PLAN.md](PLAN.md): staged T0–T9 implementation and acceptance plan.
- [EXECUTOR_PROMPT.md](EXECUTOR_PROMPT.md): instructions for a coding agent.
- `reference_core.py`: pure, deliberately limited design helpers for clean
  prose hints, scope binding, literal preservation and adjacent-window proposals.
  It does not parse Markdown, run source-policy, qualify evidence or retrieve.
- `baseline_probe.py`: opt-in invocation of the real main-branch fixture handler.
  It indexes only explicitly listed, hash-checked Markdown source files.
- Two registered test modules: 37 reference cases and 20 probe input/output cases.
- `protocol.proposed.json`: proposed budgets/arms, NOT a frozen dataset/protocol.
- `STATUS.json`: measured unit results and unmeasured integration/live work.

Historical simulated 11/11 and Grounded-like 6/7 are NOT evidence for this PR.
A must include the agent's existing `lookup_queries`, not a weaker no-lookup
baseline. A/C reuse identical saved queries; B/D reuse identical saved queries.
E checks whether a generic RU/EN instruction suffices without a profile.

## Run unit tests from a full checkout

```bash
DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 .venv/bin/python -m pytest \
  tests/docs/test_language_aware_context_reference.py \
  tests/docs/test_language_aware_context_probe.py -q
```

## Run a real DEVELOPMENT baseline

Prepare a sources-only directory, a manifest outside it, and a request file.
Compute hashes from actual file bytes; do not copy hashes from this example.

```json
{"schema_version":1,"sources":[{"path":"docs/guide.md","sha256":"ACTUAL_SHA256"}]}
```

```json
{"question":"How does cancellation affect retries?","lookup_queries":["cancellation retry behavior"]}
```

```bash
DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 \
.venv/bin/python -m experiments.language_aware_context.baseline_probe \
  --corpus-dir /ABS/sources --source-manifest /ABS/source-manifest.json \
  --request /ABS/request.json \
  --output experiments/language_aware_context/review_runs/baseline-UNIQUE.json
```

Existing reports cannot be overwritten. Import failure writes `BLOCKED_IMPORT`
and exits 2, never a retrieval miss or PASS. `EXECUTED` means handler plus packet
audit ran; it does not mean relevant/complete evidence or a correct agent answer.
Supplied lookups are marked unverified, never silently classified as live agent
output. Copied library docs are project fixtures, not a library-resolver test.

## Current boundary

Local checks used the staged experiment files, not a full installed checkout.
Direct network DNS was unavailable and runtime dependencies were incomplete.
The actual handler, A–E runs, independent data and blind answer judging remain
blocked/not run. No provider response has been fabricated. Do not mark the PR
ready based on unit counts. Keep raw runs, credentials and source corpora local.

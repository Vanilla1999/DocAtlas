# Native evidence sufficiency experiment

This experiment extends the native delivery candidate in PR #230 at
`40cfc413f8060b3d16fe962f6f9fe26bdfd27114`. It adds three opt-in selection
policies, compares them through the installed public MCP and pinned OpenCode,
and records source-witness failures as well as token cost. The default remains
`guarded-cover-v2`. None of these policies certifies semantic sufficiency or
corpus-wide absence.

## Question being tested

The v2 selector can omit an already acquired condition when that condition adds
only one query term. For example, an explicit environment can be the only new
feature in a prohibition. It can also omit a relevant restriction because the
restriction repeats already-covered terms in a different section. Returning
`not` and `no` to a stop-word vocabulary alone does not solve either problem.

This experiment asks whether additive recovery improves independently required
source coverage at an acceptable first-page cost. It does not assume that an
extra QA model is necessary. Existing extractive-QA results are documented in
[semantic-sufficiency-results.md](semantic-sufficiency-results.md); those
results do not justify automatic semantic enforcement.

## Frozen alternatives

| Policy | Behavior |
|---|---|
| `preserve` | Existing page-filling control |
| `guarded-cover-v2` | Unchanged current native selector |
| `guarded-obligation-v1` | Start with v2; append complete acquired owners that supply any still-uncovered, available literal query feature, including a single feature |
| `guarded-constraint-v1` | Start with v2; append acquired owners with restriction language linked by a shared technical identifier or at least two query-topic features |
| `guarded-combined-v1` | Apply both additive recoveries |

Here, "obligation" names the experimental policy. Its implementation covers
lexical query features, not inferred semantic obligations. Constraint words and
topic overlap are fallible relevance signals. They may miss paraphrases or add
irrelevant restrictions; the measurements must expose these outcomes.

All alternatives operate on the same authorized pre-native source pool. This is
the legacy public packet after upstream acquisition/admission/projection, not a
trace of every document considered by retrieval. These policies cannot recover
a source absent from that packet. Sources are not paraphrased,
deleted, fetched from a new scope, or promoted to instructions. Exact original
owner identity is retained. Empty v2 selections do not trigger indiscriminate
restriction scans. A full-pool conservative fallback stays intact.

The v2 selected prefix keeps its order and priority; rescued owners are appended.
That reduces displacement risk, but it does not prove first-page non-regression:
framing consumes tokens and the unchanged 3,000-token transport limit can still
cut off additional evidence. Actual delivered spans are therefore the oracle
boundary. An applied MiniLM selector continues to use the existing separate
`preserve-minilm` path; this experiment exercises installation without MiniLM
assets, with context compression off.

The selector was frozen before the implementing agent viewed new question gold:

```text
docmancer/mcp/evidence_selection.py
sha256: 81c0e094fb5377923bee595562846f0ef6aa576a23fb6d3708c3d06cc36b4abb
```

## Evaluation contract

The original V40 corpus, questions and gold remain byte-for-byte unchanged. A
separately authored challenge corpus adds genuinely distributed requirements,
conditions, exceptions, distractors, version distinctions, partial questions
and unsupported questions. It is a synthetic challenge set, not a population
estimate or evidence of general performance on arbitrary repositories.

Each corpus is indexed as one mixed project using real SQLite and public
preparation. Each policy is exercised through an installed, non-editable wheel,
public stdio MCP and the actual OpenCode 2.1.2 normalizer and ToolOutput. The
upstream client commit is `a517687fde98a7329ada3ae644a01a9fc6c4e99e`.

Gold bytes are hashed before inference but expected claims are opened only
after delivery. The evaluator checks original file spans independently of the
selector. Multiple claims and multiple source parts must all survive to pass a
documented case. Unsupported claims are listed but never counted as successful
unknown answers merely because their witness lists are empty.

The scorecard distinguishes:

- Required evidence missing before native selection (the precise upstream
  retrieval/admission/projection cause is not isolated by this boundary).
- Required evidence in that pool but absent from the first delivered page
  (selection and the page budget are not conflated with retrieval).
- Newly lost claims versus preserve and v2.
- Complete documented cases and individually delivered source claims.
- Complete first-reply `o200k_base` tokens after OpenCode, source counts and
  recorded request latency. Latency is one sequential observation with cold/warm
  ordering effects, not a controlled performance estimate.

Source text, coordinates, hash and scope/version provenance are checked. Full
signed pagination and rejection of forged, changed-question, changed-scope and
changed-source continuations remain integration controls. Source files and
SQLite logical state must be unchanged after execution.

## How to interpret the results

Infrastructure PASS means source/delivery/state invariants passed. Candidate
source-witness PASS/FAIL is reported separately and failed cases remain in the
scorecard. No policy is promoted automatically because the workflow is green.

A candidate is useful only if it recovers required evidence without losing
previously delivered requirements, and its context cost is acceptable. The
comparison keeps all candidate failures, including failures on the fresh corpus.
Product changes must not be tuned on that corpus after the first execution.

This environment has no configured answering-model provider. Consequently
`answer_model_calls=0`, `provider_usage=null`, final-answer quality and correct
unknowns remain NOT_TESTED. Source-span coverage is not an LLM correctness
score. Token counts are complete first MCP replies, not billed GPT tokens or
full-dialogue savings. A separate authenticated end-to-end run is needed for
that claim.

## Reproduction

The dedicated workflow is
`.github/workflows/native-sufficiency.yml`. It freezes original V40 inputs and
dependencies, builds the exact wheel, installs the pinned client, and runs:

```bash
python -I eval/native_sufficiency_integration.py \
  --repo /path/to/DocAtlas \
  --work /path/to/fresh-work \
  --out /path/to/fresh-results \
  --opencode /path/to/pinned-opencode
```

Use the isolated wheel environment's Python with Bun on PATH. Work/results paths
must be fresh. Detailed outputs include `PRODUCT_CHECKPOINT.json`, raw replies,
per-policy metrics, actual `OPENCODE.json`, `SUMMARY.json` and `SCORECARD.md`.
The checkpoint verifies that the installed selector and delivery source bytes
match the tested checkout. The workflow uploads all evidence, including failed
candidate results and infrastructure failures.

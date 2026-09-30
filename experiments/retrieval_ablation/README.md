# Retrieval ablation: T00–T04 diagnostic slice

This opt-in experiment does **not** change product retrieval, defaults, the MCP
schema, `uv.lock`, P0/frozen-v3 protocols, or MPNet's threshold. Initial base:
`55637eb4d29a0d06c01714ee647a5b486a5be725` (PR #204 already merged).

## What actually runs

**P** calls the existing `language_aware_context.baseline_probe.run`, including
its real handler, canonical audit, renderer and 800-token estimator. A same-call
SQL observer records individual native FTS lists before custom reranking, without
another retrieval. P keeps its actual product caps; it is not resource-matched to
A. SQL limits still exist: a saturated lane is explicitly incomplete for uncapped
recall. No precise first-loss diagnosis is inferred from a short trace.

**A** is currently **`native_fts_diagnostic_only`**, not a public context packet.
It calls the real `SQLiteStore._search_rows` query frontend and filter compiler,
active-generation joins, column weights `(6, 2, 0.5)`, and native ascending BM25
ordering. Individual AND/OR lists are saved with actual SQL/parameters. The
frozen merge is probe order, AND before OR, first stable identity; scores from
different expressions are never combined. Total raw exposure is divided across
probes (40 by default), AND consumes its share before OR, duplicates consume
budget, unused shares are not reassigned, and at most 20 unique candidates remain.
This is BM25 **within each SQL list**, not one global BM25 ordering.

Before bounded exposure, A scans the active project-document index, calls actual
metadata/source/lifecycle/risk policy functions, and verifies source snapshot and
mechanical quote ranges/hashes. The scan's rows/bytes are accounted separately;
it is not free and this is not a production performance claim. Reads share one
transaction. No `_ranking_candidate`, `final_utility`, expansion or projector is
used. Canonical checks here are mechanical; they do not certify API ownership.

A returns `packet_status=BLOCKED_SAFE_PACKET_ADAPTER`, `model_visible_packet=null`,
`quality_status=UNJUDGED`, and no answer/edit authority. Its internal source text
must **not** be given to an answerer. A complete shared public packet adapter,
reference/owner qualification, final combined-window checks and source/version
coverage across library scopes remain pending. Do not label T02 or the public
packet part of T04 complete.

## Rule map and reuse

| Class | Actual boundary | Treatment |
|---|---|---|
| HARD_SOURCE | `query_planning.metadata_matches_filters`, store filter compiler, `evidence_policy_rejection_reason`, `lifecycle_allows` | Retained; active generation, explicit project identity and frozen source membership required. Version filter is enforced when supplied. CLI pilot is project Markdown only. |
| CANONICAL_INTEGRITY | `generation_sources`, child display/retrieval hashes and byte/character/line spans; P's `audit_payload` | A performs mechanical checks before exposure and after materialization; P uses the real final audit. API/reference binding is not certified by A. |
| AUTHORIZATION | Real handler/projector's final support contract | Unchanged in P. A cannot create a packet or grant authority. |
| SOFT_RELEVANCE | `qualify_evidence` and reference preparation | Not disabled wholesale. E_G not implemented. A's packet adapter remains blocked. |
| ORDERING | Store `_ranking_candidate`, `project_doc_ranking`, projector candidate preferences | P unchanged; A bypasses custom ranking entirely. E_GR not implemented. |
| REPRESENTATION | Existing structured Markdown ingestion and contextual indexing | Unchanged. B/D and HTML/RST conversion are not implemented. |

## Reproduce

Use a full checkout and the unchanged lock, Python 3.12 for the CI comparison:

```sh
uv sync --frozen --extra dev --python 3.12
export DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 PYTHONHASHSEED=0
.venv/bin/python -m pytest tests/docs/test_retrieval_ablation_contract.py \
  tests/docs/test_retrieval_ablation_integration.py -q
.venv/bin/python -m experiments.retrieval_ablation.run freeze \
  --corpus-dir /absolute/public-corpus --source-manifest /absolute/sources.json \
  --request /absolute/request.json --output /absolute/new-freeze
.venv/bin/python -m experiments.retrieval_ablation.run run \
  --frozen /absolute/new-freeze --arm P --output /absolute/new-run-P
.venv/bin/python -m experiments.retrieval_ablation.run run \
  --frozen /absolute/new-freeze --arm A --output /absolute/new-run-A
.venv/bin/python -m experiments.retrieval_ablation.review \
  /absolute/new-run-P/result.json /absolute/new-run-A/result.json
```

The source manifest is `{"schema_version":1,"sources":[{"path":"docs/example.md",
"sha256":"<64 lowercase hex characters>"}]}`. Only explicitly listed `.md` bytes
are staged. Request accepts only `question` and optional `lookup_queries`; the
original text/literals are unchanged. Original-only and frozen-lookup panels are
separate. No filename extension tricks for RST are supported.

Freeze records exact sources/request/protocol, checkout bytes/diff/SHA, installed
package inventory, Python/SQLite/platform and lock hash. Outputs are new directories
outside the checkout. Symlinks, traversal, changed inputs/runtime, overwrite and
unmeasured quality claims are rejected. `protocol.json` remains an UNFROZEN
proposal until copied by `freeze`. Changing code requires a **new** freeze/run.

CLI should run in a separate offline process, never in a concurrent MCP server.
`DOCATLAS_OFFLINE` is a runtime policy, not an OS network sandbox. Manifest staging
and input allowlists prevent accidental label ingestion, but **OS-enforced gold
isolation is not implemented**. Existing P audit imports evaluation helpers; do
not call this an independent blinded holdout. Freeze is a reproducibility check,
not a cryptographic signature against someone rewriting all digests.

## Evidence boundaries

Tests use real SQLiteStore/FTS5 and real policy functions on synthetic documents.
They verify mechanisms, **not retrieval quality**. The two public-handler tests
need the complete locked dependencies; import errors are blockers, not TDD RED.
The diagnostic label shard extends the existing inventory without bypassing
`tests/conftest.py`. The CI retains failing JUnit/logs, frozen inputs and raw
outputs outside Git. Reports must distinguish executed diagnostics from packet
readiness and from semantic evaluation (not run).

T05–T12, dense/hybrid, independent evaluation data, actual answer generations,
non-inferiority and a product simplification decision are **not implemented**.

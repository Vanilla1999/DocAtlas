# A — acquisition method fixed before runtime

Base: `91dd2b4e9f0615e9c6ac5c4346c13200accca550`. Worker A runs no
product, test, benchmark, model or indexing calls. This document fixes the single
Q implementation before any new output; no rank-22/70/73-derived tuning.

## Chosen operation and fixed resource bounds

Q uses SQLite FTS5's built-in BM25, default equal column weights (1, 1, 1),
literal original-query word tokens joined with OR, and ascending BM25 cost.
Ties use source, chunk index and stable child identity. No AND lane, fusion,
reranker, rewrite, synonym expansion or score-based authority policy.

One retrieval lane fetches at most **256 indexed native children**, retains at
most **131072 stored estimated tokens** (256 × the existing default chunk hard
maximum 512), and at most **1048576 UTF-8 display-text bytes** (1 MiB).
These are engineering work ceilings, not paper parameters or completeness claims.
256 is a fixed power-of-two bounded batch; 1 MiB bounds admitted text storage.
An oversized child is skipped, including the first child; the scan never fetches
another batch to compensate. SQL LIMIT bounds materialized rows, not FTS engine
postings work, metadata bytes, raw-source accounting or end-to-end latency/RSS.
The runner must retain its independent call/wall ceilings.

Final request `limit`/`budget` do not reduce Q's acquisition pool. Downstream
selection/assembly/final public serialization remain responsible for their final
context budget. Two service root lanes can each acquire this batch; no promise of
256 total per public context. SQL/project/version filters can restrict membership
before the batch; dispatcher policy verification can reduce it afterwards.

## Removed on candidate path / retained off path

- Remove title-term ×1.5 and leading-phrase +2 boosts, >600-token length penalty,
  generated/mirror/stale −3 and external-generic −1.5 score penalties.
- Remove weighted BM25 (6, 2, .5), AND-first/conditional OR union, 4× scoring
  reserve and final-limit-derived acquisition count/token ceilings.
- Remove cross-source title+text dedupe: only identical section ID is deduped.
- Bypass dispatcher top-limit truncation, source diversity quota and its
  same-parent overflow. These are selection proxies, not access policies.
- Fetch native children only: adjacent/page expansion is bypassed in Q, even
  when configured. This deliberately leaves representation to downstream C;
  standalone retrieval callers must not expect expansion in this experiment.
- Existing old methods remain exclusively for baseline/default parity. Q does
  not call manual `_ranking_candidate`, diversity or fallback methods.

Retain immutable active-generation membership, metadata SQL filters and dispatcher
`metadata_matches_filters` checks, source IDs, original text/hash/span metadata,
and downstream source validity/freshness/access/authority checks unchanged.
Removing score penalties does not authorize stale or foreign sources. The raw
index includes title, metadata-prefixed retrieval text and source path; this is
not body-only BM25 and does not rebuild the index. Duplicate field text and FTS5
corpus statistics remain deviations from a fresh single-field reference baseline.
BEIR motivates BM25 as a lexical baseline, not these batch sizes or equal-field
schema. This is not Anthropic contextual retrieval, RAPTOR or a reranker.

## Interface / observable stages

Only `DOCATLAS_EXPERIMENT_HEURISTIC_REMOVAL=Q|ALL` activates Q, through the
coordinator-owned `heuristic_removal_active('Q')` in
`docmancer.docs.application.experimental_heuristic_removal`. A/S/unset/invalid
values must not activate Q. No additional environment controls or public wire
arguments are added. Q dispatcher accepts lexical only; non-lexical modes raise
`ValueError` rather than provide a misleading partial Q/hybrid arm.

Store ranking metadata identifies `fts5_bm25_equal_fields_or_v1`, zero feature
contributions and equal raw/final rank. `acquisition` metadata exposes SQL row
count, fixed ceilings, admitted counts/tokens/bytes, skipped resource rows and
ignored final request limits. Dispatcher trace retains backend ranking and adds
post-policy count. No logs, extra searches or trace-dependent selection.

## Risks and verification boundary

OR lexical retrieval can admit irrelevant sources and increase downstream work;
removing authority penalties may alter ordering of otherwise policy-valid sources.
Finite batch and greedy resource admission can still lose witnesses. BM25 rank
and negative BM25 score are not probabilities, evidence sufficiency or answer
authority. Existing source-valid/admission and selection rules in other arms may
still reorder/drop rows; Q alone does not remove them. Default parity, public
source integrity, scope/version denial, final budget and tracing parity are for
the coordinator's public integration execution. No runtime PASS claimed here.

## Implementation handoff (static only)

Changed files:
- `docmancer/core/_sqlite_store_part03.py`: early Q query path, bounded native
  acquisition, single equal-weight OR SQL query and unmodified baseline branch.
- `docmancer/retrieval/_dispatch_part01.py`: early lexical Q lane after existing
  query-plan/filter construction, mandatory post-policy verification, no quota
  truncation, method-specific configuration hash. A/S do not enter this branch.
- `docmancer/retrieval/experimental_acquisition.py`: fixed constants and lazy
  delegation to the coordinator's single flag helper.
- This report; no other worker-owned files changed by A.

The returned Q `score` is `-bm25_cost` rather than baseline's synthetic linear
rank score (`max(0, 1 - .05 × index)`); it is higher-is-better, not calibrated.
Ranking trace retains the existing field shape and explicitly supplies score
direction. The fixed acquisition metadata is carried on each retained chunk;
an empty batch has no per-chunk receipt. `DispatchResult.candidate_counts`
reports acquired rows before post-policy filtering; chunk metadata reports the
post-policy count. SQL full-universe size and filtered-out source text are not
exposed, and no extra observation scans are executed.

Baseline inventory: store scoring reserve 4×limit; two weighted SQL lanes each
limited to that reserve; store greedy estimated-token packing with first-row
overflow exception and title+text dedupe; dispatcher normalized limit at most40,
reserve usually3×limit (or limit+6), then request-limit truncation or configured
source quota/structural overflow. Hybrid remains the original per-lane40/fused60
pipeline **outside Q**, with hydration budget and vector policies unchanged.
All these baseline semantic/resource combinations are bypassed by Q, not moved
into a newly named scoring function. A does not edit the service's downstream
final request-budget interface.

Static checks: edited/new Python files parse with `ast.parse`; `git diff --check`
reported no whitespace errors. No modules imported, tests or product workloads
run, commits/pushes performed. Runtime parity and final result quality remain
unmeasured. The coordinator's flag-helper file is present and was read, not edited.

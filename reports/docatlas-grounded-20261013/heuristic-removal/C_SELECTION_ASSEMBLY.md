# C — native acquisition-rank selection / assembly

## Before-runtime contract (2026-10-13)

No product/test/model workload is authorized to this worker. Default remains unchanged;
no promotion, commit, benchmark-specific tuning, or holdout inspection.

Chosen baseline: the actual original acquisition sequence, followed stably by the
existing authority read and existing supplemental lanes; checked native source-bound
windows, exact occurrence dedupe, and whole-row greedy packing under the existing
host-captured final JSON cap. No relevance scorer, top-two quota, predicted owner
grouping, parent/neighbor/semantic rescue, similarity penalty, or arbitrary crop.
Acquisition is still finite and independently bounded; S must not change SQL or
dispatcher acquisition limits, token budgets, expansion requests, or lookup schedule.
Q changes only those bounds/ranking in its own arm. A changes admission independently.

Final budget: coordinator freezes `DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS=12000`
for all comparison arms before runtime, using existing captured scope and
`max(o200k_base(JSON), ceil(UTF8(JSON bytes)/4))` accounting. This is an engineering
resource ceiling, not a paper-derived optimum or a semantic completeness threshold.
S requires an explicit captured cap; it ignores Budget/Mini/callback membership
selectors. Whole rows are visited in order; an oversized row is omitted and later
rows may fit. No alternative parent/native rescue is searched during packing.

Membership is admission plus exact dedupe plus final fit, never qualification-first.
Representation is the whole native acquired body, not predicted parent expansion.
Removing parent expansion can lose facts available only in an unacquired parent;
removing top-two can deliver more irrelevant text. Overlapping or contained but
different spans are not duplicates. Equal words elsewhere are not duplicates.

Negative contract remains separate: old `sources=[]` expectations are NOT redefined
as PASS for nonempty legitimate retrieval. No source-valid or qualified label proves
question sufficiency. Failed qualification is not changed to true; answer/edit
authority remains false. Source/request/member/scope/version/freshness/hash/span and
same-call discovery checks are mandatory, including terminal late recheck.

## Shared interfaces / coordination requests

- Coordinator supplies `application.experimental_heuristic_removal.heuristic_removal_active(stage)`.
- C supplies `experimental_candidate_selection.native_rank_selection_active()`:
  S/ALL AND the existing live original project-read scope (captured selector
  settings present, even when all three settings are None). No old admission env
  is needed for ALL. Explicit lookup/module/library/ineligible calls do not enable S.
- B/coordinator must make `literal_context_admission.recheck_source_valid_candidate`
  source-only for A/ALL, retaining real source/request restrictions. C preserves
  calls; S alone deliberately retains baseline admission. No overlapping domain edits.
- Coordinator must dispatch the C native projector before the legacy core projection
  and bypass unowned query-block/recovery finalizers on S/ALL. Those files are not C-owned.

## Implemented diff / current integration handoff

- `_project_docs_service_part03.py`: S bypasses lane-fairness traversal,
  qualification/condition-first sorting, post-admission count/estimated-token quota,
  score-based duplicate preference and retention rescue. Original read is first,
  existing authority read second, existing supplemental lanes last. All existing
  acquisition parameters/calls remain untouched by S.
- `experimental_candidate_selection.py`: S checks current native discovery and
  already checked original admission, dedupes by that exact source/member/scope/
  snapshot/window binding, and returns every remaining native candidate in order.
  It bypasses all callback/Budget/Mini selectors, including top-two and model loading.
  The receipt reports `mode=native_acquisition_rank`, `top_k=None`, zero forwards.
  Legacy selector modes remain only for default/control; no new selector mode.
- `_docs_context_projection_core.py` (ownership extension granted by coordinator):
  S dispatches directly to `project_native_rank_context` before legacy facet
  ranking/cropping/variant expansion. A/ALL candidates go directly to B admission
  before strict-attribute/component gates, including when another non-original
  direction qualified. A-only otherwise retains its selection/assembly arm.
- `experimental_context_finalization.py`: native projector preserves operational
  refusal, request-input/exact-snapshot guards, renderer identity restrictions,
  full native body and freshly checked line spans; uses lexical requalification
  only for attribution, no membership gate. Snapshot schema is bound to the actual
  public rows. Source checks run before rendering and after finalization. A/ALL
  activates capture/recheck without the old source-valid mode. Public
  `context_unassessed=True` / `admission_contract=source_only_heuristic_removal_v1`
  survive rebuild/terminal budget, with conservative unverified quality and no
  synthesized credit. S terminal budget performs exact checked occurrence dedupe
  and never tries smaller native/parent alternatives; failed rechecks cannot
  resurrect seed-based containing/supplementary or restore-native rescues.
- `experimental_prepared_parent_assembler.py`, `joint_context_selection.py`:
  S entrypoints return the untouched native packet; Cartesian structural drafts,
  preferred section/atom closure, ancestor introductions, subset coalescing and
  rank-by-closure/cost are not executed. Parent alternatives are not predicted.
- `experimental_selection_modes.py`, `joint_context_candidates.py`,
  `joint_context_lineage.py`: unchanged control helpers, not S selectors.

### Remaining coordinator-owned integration boundaries

`docs_context_projection.py:263–268` still invokes query-block/recovery after core;
C requested ownership to return after decoration and terminal recheck for S.
`_project_context_service_part01.py:159/166` reranks before context projection;
coordinator must preserve C native acquisition sequence for S. The native projector
does not score-sort its received pack. `_project_context_service_shared.py:149–152`
drops placeholder/low-value text before the pack; source-only/native contract needs
a coordinator audit/bypass of semantic low-value filtering while preserving actual
source policy. These are visible blockers, not claims that the whole path is done.

Q interface communicated by coordinator: fixed acquisition 256 candidates,
131072 estimated tokens, 1MiB source work bound, equal-weight native BM25 OR,
no expansion. These are independent acquisition controls; C does not copy them
into the final JSON cap or alter Q from S. Environment must remain fixed throughout
each whole synchronous public call; variant mutation during a call is unsupported.

## Public verification spec (runner-owned)

Through real public prepare/context/source with real index and storage: verify full
native bytes and canonical spans/hashes, scope/version/source membership, stale-to-sync,
foreign locator refusal, false authority, state unchanged, trace on/off parity.
Verify multiple seeds of one owner survive as distinct native occurrences; no parent
failure may discard their alternatives. Same text at different offsets/documents or
versions must not dedupe. Tight final JSON ceiling must either hold after resource
registration or refuse explicitly. Compare V0/Q/A/S/ALL and disclose final facts lost,
including prior P03 and parent-only E01 risks, without altering question/oracle.

## Remaining policies and evidence boundaries

Existing finite acquisition, same-call provenance, explicit operational refusals,
request-input limits, exact snapshot requirement, renderer path/title/version length
limits, source policy and terminal validation remain engineering constraints.
Greedy rank-order packing is a transparent baseline, not SetR, RAPTOR, contextual
retrieval, optimal set selection, or proof that top-k is sufficient. Actual gains,
losses, cost, public validation and readiness are NOT MEASURED by this worker.

## Static receipt (not runtime verification)

`git diff --check` on owned changed files: clean. `python` executable unavailable
(exit127); switched once to `python3`, using stdlib AST/hash reads only, no product
imports. AST parsing succeeds for all six changed Python files. Current diff is
216 additions / 11 removals across six files, before pending wrapper integration.
Default legacy code remains solely for the control/off path; removed rules are
bypassed entirely in S. No prior RAS patch was applied.

| Application file | SHA256 at this handoff |
|---|---|
| `_project_docs_service_part03.py` | `a01b02b5e2be9346bb795243764a8147545e7bc6a0e9d167f1cf1158c4f78241` |
| `experimental_candidate_selection.py` | `2480c2226f49deb82ec5f8686ffc890ea55c6dfa460ad6c99ceaf4869a6b1790` |
| `experimental_prepared_parent_assembler.py` | `87e575b41b02123af305f3fba00cbac93cdebff2a0e3a1093e4ce07b93742cb2` |
| `experimental_context_finalization.py` | `013dd6be5dfec9e49ffec66ecbb1f8d514b9559608a474b474bb29b75efdb347` |
| `joint_context_selection.py` | `97109f961ef45f1d42d01a81c879325012e172775df6031baf58bbcae8e3ed30` |
| `_docs_context_projection_core.py` | `ea1738ba6827b0fe0b2a47758788b94cb18d77cb459284b7e67959791b183efc` |

Added rendering/source checks and full-JSON trial accounting are bounded by the
finite acquired pool but not free/O(1); raw-document hashing and snapshot copies
can be expensive. No latency/RSS/token-utility claim is established. Public strict
negative-empty performance and parent-only witness loss remain explicit risks.

## Original-query / auxiliary-lane audit before freeze

The actual baseline already lacks generated search queries. Static inspection:

- `domain/documentation_query_plan.py:85–109` preserves the exact original
  `question` as `query-original`/`origin=original`/`relation=direct`; only the actual
  `lookup_queries[:5]` caller input adds `origin=host_lookup`/`relation=host_lookup`
  rows. Whitespace checks only reject empty lookups; query bytes are not rewritten.
  Requirements do not create aliases, probes, expected-answer injections or parent
  coverage. An explicit document path is scope metadata, not an executable query.
- `application/need_query_schedule.py:12–31` schedules those direct public host
  lookups only, capped at five; `requirement_search_probes()` returns `()` and
  `scheduled_plan()` does not add rows. No inferred `canonical_intent`,
  `concept_alias`, `lexical_topic`, `retrieval_hint`, `retrieval_need`, exact-anchor
  or audited-rewrite search is scheduled. Legacy origin-handling branches in the
  service do not create queries and are unreachable under this planner.
- The backend plan also has no executable concept rewrite:
  `retrieval/query_planning.py:121–122` returns `()` from `_concept_queries`;
  `build_query_plan:284–291` uses literal query syntax for exact constraints,
  retains the original query hash and requirements hash, and does not convert
  inferred requirement values to retrieval queries. This is inspection only;
  the acquisition worker's files were not edited by C.
- `_project_context_service_part01.py:73–81` passes the original question and
  explicit caller lookups to that same planner/scheduler. The owned service
  independently rebuilds the same explicit plan at its read boundary, rather than
  executing supplied/inferred internal plan rows. No outside-owned change is
  needed to suppress generated lookup derivation in the inspected actual baseline.
- `query_project_docs` makes **two root backend reads**: first `query` unchanged
  with the request's project/source/lifecycle/scope/module/path filters; second
  the identical `query` bytes with an additional `authority=source_of_truth` filter.
  This authority lane is a separately bounded filtered duplicate acquisition, not
  a rewrite, semantic rescue or a source permission grant. It can return a subset
  in its own acquisition order; it is not assumed to have the identical results.
  Both calls remain real work and must be counted. S visits the unfiltered root
  read first, then this lane, with exact source-occurrence dedupe; it assigns no
  extra authority, semantic score or priority to the filtered lane.
- With frozen original-project input `lookup_queries=()`, the supplemental loop
  performs **zero reads**. Explicit host lookups, when supplied in other requests,
  remain separate independent directions; their checked attribution is not
  original-query rewrite/parent credit. No generated lookup is rescued if empty.
- The authority lane retains its existing `effective_expand or "page"` argument.
  With frozen requirements present, default `effective_expand` is the truthy
  string `"none"`, so that fallback does not activate. Q/ALL backend additionally
  enforces the acquisition worker's no-expansion policy. S alone does not alter
  acquisition expansion requests or make Q's intervention inseparable from S.
- For an explicitly resolved document locator, `get_project_docs` may read stored
  exact-document sections and requalify using the original explicit plan. This
  is a document-scoped index read, not a new rewritten text query; it remains a
  separate observable acquisition boundary and is not claimed to run in every
  original-project request.

Removed unused imports for `build_project_retrieval_aliases`,
`apply_retrieval_need_witness`, `derived_parent_trace`, `qualify_evidence` and the
unused query-term/supplemental-usefulness helpers from the owned service. They had
no call sites in this shard; removing them does not change default acquisition or
duplicate the Q backend. No tuned threshold, rewrite parser, new model, extra
lookup or runtime experiment was added. No planner/scheduler/shared file was edited.

Previously recorded service hash/diff totals precede this dead-import cleanup;
the final service hash is recorded in the static addendum below. All other C source
hashes above remain this worker's prior handoff hashes, subject to coordinator edits.

Static addendum after the original-query audit: owned service/report
`git diff --check` clean; stdlib `python3` AST parse of the service succeeds.
Final service SHA256:
`30e0bbeb331e19d9b2e777b4b8398193b31fc426eb0bd20dbb27592311bcb69e`.
No runtime, product import, test, model call or holdout access occurred.

# Project context quality v2 design

Status: proposed implementation plan, not a completed protocol or release gate.
The first implementation slice fixes exact-term adaptation at the application
projection boundary. Corpus v2, component attribution, and new live measurements
are not implemented by this document.

## Corrected premises

- Preserve v1 corpus bytes, locks, and recorded reports, not a predetermined red
  result. Production fixes may legitimately improve future v1 replays.
- The natural original-coverage target is 12 of 15, which is mathematically
  feasible. No audited rewrites in today's natural query plans explains the
  observed zero but does not invalidate the requirement.
- The paraphrase dataset has five positives. Absolute minima above five cannot
  pass, but this lane is explicitly report-only in v1.
- Lookup arguments being optional does not invalidate lookup attribution tests.
  Separate retrieval provenance from semantic usefulness rather than removing
  whichever check currently fails.
- Post-hoc estimates such as natural 9/15 are hypotheses, not measured baselines.
  Do not reduce requested facts, accept tangential sources, or lower 13/15 useful
  results to 12/15 merely to obtain a green verdict.

## DDD boundaries

Use the existing Docs bounded context and existing modules. No new service,
bounded context, NLP subsystem, or public MCP schema is required for these steps.

| Owner | Responsibility | Must not own |
| --- | --- | --- |
| Domain `documentation_query_plan.py`, `query_terms.py` | Query identity, exact terms, explicit rewrite lineage | Corpus case IDs, gold phrases, storage calls |
| Domain `evidence_qualification.py` | Pure source eligibility and visible-match decisions | SQLite scores as authorization, network calls |
| Domain `project_doc_ranking.py` | Eligibility-aware relevance and diversity policy | Hidden gold facts or source allowlists from eval |
| Application `context_selection.py` | Allocate candidates and aggregate domain decisions for one request | Invent qualification or whole-question equivalence |
| Application `docs_context_projection.py` | Bounded visible excerpts, domain requalification, source identity | Independent lexical thresholds or answer authorization |
| Infrastructure SQLite / retrieval gateway | Bounded candidates, exact match facts, offsets and provenance | `qualified`, semantic completeness, edit readiness |
| Evaluation `eval/` and existing self-host runner | Versioned independent obligations and measurements | Supplying gold obligations to production selection |

Distinguish three concepts throughout: candidate relevance, retrieval-query
attribution, and semantic question completeness. A lexical ratio may establish
relevance; it must not silently become full-answer certification. Project reads
remain retrieval-only with `answer_supported=false` and `edit_ready=false`.

## Ordered slices

### 1. Correct typed exact-term adaptation

Convert `DocumentationExactTerm` values to `normalized_value` when composing a
projection probe. Test symbols, paths, flags and environment variables with the
identifier present and absent from the visible snippet. Hidden full-text matches
must not restore coverage. Keep qualification exclusively in the domain.

### 2. Capture stage-local loss

Extend only the existing evaluation observer to retain bounded same-call
candidate identities, pre-projection qualified IDs, considered snippet variants,
and rejection reasons. Do not repeat retrieval to reconstruct the snapshot or
add diagnostics to public MCP output. First distinguish no retrieval hit,
qualification rejection, ranking loss, and projection truncation per failed case.

### 3. Version the independent measurement contract

Add a separate v2 corpus and migration crosswalk with preserved original prompts,
mandatory obligations, reviewed alternate witnesses, authority/scope constraints,
source revision and evaluator version. Keep v1 default behavior intact.

Normalize formatting only in the evaluator's prose witnesses. Preserve code,
identifiers, negation and modality. Headings and link labels remain routing
context, not standalone factual witnesses. Do not introduce general inflection
or fuzzy equivalence to make gold facts match.

Keep hard safety/identity/citation/budget gates. Classify unlisted sources as
unadjudicated until reviewed; report safe-but-irrelevant sources as precision
loss, never as automatically useful evidence. Keep lookup attribution as a
separate contract metric even if semantic usefulness has its own verdict.

Validate each compound case has an adequate witness within three sources and
800 total output tokens. If it does not, explicitly review whether the expected
outcome is partial context; do not silently remove obligations. Build evaluator
positive and adversarial negative fixtures before freezing the new corpus.

Report rates with denominators and distinguish report-only from gating results.
Do not rescale v1 locks. New thresholds require an explicit rationale, baseline,
and freeze before production tuning; provisional numbers are not approved DoD.

### 4. Fix retrieval and selection from stage-local evidence

First regression-test exact-anchor requests with independent host queries:
presence of an anchor must not globally erase public diversity. Preserve the
explicit named-document scope restriction while testing this change.

Measure a bounded AND/OR candidate union separately from ranking changes. Keep
query budgets, safety filters and project/lifecycle scopes unchanged. Avoid
cross-language alias additions copied from frozen questions. Reuse existing
domain query normalization rather than a second NLP implementation.

Track novelty of internal canonical facets for question-only requests without
turning them into public original coverage. Add bounded same-parent/sibling
retrieval only where the observer proves required neighboring sections were
lost. Preserve contiguous excerpts and their own offsets/evidence IDs.

### 5. Audit original attribution without rebuilding the answer parser

Inspect and reuse existing question-frame and question-plan representations.
Do not introduce a parallel semantic model just to meet a coverage counter.
Any internal component mapping must preserve the full original span, subject,
exact identifiers, negation and unresolved residue. Arbitrary host lookups are
not audited translations.

Evaluate candidate relevance separately from component completeness. An audited
component rewrite cannot on its own cover a compound parent. Aggregate only
domain-approved witnesses from the final visible snapshot, with evidence IDs
per component. Missing or unresolved components block a full-completeness claim
but must not erase useful partial retrieval context.

Before changing existing `covered_query_ids` semantics, characterize its current
retrieval-attribution contract and consumers. Initially keep stronger semantic
completeness in internal/evaluation results; public contract changes are outside
this plan. The evaluator must independently reject invented lineage, a missing
component, and high lexical overlap that omits a requested operation.

### 6. Verify independently and report residual failures

Run diagnostic inventory validation, targeted regressions, offline/advanced
suites and compilation. Replay v1 and v2 separately; never merge denominators.
Freeze a new independent holdout because the existing paraphrases have already
been inspected during debugging. Record corpus-only rescoring separately from
fresh end-to-end retrieval results. Installed-agent runs remain cancelled per
the user's request.

## Acceptance invariants

- No thresholds or frozen v1 corpus bytes changed to fit output.
- No production dependency on evaluation data or case-specific aliases.
- No metadata-only factual qualification or false original-completeness claim.
- Missing verification in an install-and-verify request remains partial even
  when installation vocabulary has high lexical overlap.
- Architecture evidence alone cannot prove an architecture-and-testing answer.
- Exact path isolation, source trust and current/historical intent survive
  diversity and sibling-selection changes.
- Only final visible snippets can support evaluation facts or component proof.
- Three sources and 800 total output tokens remain hard limits.
- Green unit tests or a new evaluation version alone do not establish live DoD.

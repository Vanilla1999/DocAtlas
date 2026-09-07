# Project context quality v2

This independent, provider-free evaluator scores final visible retrieval
responses. The evaluator itself remains report-only so captured reports stay
claim-boundary neutral. Release/PR acceptance is now a separate wrapper,
`scripts/run_project_context_quality_v2_gate.py`, bound to
`acceptance.lock.json`; it cannot rewrite corpus results or turn evaluator
failures into passes.

V2 models each positive case as mandatory semantic obligations with stable
obligation IDs that are distinct from lookup-query IDs, plus reviewed
accepted active-catalog witnesses. Real public responses use `path_or_url` and
`estimated_tokens`; authority and scope are independently resolved from active
explicit documents and recursively discovered files under active catalog roots.
Root-derived identity remains separate from relevance adjudication. Explicit
authority/scope and legacy `path` are accepted only by fixtures marked
`fixture_kind: synthetic`.

The natural lane contains all 15 v1 positives, two strict fantastical negatives,
and two realistic unsupported-answer controls. The controls accept either
fail-closed `insufficient_evidence` or retrieval-only `docs_context` with
`answer_supported=false`, `answer_available=false`, and `edit_ready=false`.
Both accepted forms must also satisfy safety, source identity, budget, and no-
authorization gates. The five reused v1 positive paraphrases and their negative
control are the separate `EXPOSED_PARAPHRASES_REPORT_ONLY` lane. They are
exposed report-only cases, not an independent holdout or independent evidence.
Semantic usefulness, lookup attribution, source
precision, unadjudicated relevance, safety, budgets, strict-negative correctness,
unsupported-answer-control correctness, and root causes remain separate. Runtime
`query-original` and lookup claims are retrieval attribution only and never
count toward completeness. Semantic completeness is verified from final visible
witnesses bound to unique returned evidence IDs and exact sources. It is compared
only with an explicit internal `diagnostics.runtime_component_coverage` runtime claim
(`component_coverage` is also accepted for existing captured fixtures);
without that diagnostic, the runtime claim is `unavailable`, not false.
`false_full_coverage` records a valid runtime-full/evaluator-incomplete disagreement.
Runtime component IDs are checked against their own mandatory inventory, never
against the independent gold obligation IDs. The self-host observer retains
component-to-visible-source bindings, snippet hashes, and internal evidence IDs
from that same call; canonical assignments must belong to the bound source.
Independent gold witnesses still determine semantic usefulness, not these runtime
assignments. Missing runtime contracts remain unavailable, not verified complete.

All live cases, including strict negatives, retain their full payloads in
`production_results`. Safety and authorization controls inspect the public payload;
budget checks independently recompute its serialized token estimate. Internal
observer diagnostics are excluded from the public token budget and safety text.
Stage diagnostics retain explicit observed/unclassified status and call counts.
Rejection-based root-cause labels are stage observations, not proof of an
obligation-local cause; unrelated rejected candidates can coexist with useful hits.

`protocol.lock.json` freezes corpus inventory and hashes independently of v1.
Witness validation checks the active project-doc catalog and current document
bytes. `migration-crosswalk.json` explains every v1 expectation change.
`diagnostic.json` is an
adversarial evaluator shard and is not part of baseline denominators.

Run `python eval/project_context_quality_v2_protocol.py` for a no-response
contract report, add `--responses FILE` to score captured public payloads, or
add `--live` to exercise current production through the existing in-process
self-host infrastructure. The evaluator output remains report-only. Blocking
acceptance is `python scripts/run_project_context_quality_v2_gate.py`, which
requires all 15 natural and all 5 exposed positive cases to satisfy their
semantic obligations, all safety/budget/negative/control checks to pass, zero
false-full coverage, and frozen lookup-attribution non-regression floors.

The previous v1/Legacy live corpus is retained as an explicit compatibility
report. Its path-specific relevance verdict no longer decides release quality,
but `scripts/check_legacy_project_context_lineage.py` still enforces the frozen
`query-original >= 12/15` floor and the existing zero-tolerance safety/budget
metrics. This separates obsolete path adjudication from safeguards rather than
silently lowering or deleting them. Run
`pytest -q tests/test_project_context_quality_v2_protocol.py tests/test_project_context_quality_acceptance.py`.

## 2.4 evaluator audit

The original question, not host lookups, determines mandatory obligations.
The public-tool inventory question accepts the direct three-name sentence in
`docs/mcp-docs-server.md:53`; a count without names is insufficient, and roles
are not additionally mandatory. The broad evidence-selection question requires
a substantive selection rule, not four architectural details introduced by
lookups. Offline ingest accepts the explicit equivalent no-vector witness in
`wiki/Supported-Sources.md:44`; the separate offline-test obligation remains.
Exact source binding, heading-only rejection, budgets, and null thresholds are
unchanged. The crosswalk records documentary reasons and the lock records the
revised corpus plus the additional active witness document.

The staged local run captured three evaluator failures before these changes,
then 67 focused passes. Its corrected live baseline is 8/15 natural and 0/5
exposed paraphrases; the prior 6/15 must not be used to claim production gain.
The subsequent generic projection fix leaves those live usefulness counts
unchanged. Full measurements and remaining gaps are recorded separately in
`/tmp/opencode/staged-plan-report.md`; this is not a passing release gate.

# N26 first-loss experiment: isolated, not accepted for the product

Date: 2026-09-26. Parent experiment: a8a0ef4ff30e1102c3a099b6d4e766aeb71183a6.
Preserved branch: `experiment/tdd-anchor-cross-lane-20260926`.
Working PR: #198, `fix/tdd-public-contract-20260926`.

## Decision

Do NOT accept the exact-anchor cross-lane patch alone. Its unit contract passes,
but the actual 30-question replay loses a previously visible required fact for
N07 direct. N26 direct remains incomplete. Restore the working tree to b7c9744
(the pre-experiment state including the new observation scripts), plus this
record. Preserve the complete candidate implementation, unmodified RED/GREEN
tests, diagnostic inventory and workflow on the experiment branch and in Git
history. This is rejection of the whole experiment, not suppression of a failing
test while retaining its runtime change. No force-push, merge or release.

## Proven first loss

Two observer-only commits, 3c02a4b and b7c9744, record actual in-process public
handler inputs/returns and executed projector branches. Both compare stable
visible outputs against an uninstrumented call. These are not stdio or LLM tests.

For N26 direct, the raw original-question and authoritative pools retrieve the
`docs/index-cleanup.md` global/configuration section (lines 64-82) at rank one.
The original Russian question correctly remains unqualified against its English
body. Planned exact anchors `--scope` and `clear-index` exist, but their narrow
retrieval lanes do not rediscover this section. `_qualify_candidate_lookups`
excludes parent-bound exact anchors from its cross-lane checks. The global
section therefore carries no qualified query IDs and is removed by
`rerank_project_doc_chunks` before projection. This is not a missing document
or failed raw lexical recall.

## Candidate and real TDD

The only candidate runtime difference is six lines replacing two in
`_project_docs_service_part03.py::_qualify_candidate_lookups`: include planned
origin=exact_anchor, relation=exact_anchor in existing body/policy checks. No new
search calls, increased budgets, fabricated BM25 scores or parent-answer proof.

RED 49b1cf7, run 36260855813: 14 failed, 3 passed; 50 existing controls passed.
GREEN a8a0ef4, run 36261134119: unchanged 17 tests passed; 50 controls passed.
The tests check real qualification, stale/foreign/risky/heading-only negatives,
original-score/parent-trace preservation, and real service candidate admission.

Candidate trace run 36261134130 proves the first loss is repaired: the global
section acquires independently checked anchor traces and survives reranking.
But projector line 503 rejects it because the anchors are already covered and
there is no new component/query direction. The parsed component contract is
empty. Both anchor coverage and a correct source citation are insufficient to
prove that all requested facts are visible.

## End-to-end acceptance failed

Run 36261134148 executes the unchanged runner and question bytes through real
stdio MCP: 60 original-main calls and 60 candidate calls, both COMPLETE, zero
transport/tool errors. Compare the candidate against the previous post-routing
936acb2 capture from run 36252233921, not only against original main.

- N13 direct improves: the previously missing
  `DOCATLAS_MCP_TEXT_FALLBACK=1` instruction appears at README.md:138.
- N07 direct regresses: before, workflow.md:129-135 explicitly says a resolved
  module path implies module scope. The candidate returns workflow.md:81-93,
  an example that does not state precedence when scope=all and module_path are
  both supplied. It also retains a pre-existing invalid mode example.
- N26 direct has the same local-only snippet as 936acb2; the global preservation
  answer is still absent. Assisted retains the useful global passage.
- 12 direct and 14 assisted visible packets change. Availability increases from
  20/30 to 21/30 direct, while assisted stays 27/30. Availability is NOT accuracy.
- N01 adds an unrelated provider-configuration table; N24 direct gains context
  but still lacks the changed-manifest invalidation rule. Do not claim a net
  general quality improvement from this experiment.

Full locked core comparison, run 36261134159 (candidate a8a0ef4, not restored
HEAD): original main 4585 passed / 21 failed / 10 skipped; candidate 4851 passed /
22 failed / 10 skipped. Dependency freeze files match. The additional failing
node is the already-known guidance regression, not a new failure from this
experiment. The N07 content regression is outside those core assertions.

## Receipts

- Before projection observation: run 36260311653, artifact 10912515241.
- Before upstream observation: run 36260504014, artifact 10911928559.
- RED: run 36260855813, artifact 10912136505.
- Candidate GREEN: run 36261134119, artifact 10912620967.
- Candidate upstream observation: run 36261134130, artifact 10912955119.
- Candidate capture: run 36261134148, artifact 10912995262.
- Same-run original capture: artifact 10912810869.
- Candidate full core: run 36261134159, artifact 10912196711.
- Same-run original full core: artifact 10912925494.
- Questions SHA256: 12835d40de697b0c719181bba59f88b86c66d4337bcfce7fc92bb673d969836f.
- Runner SHA256: 20630ac9815bddcaf2ac20ffb2183397edde573ab6e020f987ed369fa1db41b3.

## Next bounded TDD step

Use the preserved N26 projector input and the N07/N13 real before/candidate
packets as three independent acceptance controls. First reproduce missing
requested-fact coverage at projection without adding a new search or changing
budgets. Preserve the N07 explicit module-precedence fact and the N13 gain while
making N26 global/configuration preservation visible. Do not infer full semantic
support from shared anchor IDs, add question-specific answers, weaken source
policy, rewrite frozen gold, or label the 30 source-informed questions a holdout.

The previous blocked `_docs_schema_compaction.py` wording write is not retried
or bypassed. Its known test failure, obsolete mode examples and V2 witness
revision mismatch remain open. T06-T12 general repair/acceptance is not complete.

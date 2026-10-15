Clean integration candidate from exact d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c. Cherry-picked isolated FastEmbed #208, identity-only V2 locks #210 and original four PR-1 commits unchanged. Existing #206/#209 heads remain unchanged. One cause per source PR; no new semantic heuristics or expectation changes. This integration validates safe fixes only; remaining baseline causes still under diagnosis, no readiness or merge authorization. Research evidence published separately. main merge NOT_DONE.

## Consolidated continuation — 2026-10-13

Owner authorized collecting all accumulated work from `experiment/heuristic-removal-20261013` into this PR and pushing its head. The previous PR head is an ancestor: a normal fast-forward push preserves existing history; no force push, main merge or deployment.

- Source-native heuristic-removal work and earlier context-loss investigations/experiments are retained, including their historical failure reports.
- SDK delivery `limit`/`budget` and explicit lexical expansion fixes, source-tree and installed SDK evidence.
- Current-default V40 result: **22/24 positive, 8/8 documented partial, 0/8 strict-empty negative**; 40 completed contexts, source integrity/budget/read-only checks passed. No generated answers or answer-quality claim.
- E01/P03 boundary diagnostics establish loss at terminal first-fit DTO budgeting, not absence from acquisition/admission. Budget and source/scope/version protections retained.
- **MiniLM retained as an optional experiment — verification required, default OFF.** Pinned `cross-encoder/ms-marco-MiniLM-L6-v2` ONNX; weights outside the repository/package, no ordinary-query model downloads or second large model.
- Paired MiniLM pilot: both unchanged full-witness criteria remain **FAIL**. E01 filenames delivered (rank137→1), but continuation missing; P03 example rank74→106 and missing. **Full V40 reranker comparison NOT RUN** after pilot gate failure. Remaining checks: `v2plan/MINILM_VERIFICATION_TODO_RU.md`.
- Final-context sufficiency **diagnostic hook only**, disabled by default, no classifier model connected. Source-tree public integration PASS; installed in-process isolation checked on4 calls with a scripted external assessor,0 model calls. These checks prove isolation, not sufficiency accuracy or stdio/client behavior.
- Research on learned set selection/contextual representations/sufficiency preserved with primary-source receipts. No oracle rewriting or post-result manual ranking rules.

### Evidence and outstanding work

- `reports/docatlas-grounded-20261013/pre-model-research-audit/EXECUTION_RESULT_RU.md`
- `reports/docatlas-grounded-20261013/sdk-delivery-v40/RESULT_RU.md`
- `reports/docatlas-grounded-20261013/two-loss-boundaries/RESULT_RU.md`
- `reports/docatlas-grounded-20261013/learned-order/RESULT_RU.md`
- `reports/docatlas-grounded-20261013/learned-order/RESEARCH_RU.md`
- `reports/docatlas-grounded-20261013/context-sufficiency/RESULT_RU.md`

Prior PASS results describe their recorded artifacts/boundaries, not blanket acceptance of every current PR change. Full current-head CI/client/production acceptance is not established by these reports; benchmark failures remain failures. Model assets are not committed. Main merge/deploy **NOT DONE**.

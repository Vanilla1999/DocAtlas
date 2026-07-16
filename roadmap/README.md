# DocAtlas execution roadmap

This directory is the only active implementation roadmap. Older prompt collections were removed because they described an earlier product shape.

The roadmap was re-audited against `main` at commit `0664fcf` on 2026-07-11. The detailed evidence is in `AUDIT_2026-07-11.md`. Tasks 34–38 were added against the fetched Task 33C exploratory branch at `b5d1d1e` on 2026-07-15; they separate locally provable MCP/loop budgets from any later real-model benchmark claim. Tasks 39–43 were added after the 34–38 adversarial review to improve retrieval and answer quality on a fixed compact boundary before any new paid/model benchmark.

## Product direction

DocAtlas is a local-first documentation context layer for coding agents. It indexes reviewable repository documentation, detects exact dependency versions, and returns source-attributed context. Official project documentation remains normal files in Git.

DocAtlas must not silently author or commit official documentation. When documentation is missing or stale, it should give the coding model a bounded evidence-gathering and file-editing instruction, then index the accepted file.

The default agent-facing MCP path must also remain compact. Rich retrieval and audit evidence may exist internally, but the model receives one bounded canonical projection, without duplicated text/structured payloads or a broad debug schema. Static byte budgets are engineering gates, not substitutes for end-to-end correctness and provider-token evidence.

## Rules for the implementing model

1. Read `AGENTS.md`, this README, and the selected task file completely before editing.
2. Implement one numbered roadmap file per PR. Do not combine adjacent tasks.
3. Preserve the three-tool public Docs MCP surface: `get_docs_context`, `prepare_docs`, `docs_status`.
4. Do not add another public MCP tool unless the task explicitly requires it.
5. Repository files are the source of truth; SQLite and vector stores are derived indexes.
6. Never write project documentation automatically. Return instructions or propose a normal reviewable patch through the host coding agent.
7. Keep compatibility unless the task explicitly approves a breaking change.
8. Add focused tests, run related suites, and run `git diff --check`.
9. Stop when the acceptance criteria are met. Do not perform opportunistic rewrites.
10. A task is not `Done` because code exists. Every acceptance criterion needs a test, artifact, or named manual check.

## Audited state

| Task | Status | What is true now | Residual work |
|---|---|---|---|
| 01 Architecture refactor | Done for its Node slice | Python and Node parsing were extracted | Cargo/Pub and large services remain; see 25–27 |
| 02 Agent bootstrap | Done for supported installers | Compact canonical bootstrap and Docs MCP registration are installed, updated, and uninstalled with managed ownership | Task 21 credentialed low-cost-model gate remains separately owned and explicitly not-run |
| 03 Model-guided docs | Partial | Missing-doc handoff exists | `evidence_complete` can be falsely true; see 19 |
| 04 Section impact | Partial | Section metadata and CLI output exist | Stored metadata is not consumed; changed symbols are manual; see 20 |
| 05 Context7 parity | Partial | 150-item dataset and scorer exist | No real capture runner; scoring protocol is gameable; see 18 |
| 06 Cold start | Partial | Curated manifest and more lockfile parsers exist | Only three exact sources, broken target, no proven cache/SLO; see 10, 16, 17 |
| 07 Product scope | Done for scope cleanup | Core journey and honest claim boundaries exist | Benchmark is a negative signal, not product proof; see 23 |
| 08 Docs/release hygiene | Open | Task file exists | Product narrative, changelog, classifier, wiki and release truth still drift |
| 09 External ingest | Partial | Async mismatch, background execution, staging and GitHub fetch path were improved | Version propagation, hard deadlines, durable status, real failure taxonomy/recovery, reliable partial-page preservation and Kotlin evidence remain; see 11–14, 30–31 |
| 23 Product decision benchmark | Pivot required | The complete 36-cell run found no resolved-rate gain and materially higher token/latency cost | Perform patch-level failure analysis and a bounded context-delivery pivot; see 33 |
| 33 Bounded context pivot | In progress | Tasks 33A/33B and Task 33C hardening/local execution are merged. The fetched `feat/task33c-local-codex-exploratory` head `b5d1d1e` contains directional host-run artifacts, but its own report is `INCONCLUSIVE`, has a blocked lane, and is not accepted by the independent validator | Keep causal claims frozen. Use Tasks 34–38 for provider-free efficiency engineering, then run a separately approved comparable benchmark only when a verified execution environment is available |
| 34 MCP footprint truth | Done for provider-free scope | Deterministic JSON/Markdown footprint artifacts separate catalog, raw retrieval, visible response, duplication, and estimates; merged in `866d294` | Do not reinterpret static byte estimates as provider usage |
| 35 Compact MCP surface | Done for provider-free scope | The three-tool catalog is 2,001 bytes (~501 estimated tokens); normal calls use bounded structured delivery with no duplicated representative payload; merged in `866d294` | Retain the advanced-argument transition and verify real provider usage only in a later benchmark |
| 36 Canonical context projection | Done for provider-free scope | Public calls return one hash-bound bounded projection or fail closed; merged in `866d294` | Compare real-model correctness only in a later approved benchmark |
| 37 Adaptive retrieval work | Done for provider-free scope | Versioned intent routing gates expensive retrieval stages and records bounded reasons without raw text; merged in `866d294` | Treat reduced work as a latency/CPU gate, not a provider-token claim |
| 38 One-call agent loop | Done for provider-free scope | The optional host contract enforces one retained-context call and bounded request/repair/test behavior; merged in `866d294` | Production-host integration and real-model claims remain a later evidence gate |
| 39 Ranking truth | Implemented locally | FTS5 cost is converted to explicit higher-is-better utility, named feature traces and stable tie IDs are emitted, and a digest-frozen 16-case provider-free baseline has per-case gates for development/holdout/adversarial splits | Review/merge Task 39. The holdout protects Task 40 onward rather than proving a blind Task 39 improvement; selected-context contamination remains visible for Task 42 |
| 40 Parent/child index | Planned | Heading metadata and a structure-aware chunker exist, but normal Markdown ingest stores variably sized heading sections and stable child identities/spans are not the canonical retrieval unit | Add token-aware stable child chunks linked to authoritative parent sections, with exact spans, incremental rebuilds, and no overlap duplication in model-visible output |
| 41 Contextual hybrid retrieval | Planned | Lexical/dense/sparse/RRF/hierarchical components exist, but defaults/capabilities are fragmented and generic ranking is mixed with domain-specific rules | Add deterministic contextual metadata, hard authority/version filters, reproducible hybrid fusion, and an optional bounded local reranker without increasing visible context |
| 42 Minimal evidence selector | Planned | Stage/projection ceilings exist, but top-K plus cutoff does not explicitly maximize mandatory fact/authority coverage per visible token | Select a deterministic minimal sufficient evidence set, reserve required evidence, dedupe overlaps, and fail closed when critical whole items cannot fit |
| 43 Answer/token gate | Planned | Canonical answers are safe and bounded, but retrieval, selected evidence, answer completeness, and end-to-end agent success are not yet one layered Pareto gate | Prove provider-free answer/packet quality first; only then run a separately approved local production-adapter benchmark with real provider usage |

`Done for scope` means the original bounded PR is complete; it does not mean the entire subsystem is mature.

## Execution order

### Stage A — restore a truthful and safe primary workflow

1. `08_DOCS_AND_RELEASE_HYGIENE.md`
2. `10_CURATED_SOURCE_VALIDATION_HOTFIX.md`
3. `11_PUBLIC_MCP_CONTRACT_HARDENING.md`
4. `21_INSTALLER_AGENT_CONTRACT_AND_LIVE_TOOL_SELECTION.md`
5. `12_SECURE_DOCS_FETCH_BOUNDARY.md`
6. `30_NETWORK_FAILURE_RECOVERY_AND_SUITE_HERMETICITY.md`
7. `13_LIBRARY_JOB_DEADLINES_AND_CAPACITY.md`
8. `31_DURABLE_DOC_JOB_STATE_AND_RESTART.md`
9. `28_UNTRUSTED_DOCUMENT_CONTENT_BOUNDARY.md`
10. `14_KOTLIN_PARTIAL_CRAWL_ACCEPTANCE.md`
11. `15_RELEASE_ARTIFACT_GATE.md`

Do not publish a Stable release before every Stage A implementation and separately owned live/post-publish gate is green. Context7 parity additionally requires task 18's credentialed comparable report.

### Stage B — finish the local-project documentation loop

12. `19_PROJECT_DOCS_COVERAGE_AND_AUTHORITY.md`
13. `20_SECTION_IMPACT_INDEX_CONSUMPTION.md`
14. `22_CHANGE_AWARE_DOC_MAINTENANCE_LOOP.md`

### Stage C — make the product investment decision

15. `23_REAL_PROJECT_VALUE_AND_TOKEN_BENCHMARK.md`
16. `33_TASK23_FAILURE_ANALYSIS_AND_CONTEXT_PIVOT.md`

### Stage C2 — reduce MCP and retained-context cost without provider dependence

These tasks may be implemented and verified with local unit, contract, golden, and fake-adapter tests. They may claim enforced byte/request budgets only. They must not claim real-model token savings, correctness parity, or causal product value until a later comparable benchmark is available.

17. `34_MCP_TOKEN_FOOTPRINT_AND_MEASUREMENT_TRUTH.md`
18. `35_STRUCTURED_TRANSPORT_AND_COMPACT_MCP_SURFACE.md`
19. `36_CANONICAL_MODEL_VISIBLE_CONTEXT_PROJECTION.md`
20. `37_ADAPTIVE_RETRIEVAL_WORK_GATING.md`
21. `38_ONE_CALL_AGENT_LOOP_AND_CONTEXT_BUDGET.md`

Finish review/merge of this stage before starting index experiments. The compact projection and measurement boundary are the baseline that Tasks 39–43 must preserve.

### Stage C3 — improve evidence quality at a fixed compact boundary

These tasks are intentionally ordered. Do not jump directly to embeddings or a reranker: a larger/smarter index is useful only when ranking direction, holdout quality, and visible-token accounting are already truthful.

22. `39_RETRIEVAL_QUALITY_BASELINE_AND_RANKING_TRUTH.md`
23. `40_TOKEN_AWARE_PARENT_CHILD_INDEX.md`
24. `41_DETERMINISTIC_CONTEXTUAL_HYBRID_RETRIEVAL.md`
25. `42_BUDGET_AWARE_EVIDENCE_SELECTION.md`
26. `43_ANSWER_QUALITY_AND_END_TO_END_TOKEN_GATE.md`

Tasks 39–42 are provider-free local work. Task 43's provider-free gate is also local; its later production-model evidence gate remains `INCONCLUSIVE` until a verified local adapter, model credentials, and evaluator boundary are available. GitHub Actions is not required for that later local gate.

### Stage D — conditional external-library expansion

Paused because Task 23 is formally `INCONCLUSIVE` under the hardened budget gate. Do not start this stage until Task 33 produces an evidence-complete frozen benchmark that meets its decision gate. Context7/web remains the complementary external-library source during the pause.

27. `16_EXACT_SOURCE_CATALOG_AND_CACHE.md`
28. `17_LOCKFILE_WORKSPACE_VERSION_IDENTITY.md`
29. `18_CONTEXT7_PARITY_PROTOCOL_AND_CAPTURE.md`

### Stage E — reduce install and maintenance cost

30. `29_MAINTENANCE_SURFACE_POLICY.md`
31. `24_INSTALL_PROFILE_AND_DEPENDENCY_BUDGET.md`
32. `25_CARGO_PROJECT_ADAPTER_EXTRACTION.md`
33. `26_PUB_PROJECT_ADAPTER_EXTRACTION.md`
34. `27_LIBRARY_SERVICE_DECOMPOSITION.md`

After each PR, update this table with the merge commit and evidence. A later task may not silently reinterpret an earlier acceptance criterion.

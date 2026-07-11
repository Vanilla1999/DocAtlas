# DocAtlas execution roadmap

This directory is the only active implementation roadmap. Older prompt collections were removed because they described an earlier product shape.

The roadmap was re-audited against `main` at commit `0664fcf` on 2026-07-11. The detailed evidence is in `AUDIT_2026-07-11.md`.

## Product direction

DocAtlas is a local-first documentation context layer for coding agents. It indexes reviewable repository documentation, detects exact dependency versions, and returns source-attributed context. Official project documentation remains normal files in Git.

DocAtlas must not silently author or commit official documentation. When documentation is missing or stale, it should give the coding model a bounded evidence-gathering and file-editing instruction, then index the accepted file.

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
| 02 Agent bootstrap | Done for `install --project` | Compact bootstrap is generated | Hero installer does not install it; see 21 |
| 03 Model-guided docs | Partial | Missing-doc handoff exists | `evidence_complete` can be falsely true; see 19 |
| 04 Section impact | Partial | Section metadata and CLI output exist | Stored metadata is not consumed; changed symbols are manual; see 20 |
| 05 Context7 parity | Partial | 150-item dataset and scorer exist | No real capture runner; scoring protocol is gameable; see 18 |
| 06 Cold start | Partial | Curated manifest and more lockfile parsers exist | Only three exact sources, broken target, no proven cache/SLO; see 10, 16, 17 |
| 07 Product scope | Done for scope cleanup | Core journey and honest claim boundaries exist | Benchmark is a negative signal, not product proof; see 23 |
| 08 Docs/release hygiene | Open | Task file exists | Product narrative, changelog, classifier, wiki and release truth still drift |
| 09 External ingest | Partial | Async mismatch, background execution, staging and GitHub fetch path were improved | Version propagation, hard deadlines, durable status, real failure taxonomy/recovery, reliable partial-page preservation and Kotlin evidence remain; see 11–14, 30–31 |

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

### Stage D — conditional external-library expansion

Run this stage only if task 23's predeclared decision supports continued external-library parity investment. Otherwise revise or close these tasks explicitly.

16. `16_EXACT_SOURCE_CATALOG_AND_CACHE.md`
17. `17_LOCKFILE_WORKSPACE_VERSION_IDENTITY.md`
18. `18_CONTEXT7_PARITY_PROTOCOL_AND_CAPTURE.md`

### Stage E — reduce install and maintenance cost

19. `29_MAINTENANCE_SURFACE_POLICY.md`
20. `24_INSTALL_PROFILE_AND_DEPENDENCY_BUDGET.md`
21. `25_CARGO_PROJECT_ADAPTER_EXTRACTION.md`
22. `26_PUB_PROJECT_ADAPTER_EXTRACTION.md`
23. `27_LIBRARY_SERVICE_DECOMPOSITION.md`

After each PR, update this table with the merge commit and evidence. A later task may not silently reinterpret an earlier acceptance criterion.

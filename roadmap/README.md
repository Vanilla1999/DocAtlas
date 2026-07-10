# DocAtlas execution roadmap

This directory is the only active implementation roadmap. Older prompt collections were removed because they described an earlier product shape.

## Product direction

DocAtlas is a local-first documentation context layer for coding agents. It indexes reviewable repository documentation, detects exact dependency versions, and returns source-attributed context. Official project documentation remains normal files in Git.

DocAtlas must not silently author or commit official documentation. When documentation is missing or stale, it should give the coding model a bounded evidence-gathering and file-editing instruction, then index the accepted file.

## Rules for the implementing model

1. Read `AGENTS.md` and the task file completely before editing.
2. Implement one roadmap file per PR. Do not combine adjacent tasks.
3. Preserve the three-tool public Docs MCP surface: `get_docs_context`, `prepare_docs`, `docs_status`.
4. Do not add another public MCP tool unless the task explicitly requires it.
5. Repository files are the source of truth; SQLite and vector stores are derived indexes.
6. Never write project documentation automatically. Return instructions or propose a normal reviewable patch through the host coding agent.
7. Keep compatibility unless the task explicitly approves a breaking change.
8. Add focused tests, run related suites, and run `git diff --check`.
9. Stop when the acceptance criteria are met. Do not perform opportunistic rewrites.

## Execution order

1. `01_ARCHITECTURE_REFACTOR.md`
2. `02_AGENT_BOOTSTRAP.md`
3. `03_MODEL_GUIDED_PROJECT_DOCS.md`
4. `04_SECTION_LEVEL_DOC_IMPACT.md`
5. `05_CONTEXT7_PARITY_EVAL.md`
6. `06_COLD_START_SOURCE_DISCOVERY.md`
7. `07_PRODUCT_SCOPE_AND_PROOF.md`
8. `08_DOCS_AND_RELEASE_HYGIENE.md`

Architecture refactoring is first because smaller bounded modules reduce prompt size, review cost, and regression risk for every later task.

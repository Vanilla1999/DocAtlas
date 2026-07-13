# Product scope and evidence

## Default product

DocAtlas is a local-first documentation context layer for coding agents. Its primary journey is:

```text
install → get_docs_context → follow prepare_docs when returned → answer with sources
```

`get_docs_context` is the entry point for project, dependency, library, and mixed questions. `prepare_docs` performs explicit indexing, synchronization, refresh, or approved network prefetch. `docs_status` is only for health and freshness questions. Repository files remain the source of truth; DocAtlas indexes accepted files and does not author or commit project documentation.

## Advanced and maintenance-only surfaces

The following surfaces are supported but are not part of beginner onboarding and must not be expanded during this roadmap:

| Surface | Position | Reason |
|---|---|---|
| MCP Packs and pack installation | Advanced | API action tools, not documentation retrieval. |
| Patch planning, constraints, and validation | Advanced compatibility | Advisory implementation evidence; never a merge-safety proof. |
| Qdrant management and hybrid retrieval tuning | Maintenance-only | Storage and retrieval operations, not the user journey. |
| USPTO ingestion | Maintenance-only | A specialized ingestion pipeline. |
| Benchmark runners and task-level harness | Maintenance-only | Product evidence infrastructure, not end-user functionality. |
| Low-level and legacy CLI commands | Compatibility | Retained for scripts and existing users; hidden from beginner docs. |

## Evidence and claims

Each claim must name its metric:

| Claim | Evidence metric | What it does not prove |
|---|---|---|
| Retrieval returns useful sources | source precision/recall and `context_chunks_used_in_patch` | An agent will complete a patch. |
| The MCP workflow is discoverable | `docs_tool_calls` and successful first-action selection | Retrieval quality or patch success. |
| DocAtlas helps complete coding tasks | public and hidden test pass rate across repeated policy-clean runs | Superiority over repo-only until the comparison is repeated. |

Current saved public-doc comparisons measure retrieval only. DocAtlas must not claim to beat repo-only agents or Context7 for project-aware coding tasks until repeated, policy-clean benchmark runs support that statement.

Task 23's completed 36-cell task benchmark is formally `INCONCLUSIVE`: all lanes resolved 0/9 attempts, but the historical run did not capture complete token-budget metadata and its runner did not enforce the declared maximum-turn budget. Descriptively, the DocAtlas-recommended workflow increased median total tokens by about 143% and median latency by about 37%. Broader Context7-parity investment remains paused pending an evidence-complete frozen rerun; the descriptive result does not prove that local project documentation has no value.

# Sample Benchmark Report: DocAtlas vs Context7 (Live MCP)

*Generated for format reference — not a real run.*

## Executive Summary

| Metric | DocAtlas | Context7 |
|---|---|---|
| Overall Accuracy | 85% | 72% |
| Avg Response Time | 3.2s | 4.1s |
| Token Efficiency | 1,240 tok/q | 2,850 tok/q |
| Source Attribution | 100% | 62% |

## Zero-Setup

| Query | DocAtlas | Context7 |
|---|---|---|
| flutter_bloc: BlocBuilder usage | Correct, with source path | Correct, no path |
| fastapi: Depends() dependency injection | Correct, attributed | Partial |

## Preindexed

Libraries resolved before querying. DocAtlas uses local SQLite FTS5 index; Context7 uses network API.

| Category | DocAtlas | Context7 |
|---|---|---|
| Library coverage | 12/12 | 9/12 |
| Version-pinned accuracy | 100% | 67% |

## Project Docs

Tested against project-owned README, runbooks, and ADRs. DocAtlas returned Trust Contract with citations; Context7 relied on generic web knowledge.

| Query | DocAtlas | Context7 |
|---|---|---|
| Architecture overview | Exact section, path cited | Hallucinated |
| Contribution workflow | Step-by-step from CONTRIBUTING.md | Generic advice |

## Exact-Version

| Library | Requested | DocAtlas | Context7 |
|---|---|---|---|
| pydantic | 2.5.0 | Explicit unsupported (no patch-level docs) | 2.4.0 API (stale) |
| fastapi | 0.115.0 | Explicit unsupported (latest only) | Generic/stale |

## Unified Context

| Case | Expected route | DocAtlas | Context7 |
|---|---|---|---|
| project-only | project | Project docs primary, Trust Contract included | N/A |
| library-only | library | Library docs only | Public docs |
| mixed | mixed | Project docs first, library docs supplementary | N/A |
| dependency | dependency | Exact dependency docs or confirmation-required contract | N/A |

Unified-context metrics include `routing_accuracy`, `coverage_rate`, `source_scope_correctness`, `contamination_rate`, `project_primary_rate`, `exact_version_correctness_on_success`, `confirmation_contract_correctness`, `setup_calls`, and `latency`.

## Snippet-First

| Case | Expected primary snippet | Deterministic checks |
|---|---|---|
| FastAPI Depends | `Depends` Python example | symbol, language, source domain |
| Click group | `@click.group` / `click.group` Python example | symbol, language, source domain |
| Riverpod autoDispose | Dart `autoDispose` / `keepAlive` / `ref.watch` example | symbol, language, source domain |
| flutter_bloc BlocProvider | Dart `BlocProvider` example | symbol, language, source domain |
| anyhow Context | Rust `Context` / `with_context` docs.rs example | symbol, language, exact dependency version |

Snippet-first metrics include `snippet_present_at_1`, `primary_snippet_symbol_match`, `primary_snippet_language_match`, `primary_snippet_source_correct`, `snippet_noise_rate`, `snippet_truncation_rate`, `snippet_first_application_rate`, and `contamination_rate`.

## Claims We Can Make

- DocAtlas provides verifiable source attribution on every answer.
- SQLite FTS5 + local vector index enables offline, low-latency queries.
- Project-owned docs ingestion gives context-specific answers that generic web search cannot.
- Trust Contract mechanism transparently surfaces selected, rejected, and risky sources.
- DocAtlas now provides one high-level MCP entry point for project, library, dependency, and mixed documentation context.

## Claims We Cannot Make Yet

- We have not run a statistically significant number of queries.
- Results vary by library ecosystem, doc quality, and question phrasing.
- Context7 may outperform on well-documented, fast-moving libraries with frequent web updates.
- No claim that DocAtlas "wins overall" — individual runs depend on query selection.

---

*Full raw outputs (per-query JSON payloads, raw MCP responses) are generated locally during benchmark runs and stored in timestamped directories under this folder. They are **not committed** — see `.gitignore` rules. This `sample_report.md` is the only committed example and serves as a format reference only.*

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

## Claims We Can Make

- DocAtlas provides verifiable source attribution on every answer.
- SQLite FTS5 + local vector index enables offline, low-latency queries.
- Project-owned docs ingestion gives context-specific answers that generic web search cannot.
- Trust Contract mechanism transparently surfaces selected, rejected, and risky sources.

## Claims We Cannot Make Yet

- We have not run a statistically significant number of queries.
- Results vary by library ecosystem, doc quality, and question phrasing.
- Context7 may outperform on well-documented, fast-moving libraries with frequent web updates.
- No claim that DocAtlas "wins overall" — individual runs depend on query selection.

---

*Full raw outputs (per-query JSON payloads, raw MCP responses) are generated locally during benchmark runs and stored in timestamped directories under this folder. They are **not committed** — see `.gitignore` rules. This `sample_report.md` is the only committed example and serves as a format reference only.*

# ADR 0001: MCP boundary owns transport contracts

## Status

Accepted

## Context

DocAtlas exposes project and documentation context through MCP tools. The application services own business logic, but MCP clients need transport-safe JSON responses: structured failures, bounded payloads, explicit truncation metadata, and backward-compatible top-level fields.

Historically, MCP handlers duplicated output-mode logic and some failures collapsed to plain `status/message` payloads. Compact payloads could also become less useful when large evidence sections were removed without pagination or guidance.

## Decision

- The MCP interface layer owns error and output contracts.
- Application services continue to own retrieval, ranking, indexing, and project-context business logic.
- `LibraryDocsService` remains a public compatibility facade until a separate phased migration removes pass-through methods safely.
- MCP handlers should prefer direct sub-service calls when available, while preserving facade fallback for older tests, scripts, and clients.
- Degraded modes must remain visible as JSON `reason_code`, `warnings`, `diagnostics`, `mcp_compaction`, or `output_contract` fields instead of being hidden.

## Consequences

- New MCP contract helpers live under `docmancer/docs/interfaces/mcp/`.
- Structured errors keep legacy top-level `status`, `reason_code`, and `message` for backward compatibility.
- Compact output preserves useful context summaries and pagination guidance rather than silently dropping all evidence.
- Further service facade cleanup is intentionally out of scope for this ADR and should happen in smaller compatibility-preserving steps.

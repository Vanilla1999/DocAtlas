# 18 — MCP and CLI Explainability

## Problem

As retrieval becomes more source-aware and version-aware, users and agents need to understand why results were selected.

Default output should stay compact, but explicit explain modes need enough detail to debug ranking, version conflicts, and degraded retrieval.

## Goal

Improve MCP and CLI explainability for query results without making normal output noisy.

## Scope

Expose explain fields behind explicit options or structured MCP fields:

- source URL;
- canonical URL;
- source class;
- ecosystem;
- library;
- version;
- version source;
- requested retrieval mode;
- actual retrieval mode;
- degraded reason;
- lexical/dense/sparse/RRF contribution where available;
- selected snippets;
- warnings for stale or conflicting versions.

## Non-Goals

- Do not show verbose explain output by default.
- Do not expose unstable internal scores as public API unless clearly marked experimental.
- Do not require all retrieval modes to provide every score component immediately.

## Implementation Notes

Prefer structured JSON first, then human-readable formatting.

Suggested CLI shape:

```bash
docmancer query "..." --explain-json
```

MCP tools should return structured fields that agents can inspect without parsing prose.

## Verification

Add tests for:

- compact default output stays concise;
- explain JSON includes source/version/mode fields;
- degraded mode is reported when sparse or vector components are unavailable;
- snippet metadata appears when present.

## Success Criteria

- Users can debug why a result appeared.
- Agents can distinguish project docs, public docs, and exact-version dependency docs.
- Degraded retrieval does not masquerade as full hybrid retrieval.

## Current Status

Implemented MVP in:

- `docmancer/eval/trace.py`;
- `tests/test_eval.py`.

Explain traces now include per-result fields for:

- `canonical_url`;
- `source_class`;
- `ecosystem`;
- `library`;
- `version`;
- `version_source`;
- `has_code_snippet`.

Explain traces also add a structured degraded-retrieval warning when failures are present.

Verification:

```bash
uv run pytest tests/test_eval.py
```

This item is complete for structured explain-trace MVP.

Remaining future work:

- expose richer score contribution labels;
- improve CLI human-readable explain formatting;
- add MCP-specific assertions around structured fields.

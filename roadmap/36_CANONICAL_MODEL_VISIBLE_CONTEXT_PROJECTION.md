# Task 36 — canonical model-visible context projection

## Priority

P1 response-token reduction. Start after Task 35 makes bounded structured delivery the public default.

## Implementation status

Implemented locally after Task 35 and hardened after adversarial review. Normal public calls return exactly one deterministic `docs_answer`, `patch_context`, or fail-closed `insufficient_evidence` projection. Navigational/partial lanes and `source_search_required` cannot become successful docs answers; deterministic answers are extractive unless an explicit answer occurs in returned evidence. Patch projection binds duplicate path/section chunks by the exact authority-aware evidence ID, and validation recomputes each snapshot digest from its source. Projection and routing share one versioned change-intent predicate. Recursive forbidden-key checks and the existing 800/1,500/2,000/300-token ceilings remain enforced. No provider or benchmark claim is made.

## Problem

Internal retrieval values contain overlapping representations such as full `content`, `snippet`, identical `surrounding_context`, nested `source` and `section` metadata, and multiple primary/supporting/alternative snippet lists. The broad compatibility response can expose several of these representations together.

Removing fields directly from the internal retrieval model would risk breaking ranking, trust validation, evidence fidelity, and auditability. The safer boundary is a single deterministic projection from rich internal evidence to one compact model-visible contract.

## Goal

Return exactly one canonical response shape for each user intent while retaining the full source snapshot internally for validation and audit.

This task explicitly approves a versioned change to the default model-facing response shape after Task 35 has established an explicit compatibility boundary. It does not approve silently changing internal retrieval/audit schemas or removing the documented compatibility path in the same release.

The two successful public result kinds are:

1. `docs_answer` for documentation/API questions;
2. `patch_context` for coding/change tasks.

`insufficient_evidence` is a separate fail-closed status, not a partial successful answer.

## Canonical `docs_answer`

```yaml
status: ok
kind: docs_answer
answer: "short source-backed answer"
sources:
  - evidence_id: ev-...
    path_or_url: "..."
    section: "..."
    snippet: "..."
    version_binding: "..."
    content_sha256: "..."
```

Rules:

- at most three sources;
- one canonical `sources` array, not primary/supporting/alternatives in parallel;
- normal serialized target at most 800 estimated tokens;
- answer claims must be traceable to returned evidence IDs;
- exact dependency version/provenance remains visible when applicable.

## Canonical `patch_context`

Preserve the validated `ActionPacket` semantics:

```yaml
status: ok | truncated
kind: patch_context
objective: "..."
sources: []
targets: []
invariants: []
forbidden_changes: []
implementation_guidance: []
checks: []
uncertainties: []
omitted_counts: {}
estimated_tokens: 0
```

The implementation may retain the versioned internal ActionPacket field names when changing them would add migration risk. Regardless of names, the model-visible value must be singular, source-attributed, deterministically ordered, and schema-validated.

Budget policy:

- normal target: at most 1,500 estimated tokens;
- absolute ceiling: 2,000 estimated tokens;
- do not reduce the hard ceiling until a later correctness comparison proves required paths/invariants still survive;
- wrapper and recovery metadata count inside the total response budget.

## Canonical `insufficient_evidence`

```yaml
status: insufficient_evidence
kind: docs_answer | patch_context
missing: []
recommended_next_action: {}
```

Rules:

- serialized result at most 300 estimated tokens;
- no implementation guidance that invites an edit;
- no fabricated fallback facts;
- preparation remains confirmation-first;
- benchmark/client integrations must stop before edits, while the generic MCP response clearly states the required next step.

## Projection boundary

Introduce one deterministic projection layer. It may consume rich internal values, but its output must recursively exclude:

- raw `context_pack`;
- full document `content`;
- `surrounding_context`;
- ingestion/retrieval diagnostics;
- repo/code-graph dumps;
- duplicate `primary_snippet`/`primary_snippets`/alternatives representations;
- full successful test or indexing logs.

The internal evidence snapshot may keep these values outside model context. Each projected source should use immutable ID/hash and bounded path/section/line metadata so packet fidelity remains independently checkable.

## Deterministic fitting order

When a result exceeds its budget, preserve whole items in this order:

1. status, kind, objective/question interpretation;
2. canonical source-of-truth references;
3. required invariants and forbidden changes;
4. required target paths/symbols;
5. validation checks;
6. bounded implementation guidance;
7. optional supporting explanation.

Never truncate a UTF-8 string or factual item mid-value. Report omitted item counts by category. Missing required evidence produces `insufficient_evidence`, not a superficially successful smaller packet.

## Required work

1. Characterize current answer and bounded packet outputs with golden fixtures.
2. Add a dedicated model-visible projection module with deterministic serialization and ordering.
3. Build `docs_answer` from one deduplicated source list.
4. Build `patch_context` through the existing ActionPacket validator or a versioned successor with equivalent evidence rules.
5. Remove duplicate representations from public output without deleting raw internal audit evidence.
6. Add recursive forbidden-key checks for model-visible payloads.
7. Add source/evidence hash verification between internal snapshot and projection.
8. Add deterministic whole-item fitting and omitted counts.
9. Ensure the `insufficient_evidence` response is bounded and contains no edit-authorizing guidance.
10. Update public docs/examples and Task 34 fixture reports.

## Hard local gates

- `docs_answer`: at most 800 estimated tokens and at most three sources;
- normal `patch_context`: target at most 1,500, never above 2,000 estimated tokens;
- `insufficient_evidence`: at most 300 estimated tokens;
- forbidden raw keys: zero occurrences in model-visible payloads;
- every factual patch constraint has at least one valid evidence ID;
- every evidence ID resolves to the internal immutable snapshot;
- identical inputs produce byte-identical canonical JSON.

## Expected implementation areas

- `docmancer/docs/interfaces/mcp/context_tools.py`
- a new projection module under `docmancer/docs/application/`
- `docmancer/docs/application/action_packet.py`
- `docmancer/docs/models.py` only where a versioned public result type is needed
- output-contract and MCP boundary tests

## Local verification

```bash
uv run pytest tests/docs/test_mcp_token_footprint.py
uv run pytest tests/docs/test_action_packet.py tests/docs/test_mcp_boundary.py
uv run pytest tests/test_unified_docs_context_mcp.py tests/test_snippet_presentation.py
uv run python -m compileall docmancer
git diff --check
```

Use local golden/adversarial fixtures only. A provider benchmark is deferred.

## Acceptance criteria

- Every normal public result is exactly one canonical `docs_answer`, `patch_context`, or `insufficient_evidence` payload.
- Model-visible results meet their hard local budgets.
- No raw full document or duplicate context representation crosses the MCP boundary.
- Full internal evidence remains available for server validation and sanitized audit artifacts.
- Source attribution, version binding, trust policy, required evidence, and target preservation remain tested.
- Oversized inputs fit deterministically by dropping whole low-priority items and recording omissions.
- Missing critical evidence fails closed.
- Focused local tests, `compileall`, and `git diff --check` pass.

## Non-goals

- Do not alter retrieval candidate generation or code-graph policy.
- Do not lower the ActionPacket hard ceiling below 2,000.
- Do not use an LLM to summarize or compress evidence.
- Do not delete audit snapshots merely because they are not model-visible.
- Do not claim end-to-end token reduction or correctness parity without a later benchmark.

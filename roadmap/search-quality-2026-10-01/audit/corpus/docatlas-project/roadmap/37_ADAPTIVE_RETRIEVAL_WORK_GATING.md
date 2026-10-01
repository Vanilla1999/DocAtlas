# Task 37 — adaptive retrieval work gating

## Priority

P2 latency and internal-work reduction. Start after Task 36 creates a stable model-visible projection and Task 34 can measure raw versus visible context separately.

## Implementation status

Implemented locally after Task 36 and hardened after adversarial review. Documentation/API-only requests do not invoke source evidence, repo-map, or code-graph builders. Patch/source-navigation requests use the same versioned change-intent predicate as projection. The router also owns the exceptional missing-documentation authoring-evidence decision. Every stage fits whole items under explicit item and byte ceilings before context composition; observed counts/bytes and overflow remain visible in the internal routing record, and overflow fails closed. `model_visible_bytes` is populated after canonical projection. These gates primarily reduce internal work and latency; they are not a direct provider-token claim.

## Problem

Project-mode retrieval currently constructs project docs context, a repository map, source evidence, and a code graph for broad `auto`/project requests. This performs project-cartography work even for questions that only need one documentation section or exact dependency API answer.

In bounded delivery, most raw retrieval does not enter model context, so disabling internal lanes should not be sold primarily as a token reduction. Its direct benefits are lower latency, CPU/memory work, and a smaller evidence set to rank and validate. It may indirectly reduce packet noise and later agent exploration, but that requires benchmark evidence.

## Goal

Select internal retrieval lanes deterministically from task intent and evidence sufficiency. Expensive code-oriented lanes run only when their output can be necessary for the requested result.

No model call may decide routing. Hidden tests, evaluator fields, oracle patches, and post-result outcomes must not affect lane selection.

## Retrieval stages

### Stage 1 — documentation evidence

Always start with only the lanes implied by the request:

- project architecture/convention question: project-owned docs;
- dependency/API question: exact-version dependency/library docs;
- mixed question: both relevant documentation lanes;
- explicit source-location question: source evidence may start immediately.

Do not build a repo map or code graph for a complete documentation answer.

### Stage 2 — source evidence

For patch/coding tasks, collect bounded source snippets only when documentation indicates implementation targets or the task explicitly names source concepts.

Use source evidence to prove current implementation state. Do not let repository navigation metadata become authority for project policy.

### Stage 3 — repository map

Build a bounded repo map only when:

- required target paths remain unknown;
- named symbols/modules cannot be resolved from Stage 1/2;
- the task is explicitly repository-navigation oriented.

### Stage 4 — code graph

Build a bounded code graph only when at least one frozen signal holds:

- the task is cross-module/cross-package;
- multiple target modules are already supported by evidence;
- imports/references are required to connect a known source target to another required target;
- target resolution remains incomplete after earlier stages.

Generic words, large repository size alone, or a request for documentation are not sufficient.

## Routing record

Persist an internal bounded record outside model context:

```yaml
schema_version: 1
intent: patch | docs | api | source_navigation | mixed
stages:
  project_docs: {status: used | skipped, reason: "..."}
  dependency_docs: {status: used | skipped, reason: "..."}
  source_evidence: {status: used | skipped, reason: "..."}
  repo_map: {status: used | skipped, reason: "..."}
  code_graph: {status: used | skipped, reason: "..."}
raw_retrieval_bytes: 0
model_visible_bytes: 0
```

Reasons must come from versioned deterministic rules. The record is diagnostic evidence and is not added to the normal MCP response.

## Safe rollout

1. Add routing characterization tests for current representative queries.
2. Implement a versioned deterministic routing function without changing execution.
3. Run it in local shadow mode and compare proposed versus current lanes on fixtures.
4. Enable obvious low-risk skips first: library/docs-only questions must not build a project code graph.
5. Keep current patch/cross-module behavior until fixture/golden coverage proves all required targets/evidence survive.
6. Gate larger behavior changes behind one explicit temporary feature flag with a removal criterion and deadline.
7. Do not keep two indefinite production routing policies.

## Required work

1. Define intent and stage predicates in one module; remove scattered implicit checks where practical.
2. Add monkeypatch/call-spy tests proving expensive builders are not invoked when skipped.
3. Add positive tests proving repo map/code graph still run for qualifying cross-module fixtures.
4. Preserve evidence authority and trust classification across staged retrieval.
5. Enforce per-stage item and byte/token-estimate budgets.
6. Record routing reasons and per-stage raw sizes through Task 34 metrics.
7. Ensure a skipped lane cannot be reported as successful evidence.
8. Return `insufficient_evidence` when required targets remain unresolved; do not silently enable unbounded exploration.
9. Update developer documentation with the staged policy and limitations.

## Initial budgets

Use existing bounded budgets as ceilings during migration; lowering them is not the first objective. Each executed stage must still honor a finite item count and deterministic byte/token estimate.

At minimum, local tests must prove:

- docs/library-only fixture: `repo_map_calls == 0`, `code_graph_calls == 0`;
- simple single-file patch fixture: `code_graph_calls == 0` when source target is already proven;
- cross-module fixture: code graph runs at most once;
- every request performs one documentation retrieval operation at the public MCP boundary;
- routing diagnostics contain no raw source/document text.

## Expected implementation areas

- `docmancer/docs/application/project_context_service.py`
- `docmancer/docs/application/unified_context_service.py`
- `docmancer/docs/domain/query_intent.py` or a new bounded routing module
- source-map/code-graph call sites and focused tests
- Task 34 footprint fixtures/reporting

## Local verification

```bash
uv run pytest tests/docs/test_project_context_service.py
uv run pytest tests/docs/test_code_graph.py tests/docs/test_source_map.py
uv run pytest tests/test_unified_docs_context.py tests/test_unified_docs_context_mcp.py
uv run pytest tests/docs/test_mcp_token_footprint.py
uv run python -m compileall docmancer
git diff --check
```

No provider or benchmark run is required to verify deterministic lane selection. Enabling the policy does not authorize a claim about end-to-end model tokens or correctness.

## Acceptance criteria

- A versioned deterministic router owns every expensive retrieval-stage decision.
- Documentation/API-only requests do not construct repo maps or code graphs.
- Single-target patch requests avoid code graph work when earlier evidence is complete.
- Cross-module fixtures still receive the bounded connectivity evidence they require.
- Routing records distinguish used, skipped, failed, and insufficient stages without entering model context.
- Every stage has finite work/output budgets and runs at most once per public retrieval.
- Required evidence loss fails closed rather than returning a misleading successful packet.
- Focused local tests, `compileall`, and `git diff --check` pass.

## Non-goals

- Do not replace deterministic routing with an LLM classifier.
- Do not change the public three-tool inventory.
- Do not treat repo maps or code graphs as authoritative project policy.
- Do not tune rules against hidden benchmark outcomes.
- Do not claim system-wide token savings from reduced internal work alone.

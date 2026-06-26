# Sample Task-Level Report

No causal benchmark results are committed.

Current pilot scaffold status:

- two materialized FastAPI fixtures are available;
- fixture validation requires base-fail and gold public+hidden pass;
- Codex is the preferred adapter because it exposes `exec --json --ephemeral`, model selection, sandbox modes, and configured auth;
- Codex canary produced a real patch and passing test, with network probe denied by benchmark wrappers;
- kernel-level `workspace-write` sandbox failed on this host, so network enforcement is `policy_and_trajectory_audit` plus blocked `curl`/`wget` wrappers.

Example commands:

```bash
uv run python -m eval.task_level.runner --materialize --validate --tasks fastapi_depends_001 mixed_fastapi_project_001
uv run python -m eval.task_level.runner --verify-runner --runner codex --model gpt-5.5
uv run python -m eval.task_level.runner --execute --runner codex --model gpt-5.5 --tasks fastapi_depends_001 mixed_fastapi_project_001 --conditions repo_only docatlas_snippet_first --repeats 1 --run-id pilot_001
```

Latest sanitized utilization findings:

- DocAtlas MCP visibility is verified for Codex when launched through `uv run --project <repo> doc-atlas mcp docs-serve`.
- Optional availability alone produced zero adoption in the two-task utilization pilot.
- A strict diagnostic `docatlas_tool_required_once` condition produced one resolved run out of two, but it is not a product-default condition.
- A softer `docatlas_tool_recommended` condition fixed adoption (`2-6` DocAtlas calls per run across two repeats) but resolved zero out of four recommended runs.
- Observed failure classes were implementation-contract misses, not tool access failures: FastAPI auth patches missed hidden introspection names, and mixed project patches missed the exact `Annotated` dependency plus `HTTPException` error-envelope convention.

Current decision:

```text
ITERATE_DOCATLAS_CONTEXT_QUALITY
```

Secondary risk: `mixed_fastapi_project_001` may need task/public-test/context-quality iteration before scaling.

# Sample Task-Level Report

No causal benchmark results are committed.

Current pilot scaffold status:

- two materialized FastAPI fixtures are available;
- fixture validation requires base-fail and gold public+hidden pass;
- Claude Code is the preferred adapter by CLI capability, but live canary requires authentication;
- if canary fails, decision remains `ITERATE_RUNNER` and the four causal runs must not be published.

Example commands:

```bash
uv run python -m eval.task_level.runner --materialize --validate --tasks fastapi_depends_001 mixed_fastapi_project_001
uv run python -m eval.task_level.runner --verify-runner --runner claude --model sonnet
```

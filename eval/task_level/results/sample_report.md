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

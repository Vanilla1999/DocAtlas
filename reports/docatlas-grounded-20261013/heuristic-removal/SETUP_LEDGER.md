# Setup receipt — no product workloads

Executed by coordinator before final code freeze:

1. `git worktree add -b experiment/heuristic-removal-20261013 /tmp/opencode/docatlas-heuristic-removal-20261013 HEAD` from main91dd2b4e. No commit/push.
2. Dependency metadata only with stdlib importlib.metadata: existing shared runtime has pytest9.1.1,mcp1.30.0,tiktoken0.11.0.
3. `uv venv /tmp/opencode/docatlas-heuristic-removal-runtime --python /usr/bin/python3.12 --offline`.
4. New `reused_dependencies.pth` appends shared dependency site-packages; its old editable .pth is not executed. Own wheel must be installed and import-origin asserted before runtime.
5. `uv pip install --python /tmp/opencode/docatlas-heuristic-removal-runtime/bin/python 'hatchling<1.27'`: installed5 build packages; no models.
6. `uv build --wheel --no-build-isolation --python /tmp/opencode/docatlas-heuristic-removal-runtime/bin/python --out-dir <report>/wheels/baseline /home/viadmin/StudioProjects/hermes/docmancer`: baseline wheel built, SHA in BASELINE_WHEEL.json.
7. Separate baseline venv under /tmp/opencode/docatlas-heuristic-removal-baseline-runtime, same dependency-path reuse, baseline wheel installed `uv pip install --no-deps`.
8. Offline baseline ZIP audit:402 Python members equal Git HEAD source bytes, mismatches0. BASELINE_WHEEL_SOURCE_AUDIT.json. This is not runtime parity proof.

Product/import/test/prepare/context/resource/model calls0 at this checkpoint. Setup wall/CPU not measured; do not turn command success into integration PASS. Shared runtime not changed. Source worktree snapshots/metadata scripts only; no user indexes touched.

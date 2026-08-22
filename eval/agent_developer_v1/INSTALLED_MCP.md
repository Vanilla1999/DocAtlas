# P1.1 Installed-MCP live benchmark harness

This harness measures the boundary that the provider-free oracle and the older in-process model benchmark do not measure: whether a coding model can acquire the intended evidence through an **installed DocAtlas MCP process** using the exact public `tools/list` schemas.

It is an Agent Truth instrument, not a release shortcut. The maintainer has explicitly deferred the public `1.3.1` publication and post-publish verification. Development can therefore use an exact reviewed wheel now, but a reviewed-wheel run is labelled `pre-public-installed-harness` and cannot close either Public Truth or the final public-package form of P1.1.

## Unit under test

For every frozen Agent Developer task the harness creates an isolated project copy and fresh user/state directories, then launches:

```text
<fresh-venv>/doc-atlas mcp docs-serve
```

The model receives only:

- the public task id, developer task, working path, and context-call budget;
- the exact public tool names, descriptions, and input schemas returned by the installed server's `tools/list` response;
- bounded summaries of prior MCP results;
- the literal `$PROJECT_PATH` token, which the host replaces with the isolated path only immediately before the MCP call.

The evaluator-only expected trajectories, required and forbidden sources, fixture mutations, support targets, and recovery targets never enter the model request.

## Artifact modes and claim boundary

### Reviewed wheel — available before publication

A wheel built from an exact reviewed commit is installed into a fresh virtual environment with pip cache disabled. The report records:

- wheel filename and SHA-256;
- source commit SHA;
- installed distribution version;
- Python version;
- installed `doc-atlas` executable SHA-256;
- exact MCP schema digest.

This mode produces:

```text
claim_boundary = pre-public-installed-harness
artifact.origin = reviewed-wheel
```

It proves that the installed-wheel harness, stdio transport, real schemas, attribution, bounded repair, scoring, and privacy contracts work. It does **not** prove that the same bytes are public on PyPI.

### Public PyPI package — deferred

The same runner can later download and install an exact public version:

```text
artifact.origin = public-pypi
```

Only after independent release verification may the run additionally carry:

```text
artifact.public_release_verified = true
claim_boundary = public-installed-agent-evidence
```

The verifier rejects a public claim for a reviewed wheel or for an unverified PyPI origin.

## Failure-stage attribution

Every model turn and attempted MCP action is classified at the first observable boundary:

```text
model_format
→ mcp_schema
→ harness_policy
→ server_validation
→ retrieval / support / recovery outcome
→ evaluator score
```

The outer model action must first satisfy the benchmark envelope. A tool attempt is then validated against the **exact installed public input schema** before execution. The harness allows a bounded number of schema repairs, normally one. The deterministic CI pilot intentionally submits one invalid call and then a valid repair so this path cannot silently rot.

A schema-valid MCP response is not automatically a supported answer. The existing evaluator-owned Agent Developer target contract still checks:

- required scope and module selection;
- context-call budgets;
- required source identities;
- forbidden-source contamination;
- false-supported outcomes;
- ambiguity recovery ordering;
- stale-document and dependency recovery semantics.

## Evidence and privacy contract

The persisted report is allowlist-based. It contains:

- exact artifact, source, provider, model, variant, request/session, token, and schema identities;
- normalized/redacted tool arguments;
- every attempted tool call, including rejected calls;
- bounded result summaries and full-payload SHA-256 values;
- a per-task hash chain over all persisted events;
- task scores and failure-stage labels.

It intentionally does **not** persist:

- raw prompts;
- raw MCP result payloads;
- raw environment variables;
- stdout or stderr;
- authorization headers or API keys;
- absolute temporary/home/project paths.

The verifier recomputes every event digest and rejects forbidden fields, credential-like values, or absolute local paths.

## Deterministic installed-wheel CI pilot

Build and install a fresh wheel, exercise one exact-schema failure followed by one repair, and require the frozen task to pass:

```bash
rm -rf dist/installed-mcp
authenticated_python="${PYTHON:-python}"
"$authenticated_python" -m build --wheel --outdir dist/installed-mcp

"$authenticated_python" scripts/run_installed_mcp_agent_benchmark.py \
  --wheel "$(find dist/installed-mcp -name '*.whl' -print -quit)" \
  --planner scripted \
  --task module_definition_supported \
  --max-schema-repairs 1 \
  --min-pass-rate 1.0 \
  --output eval/agent_developer_v1/results/installed-mcp-ci.json

"$authenticated_python" scripts/verify_installed_mcp_agent_report.py \
  eval/agent_developer_v1/results/installed-mcp-ci.json \
  --expected-origin reviewed-wheel \
  --min-task-count 1 \
  --min-pass-rate 1.0 \
  --require-schema-repair
```

This is a deterministic infrastructure/contract gate. `scripted` is not model-quality evidence.

## Local live OpenCode run

With OpenCode authenticated and an exact reviewed wheel available:

```bash
python scripts/run_installed_mcp_agent_benchmark.py \
  --wheel dist/installed-mcp/doc_atlas-1.3.1-py3-none-any.whl \
  --planner opencode \
  --opencode-model openai/gpt-5.6-luna \
  --max-schema-repairs 1 \
  --min-pass-rate 0.0 \
  --output eval/agent_developer_v1/results/installed-mcp-opencode.json

python scripts/verify_installed_mcp_agent_report.py \
  eval/agent_developer_v1/results/installed-mcp-opencode.json \
  --expected-origin reviewed-wheel \
  --min-task-count 11 \
  --min-pass-rate 0.0
```

The pass-rate threshold remains `0.0` for initial evidence capture. Low autonomous performance is retained as Agent Truth evidence rather than converted into an infrastructure failure. Infrastructure errors, false support, contamination, missing request identity, schema drift, or privacy violations still fail verification.

## Optional direct OpenAI run

```bash
OPENAI_API_KEY=... \
python scripts/run_installed_mcp_agent_benchmark.py \
  --wheel dist/installed-mcp/doc_atlas-1.3.1-py3-none-any.whl \
  --planner openai \
  --openai-model gpt-5.6-luna \
  --max-schema-repairs 1 \
  --output eval/agent_developer_v1/results/installed-mcp-openai.json
```

The manual GitHub Actions workflow uses this transport because it can receive a repository secret without making provider availability a required pull-request gate.

## Deferred public-package run

After the public release and independent public-byte verification exist:

```bash
OPENAI_API_KEY=... \
python scripts/run_installed_mcp_agent_benchmark.py \
  --pypi-version 1.3.1 \
  --public-release-verified \
  --planner openai \
  --output eval/agent_developer_v1/results/installed-mcp-public.json

python scripts/verify_installed_mcp_agent_report.py \
  eval/agent_developer_v1/results/installed-mcp-public.json \
  --expected-origin public-pypi \
  --require-public \
  --min-task-count 11
```

`--public-release-verified` is an explicit evidence assertion, not an online auto-detection shortcut. It must be used only after the repository's separate public-release evidence establishes the exact public package identity.

## P1.1 completion boundary

This MR completes the **harness implementation** when:

- a fresh reviewed wheel is the only server implementation;
- no editable/PYTHONPATH import can satisfy the server process;
- stdio initialization and exact `tools/list` schema hashing work;
- every attempted tool call and schema failure is retained;
- one bounded repair is proven by deterministic CI;
- provider/request/token provenance is represented;
- stage attribution and privacy verification are fail-closed.

Final P1.1 Agent Truth evidence remains pending until all 11 frozen tasks are captured through the public-package mode with a real coding model. Public API changes remain frozen until P1.2 derives repeated first-divergence classes from those records.

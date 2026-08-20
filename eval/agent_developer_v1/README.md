# Agent Developer Protocol v1

This protocol evaluates DocAtlas as an evidence runtime for a coding agent, not as a human-facing question-answering interface.

The unit under test is a **coding trajectory**: a developer task has a working path, one or more evidence scopes, bounded `get_docs_context` calls, required source identities, forbidden source identities, and a target support/recovery outcome. The provider-free CI lane executes the reviewed oracle trajectory. A model-backed lane can now let a coding model choose the read-only evidence calls itself while being scored against the same evaluator-owned task contract.

## Why this protocol exists

The project-answer surface and self-hosting gates prove bounded question parsing and the complete retrieval → proof → projection pipeline on reviewed DocAtlas questions. They do not prove that an agent working inside an arbitrary small module can move safely between module-local, project-wide, cross-module, dependency, ambiguity, and stale-document evidence.

This corpus therefore freezes agent-oriented invariants:

- `module_path` retrieval must not leak neighboring module or project evidence;
- a project-wide obligation must use project scope rather than silently widening a module call;
- a task that needs module and project facts may use two bounded context calls;
- cross-module comparison uses `scope="all"` without a module filter;
- missing exact dependency docs remain non-edit-ready and return reviewed prefetch guidance;
- stale project docs remain non-edit-ready and return reviewed sync guidance;
- ambiguous module names must never be resolved by guessing;
- any source listed in `forbidden_sources` is a blocking contamination failure.

## Baseline versus target

`tasks.json` contains the public coding-agent task prompt, working path, fixture id, class, and tool-call budget. It intentionally omits oracle scopes, source identities, questions, and expected outcomes. The model-backed runner narrows that public record further: the model receives only the task id, developer task, working path, and `get_docs_context` call budget. `class` and `fixture` stay host-side so they cannot reveal the expected planning strategy.

`expected_trajectories.json` is evaluator-only oracle data. It keeps **baseline** and **target** expectations separate. Baseline expectations freeze what the current released engine is known to do. A known safe false-negative is represented with `known_gap` rather than being hidden or converted into a passing answer. Target expectations define the desired behavior after later production commits. The model-backed lane never serializes this file, its scopes, expected questions, required/forbidden sources, mutations, or known gaps into the model request.

The frozen baseline remains a historical reference while later commits close named safe gaps. The runner accepts a changed result only when the **complete target contract** matches, including target status, required sources, recovery tool, and confirmation reason. This prevents an `insufficient_evidence → ok` improvement from being mislabeled as false support while still rejecting an unsupported `ok` that lacks its target evidence.

The provider-free runner exits non-zero when a call matches neither its frozen baseline nor its complete target contract, or when it produces false support, missing required evidence, a wrong recovery action, edit-authorizing failure output, scope drift, an invalid working path, metric drift, or forbidden-source contamination. A target gap is reported until the complete target contract is closed.

## Provider-free CI gate

```bash
python scripts/run_agent_developer_gate.py
```

The run is provider-free and uses an isolated temporary `DOCMANCER_HOME`. It copies each fixture before indexing so stale-doc mutations never alter committed files.

Final acceptance summary:

```text
target closure: 11/11 tasks; named target gaps=0; false-supported=0; forbidden-source-contamination=0
Agent Developer Protocol v1: TARGET PASS
```

The runner is a hard CI gate: any remaining target gap, baseline/target contract drift, false-supported result, wrong recovery action or arguments, missing required source, edit-ready failure, scope/working-path drift, target-metric drift, or forbidden-source contamination exits non-zero. The historical baseline remains in the oracle only to distinguish reviewed behavior changes from regressions; it no longer permits a baseline-only CI pass.

## Model-backed planning benchmark

The model-backed benchmark measures the missing layer: whether an actual coding model can choose the correct DocAtlas evidence trajectory without seeing the evaluator trajectory first.

The model-visible surface is intentionally smaller than the evaluator surface:

- task id, developer task, working path, and context-call budget only;
- host-owned `get_docs_context`, `docs_status`, and `finish` actions only;
- no `prepare_docs`, sync, dependency prefetch, repository write, test, shell, source-search, or network action is model-callable;
- `project_path` is injected by the host rather than selected by the model;
- stale-document mutations and every oracle expectation stay evaluator-side;
- model-visible DocAtlas feedback is bounded and the temporary project path is redacted.

The scorer compares model-chosen calls with the same evaluator-owned target contract used by the provider-free protocol. It checks call budgets, exact scope/module selection, target status and sources, forbidden-source contamination, false support, and ambiguity recovery. For an ambiguity task it also accepts a strictly safer shortcut when the model derives the exact module path from the supplied working path and directly obtains the same target evidence; the benchmark does not force an unnecessary ambiguous-name call merely to imitate the oracle path.

The live closure is pinned to **`gpt-5.6-luna` with the `medium` variant**. The preferred local path uses the authenticated OpenCode chat session instead of requiring a direct API key. `scripts/opencode_chat_support.py` invokes `opencode run --format json --model <provider>/gpt-5.6-luna --variant medium` inside an isolated temporary project whose OpenCode permissions are denied, so the model cannot inspect repository/evaluator files or call shell, web, MCP, skills, or other tools.

### One-command local closure

From the repository root, with OpenCode already authenticated:

```bash
uv run python scripts/run_live_model_closure.py \
  --opencode-model openai/gpt-5.6-luna
```

The orchestrator reuses an already complete passing Task 21 report unless `--force-task21` is supplied, runs all missing Agent Developer tasks, seals/verifies the Agent report, and then runs the provider-free committed-evidence contract test.

Agent resume is provenance-bound. Every reusable OpenCode Agent turn must contain the exact current `benchmark_contract_sha256`, derived from the evaluator corpus/fixtures, OpenCode transport/runner, provider-free oracle gate, and DocAtlas Python runtime. If any of that contract changes, the old row is not reused and that task is run again. Result files, local caches, and this README are excluded from the fingerprint so recording/documenting evidence does not invalidate it.

On evidence-complete success the files are:

```text
eval/results/task21_tool_choice_gate.json
eval/agent_developer_v1/results/model-benchmark.json
```

The Agent Developer result directory may be ignored by repository defaults, so use `git add -f` for that report when recording evidence.

The Agent benchmark deliberately has no retrospectively invented minimum pass-rate: the frozen verifier currently uses `--min-pass-rate 0.0`. A low pass-rate is retained as model-quality evidence rather than converted into an infrastructure failure. Closure still requires all 11 tasks to execute, no infrastructure errors, zero false-supported outcomes, zero forbidden-source contamination, current sealed task/oracle fingerprints, `medium` on every usage row, and exact benchmark-contract provenance for OpenCode rows.

### Individual local OpenCode run

```bash
uv run python scripts/run_agent_developer_opencode_chat.py \
  --opencode-model openai/gpt-5.6-luna \
  --resume \
  --output eval/agent_developer_v1/results/model-benchmark.json

uv run python scripts/verify_agent_developer_model_report.py \
  eval/agent_developer_v1/results/model-benchmark.json \
  --seal \
  --expected-model gpt-5.6-luna \
  --min-pass-rate 0.0
```

### Optional direct OpenAI API path

The direct Responses API runners and manual GitHub Actions workflows remain available as an optional transport. They are fixed to Luna/medium and use `OPENAI_API_KEY`, but they are intentionally **not** required pull-request gates: provider availability, credentials, rate limits, and model behavior must not make deterministic CI non-reproducible.

GitHub Models is not a supported live provider for this benchmark anymore: its inference service was retired in July 2026. Historical GitHub Models report/provider code may remain for audit compatibility, but new live evidence must use an active provider.

The report records pass rate, scope accuracy, recovery accuracy, false support, forbidden-source contamination, provider/model identity, per-turn token usage, reasoning effort, request/session identifiers, and the bounded model-chosen trajectories. Provider/transport failures are reported separately as infrastructure errors rather than being counted as model-quality failures.

## Current closure

After the scope/recovery contract hardening, the provider-free oracle closes all **11/11** reviewed trajectories. Module ambiguity remains fail-closed, but the bounded response preserves `operational_reason_code=module_ambiguous`, returns at most eight exact `module_candidates`, recommends public `docs_status(action="project", details=true)`, verifies both module identities in that response, and performs the successful retry with an exact `module_path`. The dependency trajectory now proves both module-local evidence and the exact dependency-prefetch recovery within two context calls. The permanent `advanced-contract` CI job runs this protocol on every pull request and push to `main`; the separate model-backed lane measures autonomous planning without replacing that deterministic gate.

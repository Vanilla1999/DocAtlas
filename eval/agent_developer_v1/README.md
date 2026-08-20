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

A trusted GitHub Models run is manual by design:

```bash
AGENT_DEVELOPER_GITHUB_TOKEN=... \
python scripts/run_agent_developer_model_benchmark.py \
  --model openai/gpt-4o-mini \
  --output eval/agent_developer_v1/results/model-benchmark.json
```

The repository workflow `.github/workflows/agent-developer-model-benchmark.yml` uses `workflow_dispatch`, read-only repository permission plus `models: read`, Python 3.13, and SHA-pinned Actions. It first reruns the provider-free product-scope contract, then executes the model benchmark and uploads the JSON report. It is intentionally **not** a required pull-request gate: provider availability, rate limits, and model behavior must not make deterministic CI non-reproducible. An explicit `--min-pass-rate`/workflow input can turn a trusted benchmark run into a chosen quality threshold without changing the permanent provider-free release gates.

The report records pass rate, scope accuracy, recovery accuracy, false support, forbidden-source contamination, provider/model identity, per-turn token usage, and the bounded model-chosen trajectories. Provider/transport failures are reported separately as infrastructure errors rather than being counted as a model-quality failure.

## Current closure

After the scope/recovery contract hardening, the provider-free oracle closes all **11/11** reviewed trajectories. Module ambiguity remains fail-closed, but the bounded response preserves `operational_reason_code=module_ambiguous`, returns at most eight exact `module_candidates`, recommends public `docs_status(action="project", details=true)`, verifies both module identities in that response, and performs the successful retry with an exact `module_path`. The dependency trajectory now proves both module-local evidence and the exact dependency-prefetch recovery within two context calls. The permanent `advanced-contract` CI job runs this protocol on every pull request and push to `main`; the separate manual model-backed lane measures autonomous planning without replacing that deterministic gate.

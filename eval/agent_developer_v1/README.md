# Agent Developer Protocol v1

This protocol evaluates DocAtlas as an evidence runtime for a coding agent, not as a human-facing question-answering interface.

The unit under test is a **coding trajectory**: a developer task has a working path, one or more evidence scopes, bounded `get_docs_context` calls, required source identities, forbidden source identities, and a target support/recovery outcome. The provider-free CI lane executes the reviewed oracle trajectory. A future model-backed lane may let a coding model choose the calls itself, but it must be scored against the same task contract.

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

`tasks.json` contains only the public coding-agent task prompt, working path, fixture id, class, and tool-call budget. It intentionally omits oracle scopes, source identities, questions, and expected outcomes.

`expected_trajectories.json` is evaluator-only oracle data. It keeps **baseline** and **target** expectations separate. Baseline expectations freeze what the current released engine is known to do. A known safe false-negative is represented with `known_gap` rather than being hidden or converted into a passing answer. Target expectations define the desired behavior after later production commits. A future model-backed lane must not expose this file to the coding model.

The runner exits non-zero for baseline drift, false-supported outcomes, missing required baseline sources, wrong recovery actions, or forbidden-source contamination. A target gap is reported but does not fail this first diagnostic commit.

## Run

```bash
python scripts/run_agent_developer_gate.py
```

The run is provider-free and uses an isolated temporary `DOCMANCER_HOME`. It copies each fixture before indexing so stale-doc mutations never alter committed files.

Expected first-commit summary:

```text
Agent Developer Protocol v1: BASELINE PASS
```

followed by a target-closure count and named gaps. Later commits should reduce the named target gaps without changing the safety contract.

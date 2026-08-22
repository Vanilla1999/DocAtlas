# Installed MCP Agent v1

Status: **harness construction**, not Agent Truth closure.

Maintainer sequencing decision on 2026-08-22: public publication and post-public release verification are deferred. The reviewed `1.3.1` release request is therefore non-executable (`execute_on_merge=false`). P0 public-artifact rows remain pending; this work must not present a built wheel, source checkout, tag, or scripted driver as public-release evidence.

This protocol implements the next measurement boundary without changing the public MCP API or retrieval semantics:

```text
exact source commit
→ built wheel or exact public wheel
→ fresh virtual environment
→ installed `doc-atlas mcp docs-serve`
→ real tools/list schemas
→ model/driver tool attempts
→ MCP schema validation
→ server result
→ support/recovery classification
→ sanitized evidence record
```

## What this slice proves

The provider-free CI lane proves only that:

- the harness builds one wheel and installs that wheel into a fresh virtual environment;
- the server process is the installed `doc-atlas` executable, not an editable source import;
- MCP initialization and `tools/list` use the installed three-tool surface;
- every attempted call is classified and hashed;
- one bounded scripted trajectory can obtain cited project evidence;
- the resulting report contains package, commit, schema and trajectory identity without raw prompts, raw results, secrets, or absolute workspace paths.

It does **not** prove that an autonomous coding model can use the contract. A real-model run is required before P1.1 can be marked complete.

## Package modes

The harness supports two explicit modes:

1. `--wheel PATH` — a wheel built from an exact reviewed commit. While publication is deferred, this is the only CI mode and is labelled `built_wheel`.
2. `--package-spec doc-atlas==X.Y.Z` — downloads one exact public wheel with pip cache disabled, hashes it, installs those exact bytes, and labels the run `public_package`.

A `built_wheel` report cannot close any public-release scorecard row. A future Agent Truth claim should normally use `public_package` after the deferred release work is completed.

## Driver protocol

`--driver scripted` is a deterministic positive control. It executes the canonical lifecycle:

```text
get_docs_context
→ prepare_docs(sync_project_docs, with_vectors=false)
→ get_docs_context
→ final
```

`--driver-command '<command>'` is the real-model adapter boundary. For each turn the command receives one JSON object on stdin and must return exactly one JSON object on stdout:

```json
{"type":"tool_call","name":"get_docs_context","arguments":{}}
```

or:

```json
{
  "type":"final",
  "text":"bounded final answer",
  "provider":"provider-id",
  "model":"model-id",
  "request_id":"provider request id",
  "usage":{"input_tokens":0,"output_tokens":0}
}
```

The turn payload contains the case question, the exact installed tool schemas, and bounded in-memory history. Raw payloads and raw tool results are never written to the report.

## Frozen smoke case

`cases/project_docs_round_trip.json` is an infrastructure positive control, not one of the 11 Agent Developer outcome cases. It creates a temporary repository with one reviewable project document and requires the installed server to return its exact source and marker text.

The 11 frozen real-model cases and their first-divergence atlas remain P1.2 work. They must not be silently replaced by this smoke case.

## Report contract

Each report records:

- source commit and dirty-state claim;
- install mode, distribution, version, wheel filename and SHA-256;
- installed CLI identity;
- exact tool names and canonical schema SHA-256;
- driver/provider/model/request and reported usage provenance;
- every attempted tool call with argument/result hashes and failure stage;
- bounded repair counters;
- outcome and first divergence;
- privacy scan result.

Failure stages are intentionally separate:

```text
adapter_protocol
mcp_schema
server_validation
retrieval
support
recovery
none
```

The verifier rejects reports containing absolute Unix, Windows or UNC paths, known credential field names, raw prompt/result fields, an unexpected public tool, invalid hashes, missing attempts, or a success result with a non-`none` first divergence.

## Local provider-free run

```bash
python -m pip install -e '.[dev]' build
python -m build --wheel
python scripts/verify_installed_mcp_agent_report.py --self-test
python scripts/run_installed_mcp_agent_harness.py \
  --wheel "$(find dist -name '*.whl' -print -quit)" \
  --case eval/installed_mcp_agent_v1/cases/project_docs_round_trip.json \
  --driver scripted \
  --output /tmp/installed-mcp-agent-v1.json
python scripts/verify_installed_mcp_agent_report.py \
  /tmp/installed-mcp-agent-v1.json
```

## P1.1 completion boundary

P1.1 remains open until at least one frozen real-model run supplies:

- a non-scripted provider/model identity;
- provider request IDs for every model turn;
- real usage provenance or an explicit provider-unavailable marker;
- every tool attempt, including validation failures;
- bounded repair behavior;
- a reproducible package/commit/schema identity;
- a privacy-clean artifact;
- no claim stronger than the measured outcome.

No `working_path`, server-owned inference, continuation token, retrieval tuning, or public schema change is authorized by this harness alone. Those remain hypotheses for P1.2/P1.3.

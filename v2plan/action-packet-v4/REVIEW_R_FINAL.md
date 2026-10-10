# Independent R final delta review

**Verdict: core R1–R8 closures remain intact and finalized patch data survives the reviewed provider-composition path, but the active eval migration has one remaining Medium blocker (R9: stale required-once MCP instructions). Do not claim the active migration is fully complete at this HEAD.**

Reviewed exact HEAD: `50c6bb24c71ab3597100914d7f3d9ed1a2f05fda`, worktree `/tmp/opencode/action-packet-v4-integration`. Baseline for this final delta: `d84ff2972e65ee996d0688513dc04b724fdeec56`.

## Scope and execution boundaries

- Read the entire final `CONTRACT.md`, including amendment 11. Independently inspected `git diff d84ff297..HEAD`, the integrated `edf4c698` indirect-consumer migration and `50c6bb24` provider-history/reporting changes. Reviewed actual new mocked-runner test code, not worker reports.
- Initial `REVIEW_R.md` and `REVIEW_R_CLOSURE.md` were not edited; their working-tree bytes match their committed HEAD blobs. They remain the detailed evidence for the independently reproduced R1–R8 closures.
- No production/test edits, nested agents, live provider/network calls, installations, indexing, corpus/runtime scan expansion or historical evaluation/test execution. Only this NEW repository report was written. Independent mocked-runner output went only under the dedicated NEW-test temporary directory, not repository/historical artifacts.
- `FINAL_REPORT_RU.md` is a coordinator-owned pending template, not evidence of a completed gate; its update is outside this review.

## Commands and actual results

Executed with normal conftest and the existing interpreter:

```sh
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python -m pytest tests/test_action_packet_v4_contract.py tests/test_action_packet_v4_selection.py tests/test_action_packet_v4_public.py tests/test_action_packet_v4_integrated.py tests/test_action_packet_v4_eval.py --basetemp /tmp/opencode/action-packet-v4-r-final-tests -o cache_dir=/tmp/opencode/action-packet-v4-r-final-cache
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python v2plan/action-packet-v4/VERIFY_EXAMPLES.py
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python v2plan/action-packet-v4/VERIFY_SCOPE.py
```

All exit 0:

- **194 passed in 5.59s**, all five NEW suites.
- Examples all PASS through actual dispatch/current surface schema/terminal structuredContent/text fallback: 205 bytes/52 tokens, 1665/417, 1369/343, 26171/6543. The last example retains 18 distinct necessary sources and requirements.
- Scope: 59 changed paths, 2567 unchanged baseline paths, syntax PASS for 50 modules, whitespace PASS.
- Independent import check: **43 changed source/eval modules import successfully** from the worktree.
- Independent static AST check of eval source: **16 calls** to `build_action_packet`, `validate_action_packet`, `project_patch_context` or `patch_selection_config`; no removed `max_tokens` keyword or positional patch-selection budget remains on those direct names/attributes. This is not a proof about arbitrary dynamic forwarding.

Additional inline-Python commands with the same environment independently exercised composer, nine-turn mocked runner, evaluator behavior, public argument rejection and Codex observation metadata. All assertions passed/commands exited 0. No HTTP/provider client was called: the real runner's client was replaced with an in-process stub and retrieval with NEW `OfflineRetrieval` fixtures.

## Finding R9 — Medium: active required-once prompt still instructs a removed MCP argument

**Locations:** `eval/task_level/conditions.py:174-187` (especially `:180`), injected by `eval/task_level/_execution_part04.py:228-229`; current required-once reader `eval/task_level/runners/codex.py:412-427` expects `context_format='patch_context'`.

`TOOL_REQUIRED_ONCE_INSTRUCTION` still tells a direct MCP actor to call:

```text
project_path="."
delivery_strategy="bounded_direct"
question="<original task objective>"
```

The active `docatlas_tool_required_once` condition has `require_docatlas_call_before_edit=True`, so `execute_pilot` appends this instruction to its actual agent prompt. This is not merely an old saved report or a frozen score/threshold assertion. Current public MCP rejects `delivery_strategy` as unknown; the instruction also omits the new explicit patch format. A direct MCP/Codex actor following the supplied arguments cannot produce the expected v4 retrieval observation.

**Independent concrete reproduction, executed offline:**

```python
import runpy
from docmancer.mcp._docs_server_part01 import call_docs_tool_payload
from eval.task_level.conditions import CONDITIONS, TOOL_REQUIRED_ONCE_INSTRUCTION
from eval.task_level.runners.codex import _required_once_retrieval_metadata

m = runpy.run_path('tests/test_action_packet_v4_public.py')
raw = m['necessary_evidence'].__wrapped__(None)
service = m['OfflineRetrieval'](raw)
question = 'Inspect protocol implementations'
args = {'question': question, 'project_path': '.',
        'delivery_strategy': 'bounded_direct'}
result = call_docs_tool_payload('get_docs_context', args, service)
metadata = _required_once_retrieval_metadata(
    {'arguments': args, 'result': {'structuredContent': result}},
    task_objective=question,
)
```

Actual result:

```text
status=failed
error.reason_code=validation_error
error.message=unknown field(s) for get_docs_context: delivery_strategy
offline retrieval service calls=0
question_matches_task_objective=True
context_format=None
action_packet_result=None
action_packet_completeness=None
retrieval_succeeded=False
```

Also independently asserted that the active condition requires instruction injection and that the constant contains the obsolete `delivery_strategy="bounded_direct"` line. The hosted runner smoke does not catch this: its controlled `get_docs_context(query)` adapter substitutes `context_format='patch_context'` internally, whereas direct MCP actors consume the prompt.

**Invariant:** user-approved active API/field migration must use the actual reachable public v4 ingress. Preserve historical score thresholds/one-call counts, but do not give active callers invalid legacy wire arguments or add an adapter that pretends v3 still works.

**Suggested closure:** narrowly migrate the active required-once instruction to explicit read-only `context_format="patch_context"`, preserving task objective and historical call counts/thresholds. Add a NEW offline check that the arguments advertised by the injected instruction are accepted by the real current surface and satisfy v4 observation metadata. `conditions.py` is outside C's current enumerated write ownership; coordinator approval for that narrow dependency is needed before editing it. R made no production fix. This blocker is in active eval integration, not a reopened core R1–R8 finding or a claim about a live model's behavior.

## Independent provider/history evidence

Inspected `_github_models_part02.py:254-258` (full patch tool output, no 8000-character slice), `_github_models_part01.py:605-684` (recognition, history selection and clipping exemptions), and `:68-77` (existing hosted input guard bypass for recognized v4 data, no enlarged sentinel).

Built actual finalized necessary protocol data using the NEW 12-source fixture and `_task42_projection`, with an old eval maximum of 128. It validates against its canonical snapshot; packet estimate is **13975**. Independent checks:

- Serialized provider message is **55920 UTF-8 bytes**, well beyond the old 8000-character boundary and 32000-byte transport boundary.
- Put that message before **12 newer ordinary history messages**, then composed with the original `token_limit=7000`. The protected message remains byte-for-byte intact, all 12 source windows retain their SHA256s, `clipped_messages=[]`, and `protected_patch_data_exceeds_input_budget=True`. There is no fake increased cap or infinity/large sentinel.
- Embedded the same finalized projection alongside explicit target/preservation instructions in a base message and composed with `token_limit=1`. The entire message is unchanged. Its explicit instructions are retained, not inferred as permissions from document data.
- Ordinary history without patch data stays within its existing budget (independent estimate **3687 <= 7000**), and its protected-over-budget flag is false.

**Independent actual runner reproduction:** used the real `GitHubModelsRunner`, real `_execute_agent_tool`/handler and message composer; replaced only provider client and retrieval service with offline stubs. Used the workspace already produced by the NEW mocked-runner fixture, only `list_files` between retrieval and finish, no shell/test/edit action, and a verified stub sandbox.

The runner completed **9 requests**. After the first retrieval, the same **55932-byte** patch-bearing message was delivered unchanged in **8 subsequent requests**, including the last request beyond the old six-message history selection. Each retained packet has `result=data`, `edit_ready=False`, 12 sources and valid exact-text hashes. Retrieval service was called exactly once. This reproduces more history aging than the seven-turn NEW test and never calls a provider.

Provider-side/model capacity is still UNKNOWN. Shape recognition at composition has no independent retrieval snapshot; it must not be described as a new evidence-authentication or edit-authorization mechanism. Full packet validation belongs upstream. Non-patch provider response/request-count guards remain operational safeguards, not v4 source-window compaction.

## Remaining migrated consumers and frozen-policy separation

- The ten indirect consumers plus `report.py`, `_execution_shared.py` and provider history changes were inspected. Reporting now reads `result/completeness`; actionability measures visible sources/assignments while normative/workflow recalls remain zero/unsupported. No replacement v3 policy scaffold or document-derived workflow grant was found in the reviewed delta.
- Independently ran the projection gate on the unchanged large packet: an eval maximum of 1500 fails `projection:token_budget_or_estimate`, then maximum 50000 passes. Both checks leave all 12 sources untouched. These are evaluator assertions, not output-producing caps; the numbers here are NEW reproduction inputs, not changes to frozen thresholds.
- Independently measured actionability: source coverage/citation fidelity 1.0, critical-invariant and behavioral recalls zero. `_bounded_direct_projection_errors` explicitly returns `unsupported_evaluation_requirement:workflow_checks_from_patch_context`.
- Independently ran a small valid v4 packet through `OneCallAgentLoop` followed by a fake shell action: `retrieval_only_does_not_authorize_edit`, no action execution. Existing one-call loop output/history ceilings still fail an evaluation closed rather than crop mandatory patch blocks; they remain historical eval/runtime policy, not a public formatter budget. Historical actor acceptance is not established.
- Independently confirmed docs `_task42_projection` remains `docs_answer`, estimate **52**, within 800, no validation errors. The full NEW docs/profile regressions also pass.
- Searched current eval source for legacy packet field reads and producer budgets. Remaining `status` reads are docs branches, observations of general run status, or legacy metric branches bypassed for schema v4. Remaining `invariants/checks` reads in actionability are below its early v4 return. The stale active prompt argument is separately reported as R9 rather than dismissed as frozen historical reporting.

## Preservation and final limits

- Base-to-HEAD changed-path inventory contains only approved production/eval paths, NEW v4 tests/shards and new `v2plan/action-packet-v4/` coordination documents. No old tests/conftest/gold/frozen threshold files, historical artifacts/reports, WIP/removal reports or NEXT work changed in that tracked diff. Threshold values in untouched condition/schema/pilot protocols remain unchanged; updated unsupported-policy prose retains the historical RED/GREEN count rather than enabling it.
- Primary worktree read-only status is still solely `?? v2plan/artifacts/`; primary HEAD is `b89fa3cc16534445501bab14e0d63e099e9f61f6`. Those unfamiliar/pre-existing untracked artifacts were neither opened nor changed; their complete historical parity is not proved.
- R1–R8 remain closed within the prior independently verified scope; this final delta does not modify the core fixes and their NEW regressions pass again. The one unresolved active eval blocker is R9 above.
- External transport/model capacity, wheels/package parity, index/corpus parity, live-provider behavior and historical evaluation acceptance remain **UNKNOWN**. No live/historical evaluations were run, no global mathematical minimization claim is made, and no full-product release or security proof is offered.
- Final gate at this exact HEAD is **not fully clear for all active eval consumers** until R9 is corrected or explicitly excluded by the coordinator with an honest limitation. Core/transport/composer preservation checks above pass; they do not erase that blocker.

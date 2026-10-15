# Independent R final closure

**Bounded verdict: R1–R9 closed. No residual finding or local review blocker identified in this final narrow delta.** This is completion of the reviewed core/active-consumer migration gate, not full-product release, security, provider, installed-package or index parity certification.

Exact reviewed HEAD: `0f72267710317897f74cff93e996191809e342e7` at `/tmp/opencode/action-packet-v4-integration`. Final delta baseline: `50c6bb24c71ab3597100914d7f3d9ed1a2f05fda`.

During report completion, the coordinator advanced HEAD to `88271210c85d29fc6817475651176ca1210de016` (`docs: record final 195-test integrated verification`). Independently checked `git diff 0f722677..HEAD`: only `FINAL_REPORT_RU.md` changed; the production/eval/test delta is empty. Test and reproduction evidence below is for the requested `0f722677` code, unchanged by that documentation commit.

## Independent scope

- Inspected `git diff 50c6bb24..HEAD`, including the actual one-line instruction change, NEW regression/shard, amendment 12 and coordination documents. Amendment 12 authorizes this narrow `conditions.py` dependency. No worker claim or pending coordinator template was used to close R9.
- The only production/eval path changed in this delta is `eval/task_level/conditions.py`. Core fixes and previously reviewed provider composer/consumer paths are unchanged. The prior independent R1–R8 closures and provider-preservation evidence remain applicable, and their NEW regression suites pass again.
- Production/tests were read-only. Initial `REVIEW_R.md`, `REVIEW_R_CLOSURE.md` and `REVIEW_R_FINAL.md` working bytes were independently compared to committed HEAD blobs and are unchanged. Only this NEW report was written by R.
- No nested agents, network/live provider calls, installations, indexing, scan expansion, old tests or historical evaluations. The actual prompt injection was executed in isolation, not by running a historical pilot.

## Exact suite/verification commands and actual results

From the integration worktree:

```sh
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python -m pytest tests/test_action_packet_v4_contract.py tests/test_action_packet_v4_selection.py tests/test_action_packet_v4_public.py tests/test_action_packet_v4_integrated.py tests/test_action_packet_v4_eval.py --basetemp /tmp/opencode/action-packet-v4-r-final-closure-tests -o cache_dir=/tmp/opencode/action-packet-v4-r-final-closure-cache
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python v2plan/action-packet-v4/VERIFY_EXAMPLES.py
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python v2plan/action-packet-v4/VERIFY_SCOPE.py
```

All exit 0:

- **195 passed in 5.89s**, all five NEW suites, normal conftest.
- Examples all PASS: failure 205 bytes/52 tokens; partial 1665/417; small complete 1369/343; unique necessary evidence 26171/6543 with 18 sources/requirements retained. Actual dispatch, current surface schema and both terminal structuredContent/canonical text fallback were exercised.
- Scope: **61 changed paths**, **2566 unchanged baseline paths**, syntax PASS for **51 modules**, whitespace PASS.

## R9 — Closed by actual injection → public dispatch → observer reproduction

Correction: `eval/task_level/conditions.py:180` now advertises `context_format="patch_context"`, not removed `delivery_strategy`. Actual active injection remains `eval/task_level/_execution_part04.py:228-229`; Codex metadata consumes it at `eval/task_level/runners/codex.py:412-427`.

Independently executed an inline Python command with the same `PYTHONPATH`, bytecode setting and interpreter. It:

1. Read/parsed the actual `_execution_part04.py` AST and located its sole `if ...require_docatlas_call_before_edit` branch.
2. Executed that exact branch with the real `CONDITIONS`, real `TOOL_REQUIRED_ONCE_INSTRUCTION`, condition `docatlas_tool_required_once` and original question `Inspect protocol implementations`.
3. Parsed the injected `- key="value"` argument lines, replacing only the documented `<original task objective>` placeholder with that unchanged question.
4. Obtained `current_docs_surface(env={})`, validated the parsed arguments against its actual tool input schema and called real `call_docs_tool_payload` with a NEW offline 12-source necessary-evidence fixture.
5. Validated the actual result against the current output schema; independently checked core v4 validation with the same `project_path='.'` after refreshing the core-only estimate, exact source hashes and final serialization estimate.
6. Passed the real public result and the parsed input arguments into `_required_once_retrieval_metadata`.

Actual independently produced arguments:

```json
{"context_format":"patch_context","project_path":".","question":"Inspect protocol implementations"}
```

Actual result: **v4 `patch_context`, `result=data`, `completeness=complete`, `edit_ready=false`, 12 sources, 55910 UTF-8 bytes, 13978 estimated tokens, exactly one offline retrieval call**. The estimate matches compact sorted UTF-8 serialization; full source text hashes validate.

Actual metadata:

```json
{"action_packet_completeness":"complete","action_packet_result":"data","context_format":"patch_context","question":"Inspect protocol implementations","question_matches_task_objective":true,"retrieval_succeeded":true}
```

The injected prompt still says `` `get_docs_context` exactly once `` and starts with the original question. This reproduction exercises the active injection statement and real current dispatch/observer, not a manually substituted hosted adapter or only the added regression's green status.

Negative control: sending the old advertised `delivery_strategy='bounded_direct'` to the same real surface still returns `validation_error` before any retrieval. No legacy adapter or unknown-argument ignoring was introduced.

**Invariant satisfied:** active required-once instructions use the actual explicit read-only v4 ingress; successful retrieval does not grant editing/workflow permission.

## Preservation and bounded final status

- Independently compared current `conditions.py` to its `50c6bb24` blob. Replacing just the new instruction line with the old line reproduces the previous file byte-for-byte. Thus every other condition definition, count, numeric threshold and instruction byte in that file is unchanged.
- Production/eval changed-path assertion yields only `['eval/task_level/conditions.py']`. No core, provider-history, other-condition or threshold correction was made in this final delta. The existing NEW docs/profile/transport/role/binding/nonauthorization regressions all pass; R1–R8 remain closed rather than being reopened by this instruction change.
- Initial integration status showed coordinator work on `v2plan/action-packet-v4/FINAL_REPORT_RU.md`. It was neither edited nor reverted by R and is not evidence for this gate. Coordinator documentation update remains separate from production changes.
- Primary read-only check: HEAD remains `b89fa3cc16534445501bab14e0d63e099e9f61f6`; status remains solely pre-existing `?? v2plan/artifacts/`. Those artifacts were not opened/modified. Approved changed-path verification passes; no historical tests/gold/threshold/report/WIP/removal-artifact changes were made by this review.
- No residual finding reproduced in this narrow final delta. The previously identified active API instruction blocker R9 is closed; R1–R8 closures are preserved. Historical workflow conditions remain explicitly unsupported/fail-closed where v4 cannot establish their requirements; green interface tests do not establish historical score acceptance.
- External transport/model capacity, live-provider behavior, wheels/installed-package parity, deployed index/corpus parity and historical evaluation acceptance remain **UNKNOWN**. No full release/security proof or global mathematical minimization claim is made.

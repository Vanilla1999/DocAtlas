# ActionPacket v4 contract (coordination version 1)

Base: `b89fa3cc16534445501bab14e0d63e099e9f61f6`.
Implementation is offline and isolated under `/tmp/opencode/`.

## Wire contract

Required common fields: `schema_version: 4`, `result: data|failure`,
`completeness: complete|partial|unavailable`, `edit_ready: false`,
`estimated_tokens: positive integer`. No field grants workflow/edit permission.

Data additionally requires a nonempty `sources` array. Each source has
`evidence_id` (existing ActionPacket evidence identity), `stable_id` (selector
identity), `path`, `symbol_or_section`, `authority`, `instruction_trust:
untrusted_data`, `scope`, `version_binding`, `text`, `content_sha256` (SHA256 of
the exact UTF-8 text). Non-null `char_start`, `char_end`, `line_start`, `line_end`
are included when supplied by the admitted selector candidate. Text is the
whole admitted display window, never a size-cropped snippet. Attribution and
offsets must match the admitted retrieval window; caller hashes/spans cannot
be trusted blindly.

Optional nonempty fields common to either result:
- `requirements`: selector requirements serialized from the canonical DTO,
  omitting null/empty fields only (not changing values). Retain IDs, kinds,
  explicit values, provenance and proof roles; no prose-derived new obligations.
- `missing`: sorted unique machine requirement/retrieval reason strings.
- `mutation_intent`: explicitly supplied mutation contract only, with lossless
  target, destination, acceptance and request-plan content; omit empty/null
  sections, never slice data. Resolution/readiness cannot grant permission.

Data may also have nonempty `assignments`: canonical selector assignment rows,
omitting null/empty fields; assignment evidence IDs reference source `stable_id`.
Keep unit hashes/spans and proof roles. Validate bindings against visible data
and canonical inputs. Failure requires nonempty `missing`, no sources or
assignments, and `completeness: unavailable`. Partial data requires nonempty
missing. Complete data has no missing and covers all canonical mandatory
requirements with valid assignments. Without explicit content obligations,
retain the existing admitted relevance selection and fail closed on the
selector's missing-content-assignment verdict (useful data remains partial).
Absence means no supplied value/claim, never authorization.

No duplicated objective/task scaffold or empty policy/check/target sections.
No legacy v3 adapter. Strict schema, binding and trust validation remain.
Serialization for both packet and final patch projection: UTF-8
`json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"))`.
Estimator: ceil(serialized bytes / 4), minimum 1; refresh to a fixed point
including the estimate itself after every public metadata change.

## Interfaces

`build_action_packet` retains explicit keyword inputs except `max_tokens`
(removed), returns v4. `validate_action_packet` retains evidence_items,
project_path/module_path inputs, removes max_tokens. Existing exported
evidence identity helper remains available. Export canonical serialization and
estimate refresh helpers for C to reuse, with names recorded in A handoff.
`patch_selection_config()` takes no budget. SelectionConfig patch limits use
None, not infinity/large sentinels. Docs profiles retain existing budgets.

`project_patch_context(packet=..., evidence_items=...)` takes no max_tokens,
returns (final v4 plus `kind: patch_context`, internal snapshot).
Final projection may add only necessary explicit non-authorizing recovery
metadata; do not replace partial data, slice explicit values, or call legacy
insufficient compaction. `validate_model_visible_projection` keeps docs
budget checks but supports patch with no max_tokens; strictly validate v4
and bindings plus allowed public recovery fields, ignoring no invalid fields.

## Selection

Preserve eligibility/scope/version/freshness/identity guards. Remove patch-only
token target/hard/reserve, candidate/source/items/spans representation caps,
budget-fit gates and length-dependent utility cutoffs. Do not expand retrieval.
Deterministic stable ordering and existing non-size-based relevance admission;
no NL sufficiency classifier. Eliminate only mechanically interchangeable
exact duplicates with equivalent identity, attribution, scope/version and
coverage. Similar bytes or shared parents alone do not prove equivalence.
Retain distinct admitted evidence, especially necessary witnesses.

## Initial limit inventory

| Location | Limit | Decision |
|---|---|---|
| _action_packet_shared | 128/1500/2000; estimated schema max | remove |
| _action_packet_part03 | fit/remove/compact; objective/issue slicing | remove on new packet path |
| _action_packet_part01/02 | snippet clipping and source identifier representation bounds | remove from active v4 path; preserve unrelated technical validation |
| _evidence_selection_part01 | patch 256/1200/2000/reserve/source item limits | remove patch only |
| evidence_models/selection parts | candidate/document/span limits; cost-based utility and fit gates | optional None patch only; docs unchanged |
| model_visible_projection | patch cap, optional shedding, partial -> empty failure | remove patch only |
| MCP context_tools | packet budget, repeated failure compaction, recovery hint slicing | remove patch only; preserve docs policies |
| mutation_intent DTO/request-plan constructors | domain input bounds | inspect; do not silently slice explicit packet inputs; report blockers |
| retrieval/corpus/stage guards | search scope and runtime guards | retain; no rebuild or scan expansion |

## Ownership (exact write allowlists)

A: `docmancer/docs/application/action_packet.py`,
`docmancer/docs/application/_action_packet_shared.py`,
`docmancer/docs/application/_action_packet_part01.py`,
`docmancer/docs/application/_action_packet_part02.py`,
`docmancer/docs/application/_action_packet_part03.py`,
`docmancer/docs/application/_action_packet_part04.py`,
`tests/test_action_packet_v4_contract.py`.

B: `docmancer/docs/application/evidence_models.py`,
`docmancer/docs/application/evidence_requirements.py`,
`docmancer/docs/application/evidence_selection.py`,
`docmancer/docs/application/_evidence_selection_shared.py`,
`docmancer/docs/application/_evidence_selection_part01.py`,
`docmancer/docs/application/_evidence_selection_part02.py`,
`docmancer/docs/application/_evidence_selection_part03.py`,
`tests/test_action_packet_v4_selection.py`.

C: `docmancer/docs/application/model_visible_projection.py`,
`docmancer/docs/interfaces/mcp/context_tools.py`,
`tests/test_action_packet_v4_public.py`.

Coordinator: this new contract, new verification/report files under
`v2plan/action-packet-v4/`, and new `tests/test_action_packet_v4_integrated.py`.
Any other production dependency requires a coordinator-approved ownership
extension. No overlapping writes, old tests/conftest/gold/reports/artifacts edits.

## Verification and execution boundaries

Create/run only new targeted tests. Existing tests may be read as interface
examples but not modified/run. No network/provider calls, install/reinstall,
index rebuild, runtime scan expansion, extra dependencies, nested subagents,
push or main-branch merge. NEXT06/NEXT07 0ce30227 and artifacts untouched.
Tests use separate temp directories; source code must import from worktree.
Keep useful partial evidence, explicit constraints, Unicode/long identifiers,
hash/span fidelity, deterministic ordering and strict nonauthorization.
Exercise actual unique necessary data >2000 estimated tokens through final
MCP; no padding fixture. Check unrelated docs profiles with NEW tests.

Workers commit only allowlisted changes and report base/worktree/branch,
commit, files, contract coverage, commands/exit/results, dependency requests,
limitations/blockers. R independently reviews integrated diff and reproduces
key tests; R edits no production code.

### Coordinator dependency amendment 1

B additionally owns `evidence_requirements.py`: its explicit path/public
requirement bounds currently slice at 12 and insert an input_limit reason.
For patch selection preserve the entire explicit contract (a deliberate
patch-only flag on build_requirements is permitted, default docs behavior
unchanged). B communicates the exact parameter to A. Do not enlarge the
retrieval universe or remove docs input guards. A must avoid the lossy
with_explicit_path_targets helper for bare required_target_paths; preserve
these through selector obligations instead. Supplied MutationIntentContract
constructor rejecting domain guards remain unchanged; no serializer slicing.

### Coordinator dependency amendment 2

Normal test infrastructure requires new hash-bound diagnostic extension
shards. Approved additional ownership: A/B/C respectively
`tests/diagnostic_labels.action_packet_v4_a.json`,
`tests/diagnostic_labels.action_packet_v4_b.json`,
`tests/diagnostic_labels.action_packet_v4_c.json`. Coordinator owns
`tests/diagnostic_labels.action_packet_v4_integrated.json`. Shards label only
new tests; old inventory and conftest remain unchanged. Use the existing
`/home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python` interpreter,
`PYTHONPATH=.` from each worktree, no installation or network.

### Coordinator dependency amendment 3

C additionally owns `docmancer/docs/interfaces/mcp/output_contract.py` and
`docmancer/mcp/_docs_server_part01.py`. Terminal dispatch and CallToolResult
repeat internal `compact_mcp_payload`; its default 32000-byte cap replaces
patch projections with transport_size_limit. Bypass that arbitrary internal
representation ceiling for finalized v4 patch projections only; docs/error
paths remain unchanged. Patch JSON text fallback uses the same compact sorted
UTF-8 serialization as the estimator. Test necessary unique evidence beyond
32000 bytes through both terminal structuredContent and fallback text, not
only handler/projector. Actual external transport capacity remains unknown.

### Coordinator dependency amendment 4

B additionally owns `docmancer/docs/application/evidence_candidates.py`,
`docmancer/docs/domain/_answer_units_shared.py`,
`docmancer/docs/domain/_answer_units_part01.py`, and
`docmancer/docs/domain/_answer_units_part02.py`. Patch normalization must not
silently clip witness units at 1500 characters / 64 units (nor disguise these
as run-count limits). Add patch-specific unbounded extraction behavior while
retaining default docs extraction. Long and late exact explicit witnesses
must remain coverable; hash/span/identity validation remains mandatory.

### Coordinator dependency amendment 5 — user-approved ingress

Inspection showed public patch_context was unreachable: handler initialized
kind to docs_answer and never switched to patch. User explicitly approved an
optional `get_docs_context(context_format="patch_context")`; absent parameter
keeps existing docs routing. It selects only non-authorizing presentation,
never mutation permission, retrieval widening, or inferred operation.
Unsupported supplied values must reject rather than silently default.
C additionally owns `docmancer/mcp/_docs_server_tool_data.py` and
`docmancer/mcp/_docs_server_schema.py` for actual public input and output
schemas. Output uses a discriminated v4 patch alternative, not legacy status
scaffold. Tests activate the actual dispatch with the explicit input, including
operational failures and final terminal structuredContent/text fallback.

### Coordinator dependency amendment 6 — patch coordinate fidelity

B inspects/fixes patch-only assignment end lines: a multi-line witness/hash
must not advertise start-only line coverage. Patch supplied character-window
length must equal the admitted display window length. Preserve docs-specific
coordinate behavior and parent authenticity caveats; no permission inferred.

### Coordinator dependency amendment 7 — user-approved eval migration

User explicitly approved surgical active eval-code migration and NEW offline
smoke tests. Historical tests/gold/thresholds/reports remain unchanged and
historical evaluations are not run; their acceptance remains UNKNOWN.
C additionally owns `eval/evidence_selection_quality.py`,
`eval/answer_quality_runner.py`, `eval/task_level/_github_models_shared.py`,
`eval/task_level/_github_models_part01.py`,
`eval/task_level/task33_validation.py`,
`eval/task_level/task33_codex_exploratory.py`,
`eval/task_level/runners/codex.py`, `eval/task_level/_execution_part03.py`,
`eval/task_level/_isolated_delivery_shared.py`,
`eval/task_level/_isolated_delivery_part02.py`, plus new
`tests/test_action_packet_v4_eval.py` and
`tests/diagnostic_labels.action_packet_v4_eval.json`. Migrate producer API
calls and v3 field reads, not old score expectations. Evaluation-only frozen
budget assertions are not runtime caps and must not re-enter v4 producers.
Unsupported historical normative/workflow requirements stay fail-closed.

### Coordinator dependency amendment 8 — rooted projection binding

Coordinator reproduced a valid catalog-bound packet being discarded by
projector re-validation without the builder's project_path/module_path.
`project_patch_context` additionally accepts these optional scope inputs;
MCP passes the same explicit scope throughout. Internal snapshots retain the
revalidation scope, and model-visible validation reuses it. Do not resolve the
mismatch by disabling source attribution checks or treating authority as
permission. C owns the narrow fix and new regression within existing files.

### Coordinator dependency amendment 9 — independent review closure

R's immutable initial report records six findings at 04b35923. B owns R1
(restore explicit rejected-source admission guard) and R3 (binding validation
must enforce the selector's proof-role admission). A owns R4 (stable-identity
collision rejection), R5 (all explicit mutation resolution binding kinds
require actual canonical local evidence) and R6 (retained plan/explicit mutation
requirements cannot disappear from completeness checks). C owns rooted R2.
`validate_assignment_binding` gains optional keyword `requirements=()`;
A passes canonical requirements, B canonical validation passes its whole set,
C's existing docs-assignment check passes decision.requirements. Contextual
roles fail closed without scope, never grant by missing data. Add new regression
tests to existing NEW suites and preserve historical tests. R re-reviews all
integrated corrections plus the pending eval migration; worker claims alone
do not close findings.

### Coordinator additional reproduction R7

Patch requirement dedupe used value.casefold(), erasing one of explicit
required_fact values `Cache enabled.` / `cache enabled.` while claiming
complete. These distinct literal obligations are not interchangeable.
B owns patch-only lossless literal/provenance dedupe correction; coordinator
adds a cross-layer regression. Default docs policy stays unchanged. R must
independently verify this closure along with its six original findings.

### Coordinator additional reproduction R8

Distinct indexed windows with the same path/text/line coordinates but
different stable IDs and character offsets shared the legacy ev identity.
Both windows were admitted, but the ev-keyed public snapshot overwrote one.
A owns binding ev identity to normalized stable identity and exact character
window, and strict duplicate ev-ID rejection; no legacy ABI guarantee. C
consumes the same exported identity helper, never drops distinct windows or
loosens snapshot checks. Coordinator adds a public projection regression.

### Coordinator dependency amendment 10 — indirect eval source ownership

C additionally owns the ten reported indirect active consumers:
`eval/answer_quality_gate.py`, `eval/task_level/_execution_part01.py`,
`eval/task_level/_execution_part02.py`, `eval/task_level/_execution_part04.py`,
`eval/task_level/_one_call_agent_loop_core.py`,
`eval/task_level/_github_models_part02.py`,
`eval/task_level/evaluators/actionability.py`,
`eval/task_level/evaluators/docatlas_utilization.py`,
`eval/task_level/evaluators/policy.py`, and `eval/task_level/task33_pilot.py`.
No changes to frozen historical threshold values/tests/gold or evaluator runs.
New smoke coverage stays in the already owned NEW eval suite/shard.

### Coordinator dependency amendment 11 — final active delivery consumers

C additionally owns `eval/task_level/report.py` and
`eval/task_level/_execution_shared.py`; `_github_models_part01.py` is already
owned. Finalized v4 evidence must survive evaluator/provider message composing
and history selection without internal string clipping or dropping necessary
packet messages. This is verified offline, not through provider calls.
Historical workflow rules remain explicitly unsupported/fail-closed and their
threshold values unchanged. Status reporting reads v4 result/completeness.
Actual external model capacity and historical actor acceptance stay UNKNOWN.

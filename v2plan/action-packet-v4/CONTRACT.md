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

# Independent review R — integrated ActionPacket v4 core

**Outcome: six unresolved findings.** The 106 new targeted tests pass, but deeper negative reproductions expose evidence-admission, projection and binding-validation gaps. This is not a release or security certification.

## Scope and execution

- Worktree: `/tmp/opencode/action-packet-v4-integration`.
- Reviewed HEAD: `04b359235855193fa6fdaa1615b1b0b7de408b97`.
- Base: `b89fa3cc16534445501bab14e0d63e099e9f61f6`.
- Read the entire `CONTRACT.md`, including ownership and all seven amendments. Independently inspected `git diff b89fa3cc..HEAD`, production changes and all four new test modules, not worker reports.
- Production and tests were read-only. No nested agents, provider/network calls, installation, indexing, corpus expansion, historical-suite execution, or artifact modifications. Only this new report was written.
- The active eval consumer migration is an explicitly known pending dependency, not a finding against this HEAD. Its later integrated delta needs follow-up review.

Commands executed from the integration worktree:

```sh
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python -m pytest tests/test_action_packet_v4_contract.py tests/test_action_packet_v4_selection.py tests/test_action_packet_v4_public.py tests/test_action_packet_v4_integrated.py --basetemp /tmp/opencode/action-packet-v4-r-tests -o cache_dir=/tmp/opencode/action-packet-v4-r-cache
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python v2plan/action-packet-v4/VERIFY_EXAMPLES.py
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python v2plan/action-packet-v4/VERIFY_SCOPE.py
```

Actual results, all exit 0:

- Normal conftest pytest: **106 passed in 3.63s**.
- Examples: empty failure 205 bytes/52 tokens; partial data 1665/417; small complete 1369/343; unique necessary evidence 26171/6543, all 18 requirements and sources retained. All four PASS through real `call_docs_tool_payload`, current surface output schema, structuredContent and canonical JSON fallback.
- Scope: 32 changed paths within ownership; 2589 unchanged baseline paths; syntax PASS for 37 modules; diff whitespace PASS.
- New public transport test also passes with necessary evidence exceeding 32000 bytes through dispatch and both terminal modes.
- Integration `git status --short` was empty before this report. Read-only primary-worktree status showed only `?? v2plan/artifacts/`; these pre-existing/unfamiliar artifacts were neither opened nor changed. Primary branch HEAD remains the stated source base. This status alone is not a historical artifact parity proof.

The additional negative checks below were executed as inline Python with the same interpreter/environment, using `runpy.run_path('tests/test_action_packet_v4_contract.py')` to reuse only the NEW `_canonical_packet` and `_evidence` fixtures. They do not invoke historical tests.

## Findings

### R1 — High: rejected sources re-enter admitted patch evidence

**Location:** `docmancer/docs/application/_action_packet_part03.py:81-84`; `docmancer/docs/application/_evidence_selection_part01.py:453-488`.

The replacement builder delegates admission to `select_evidence`, but its eligibility function never consumes `trust_contract`. The old builder subsequently applied `_rank_and_dedupe`, whose rejection guard at `_action_packet_part01.py:291` is no longer reachable from v4. Consequently an explicitly rejected source can supply a complete packet and reach public MCP.

**Reproduction:** with the new fixture's `e`, call:

```python
trust = {'sources': {'rejected': [e[0]['path']]}}
q = build_action_packet(question='cache', context_pack=e,
    trust_contract=trust, public_requirements=(e[0]['content'],))
```

Actual result: `data complete ['docs/cache.md']`; `validate_action_packet(q, evidence_items=e)` returns `[]`. An offline service returning `status='success'`, this context pack, trust contract and public requirement, passed through `handle_context_tool` with explicit `context_format='patch_context'`, also returns `data complete ['docs/cache.md']`.

**Invariant:** preserve eligibility/scope/trust guards; only admitted evidence can survive. Removing size limits must not remove explicit rejection. Restore rejection independently of lossy legacy rendering/deduplication.

### R2 — High: projector loses project/module authority inputs and discards valid evidence

**Location:** `docmancer/docs/application/model_visible_projection.py:617-626`, `:697`; `docmancer/docs/interfaces/mcp/context_tools.py:561-564`.

The handler builds and validates using `project_path`/`module_path`, but the projector revalidates with only evidence items; its snapshot likewise does not retain the authority context for final validation. `_effective_authority` is context-dependent. A valid supporting project document can be reinterpreted as canonical without the supplied project root and rejected for attribution mismatch, replacing useful complete/partial evidence with empty failure.

**Reproduction actually executed:** use `_evidence()` (canonical-declared `project_doc`) and the existing empty test root `/tmp/opencode/action-packet-v4-r-tests`:

```python
p = build_action_packet(question='cache', context_pack=e,
    project_path=root, public_requirements=(e[0]['content'],))
validate_action_packet(p, evidence_items=e, project_path=root)  # []
validate_action_packet(p, evidence_items=e)  # source differs from bound retrieval window
project_patch_context(packet=p, evidence_items=e)
```

Builder authority is `supporting`; valid-with-root errors are `[]`. Projector returns `failure/unavailable`, no sources, `missing=['invalid_action_packet']`, estimate 42. The same offline raw result through public handler with `project_path=root` reproduces this empty failure.

**Invariant:** attribution must match admitted retrieval windows; projection must retain useful admitted evidence. Carry canonical authority context into projector/snapshot validation, or retain a validated canonical normalization rather than recomputing under different inputs.

**Coordination status:** independently reproduced by R before receiving the coordinator's matching rooted-catalog reproduction. The coordinator subsequently reports that C is fixing scope threading and snapshot fidelity. That fix is pending, not present/verified at reviewed HEAD; re-review the final integrated delta before closing R2.

### R3 — High: assignment validator accepts proof roles the selector forbids

**Location:** `docmancer/docs/application/_action_packet_part04.py:101-107`; `docmancer/docs/application/_evidence_selection_part01.py:127-135`. Compare selector restrictions in `_evidence_selection_part03.py:542-557`.

Validation verifies that assignment and requirement proof-role strings agree, but does not enforce selector admission restrictions for that role. A matching literal can therefore be represented as a valid `project_rule`, implementation fact from a project document, unbound dependency fact, or unscoped document statement, even when canonical requirements are independently supplied.

**Reproduction:** take new `_canonical_packet()` and change BOTH `requirements[0]['proof_role']` and `assignments[0]['proof_role']` to `project_rule`, refreshing the estimate. Supply the corresponding `EvidenceRequirementSet` made with `dataclasses.replace`.

Actual validator errors: `[]`. Selecting the same evidence against those same canonical requirements reports the requirement missing plus `visible_content_assignment_required`. The same mismatch was reproduced for `implementation_fact`, `dependency_fact` and `document_statement`. The forged `project_rule` packet survives `project_patch_context` as `data complete` and final `validate_model_visible_projection` returns `[]`.

**Invariant:** strict trust/proof-role binding; document data cannot become normative proof through relabeling. `edit_ready` stays false, so this is not a demonstrated execution-permission grant. Validation must enforce the same role eligibility as canonical selection, not just literal/hash equality.

### R4 — Medium: validator resolves conflicting stable identities by input order

**Location:** `docmancer/docs/application/_action_packet_part04.py:87-100`.

`by_candidate` silently overwrites earlier candidates sharing a stable ID. Unlike the selector's new collision guard, validation does not reject conflicting attribution/span bindings. A packet referencing the last row is accepted even though neither conflicting row would be admitted by canonical selection.

**Reproduction:** set fixture `e[0]['stable_id']` to the packet source's stable ID; create `bad={**e[0], 'path':'docs/other.md'}` and validate the unchanged packet with `evidence_items=[bad,e[0]]`.

Actual validation errors: `[]`; builder against these inputs reports `stable_identity_collision:<stable_id>` and no admitted evidence. Projector/final validation also accepts `data complete`/`[]`. The overwrite makes acceptance depend on evidence ordering.

**Invariant:** same stable identity with differing attribution/spans must fail closed; deterministic identity binding must match canonical selection. Reuse equivalent collision validation before constructing the lookup map.

### R5 — Medium: non-target mutation binding assertions lack evidence integrity checks

**Location:** `docmancer/docs/application/_action_packet_part04.py:146-166`.

Only `binding_kind == 'target' and exists` receives path/request/symbol checks. `parent_context`, `destination_context`, and other false-existence claims need only name a visible evidence ID; fabricated paths and collision-free assertions are accepted. Matching an externally supplied contract hash proves serialization fidelity, not that its resolution assertions are evidence-backed.

**Reproduction:** attach a correctly hashed `MutationIntentContract('create','source',...)` requesting/destined for `src/new.py`, with a `ResolvedTarget` referencing the cache documentation evidence ID but `path='invented/unrelated.py'`, `exists=False`, `collision_free=True`, and either `parent_context` or `destination_context`.

Actual validation errors with `evidence_items=e` AND `mutation_intent_contract=c`: `[]` for each variant. A contract with both forged bindings also survives projector/final validation as `data complete`/`[]`.

**Invariant:** mutation bindings must be validated against visible data/canonical inputs; absence is not authorization or collision-freedom. Validate each binding kind's actual local structure/collision evidence and request association. No actual edit authorization is granted by this demonstration.

### R6 — Medium: complete packet may omit mandatory obligations derivable from its own request plan

**Location:** `docmancer/docs/application/_action_packet_part04.py:113-145`.

Coverage uses only the requirements currently serialized in the packet. Request-plan validation checks hashes and polarity but never checks that its canonical selector obligations are present. A packet can retain a valid explicit plan for an absent mutation target while claiming completeness using unrelated literal evidence.

**Reproduction:** attach a valid hashed plan/contract for modifying `src/missing.py` to `_canonical_packet()` without adding any plan-derived requirements. `build_patch_evidence_requirements(plan)` returns mandatory `patch:target_declaration:0:4c49d89bacfb`, which is absent from the packet.

Actual `validate_action_packet(q, evidence_items=e, mutation_intent_contract=c)` errors: `[]`. Projector returns `data complete`; final validation errors: `[]`. Thus even supplied canonical mutation input does not force its mandatory requirement into the completeness check.

**Invariant:** complete means covering all canonical mandatory requirements, including obligations deterministically derived from the retained explicit plan. Regenerate/check these requirements during validation; require explicit target obligations as the builder does. This is distinct from omissions of an entirely external requirement set: supplying the validator's `requirements` parameter does detect those omissions.

## Positive checks and limits

- The explicit public patch route is reachable and advertised with a v4 discriminated output alternative. Omitted/null ingress remains docs routing; unsupported formats reject. No active legacy-v3 adapter was found on this route.
- No hidden/default patch representation token/byte/count ceiling was found along the inspected selector, builder, validator, projector, dispatch and terminal transport path. Patch limits are `None`; cost/length fit gates are bypassed; full selected windows and late/long witnesses survive the NEW tests. Remaining ingress retrieval/runtime guards are intentionally unchanged, not representation-cap removal claims.
- Mutation DTO/request-plan constructors retain their existing domain count rejection guards. The v4 serializer does not call the lossy legacy target augmentation/parser or slice explicit DTO fields.
- New tests cover strict schema types/unknown fields, hashes/coordinates, literal witnesses, useful partial data, duplicate permutations, explicit requirement retention, non-authorizing recovery and final metadata estimates. Recovery `auto_execute=True`, extra permission/workflow fields and mismatched snapshots reject in those tests. The findings above identify deeper cases beyond those checks.
- Default docs profile budgets and extraction limits pass the NEW regression checks; this is bounded evidence of preservation, not exhaustive product compatibility.
- External transport capacity, packaged wheels/import parity, index/corpus parity, historical eval acceptance and pending ACTIVE eval migration are **UNKNOWN/not reviewed here**. No global mathematical minimization, full-product release readiness, or security proof is claimed.
- All six findings remain unresolved at reviewed HEAD; no production/test fixes were made by R.

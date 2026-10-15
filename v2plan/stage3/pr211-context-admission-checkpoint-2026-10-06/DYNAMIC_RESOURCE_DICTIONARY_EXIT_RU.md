# Dynamic resource renderer: final disjoint delivered-policy allocation

2026-10-06, primary `/tmp/opencode/docatlas-stage3-integration-active`.
**Scoped implementation complete / independent review pending; full dictionary exit NOT DONE.**
First/second reviewed production/tests не изменялись. Legacy proof и corpus
locale/topic exclusions по-прежнему OPEN/BLOCKED. Network/commit/push не выполнялись.

## Exact files

- Production: только `docmancer/mcp/_docs_server_part01.py`, две dynamic branches
  внутри `read_docs_resource`.
- New `tests/test_dictionary_exit_dynamic_resources.py`.
- New `tests/diagnostic_labels.dictionary_exit_dynamic_resources.json`.
- Этот новый checkpoint report.

Не менялись schemas, tool names/order, feature flags, URI identities, static
catalog/resource texts, source continuation execution, lifecycle/job execution,
old tests/gold/frozen artifacts/thresholds или reviewed first/second slices.

## Rules / removal

| Dynamic route | До | Теперь |
|---|---|---|
| `docmancer://workflow/project-docs/{project_path}` | Non-public mode=auto; immediate preparation/retry | Только public `get_docs_context(project_path=..., question=...)`, original question placeholder, explicit optional bindings; no guessed scope. |
| `docmancer://library/{ecosystem}/{library}/{version}` | Non-public ecosystem/mode on context call; missing/stale+approval→prefetch; unconditional retry | Только public `question`, `library`, `version`. Ecosystem сохранён как untrusted locator metadata, не argument и не authority. No executable preparation example. |
| Оба renderer bodies | Source/URI text мог попасть в Markdown/code как instructions/arguments | JSON-quoted literals, Unicode/control escaping и backtick→Unicode escape. AST/JSON round-trip сохраняет исходные locator values; `question` всегда caller-supplied placeholder. |
| Lifecycle guidance | Inferred preparation и success-unchecked retry | Только explicit user lifecycle request или actual returned typed recommended_next_action, exact arguments, network consent/confirmation и existing budgets. Missing/stale и network approval сами не authorization. |
| Async/retry | Immediate/unconditional retry | Returned job_id status, authoritative terminal success + readiness, максимум один unchanged bounded retry; no running/failed/cancelled retry или polling/retry loops. |
| Authority | Неявный readiness/context shortcut | Stop on hard_stop, unresolved readiness/authorization, missing approval/uncertain binding. Flags/context/lookup coverage не answer proof или edit readiness; mutation requires separate explicit target/authorization. |

Guidance остаётся read-only: resource reads не вызывают tools/network/service.
URI parser/returned URI/name/mimeType сохранены; никакой topic/language dictionary
не перенесён в новые prompts. Question не выводится из locator metadata.
Explicit version/path/project/library provenance, lockfile requery и ≤5 explicit
same-question lookups сохранены; URI version alone не current/exact snapshot proof.

## Tests / normal conftest / new-only shard

Environment: `PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1`,
`.venv/bin/python -m pytest -p no:cacheprovider`. `--noconftest` не использовался.

| Проверка | Result |
|---|---|
| New dynamic module | **27 PASS**: 19 behavioral / 8 schema instances; 6 base nodeids. |
| New + bounded technical selection | **76 PASS / 1 FAIL** внутри combined run. |
| Old mixed selection | **64 PASS / 27 FAIL** внутри combined run. |
| Combined | **140 PASS / 28 FAIL**, 1 existing multipart deprecation warning; RED не переименован в PASS. |

New node hash:
`310c99991a1c13339143f1ecfd7f7316a38f39496fe45b23d33a9b12cb17792d`.

Behavioral tests реально вызывают `docs_server.read_docs_resource`: 16 poison
round-trips (project/library/ecosystem/version × quotes/backticks/newlines/Unicode),
2 no-tool/no-service reads, 1 static/catalog/contract/source-reference invariance.
Schema cases: 4 parsed actual examples validated against runtime public schema
and explicit allowed-property membership; 4 lifecycle/source guidance shape
checks. Последние не доказывают authorization enforcement исполнения jobs/edits.
Poison inputs не генерируют вопрос/kwargs, ecosystem metadata JSON round-trips;
raw Markdown/code injection не воспроизводится в resource body.

Bounded technical suites:

- `tests/docs/test_mcp_token_footprint.py`
- `tests/docs/test_mcp_boundary.py`
- `tests/docs/test_finalized_mcp_output_integrity.py`
- `tests/test_support_surface_policy.py`

Technical-selection red:
`test_mcp_boundary.py::test_patch_constraints_debug_compaction_preserves_contract_fields`
ожидает answer_available=True, current non-owned patch path возвращает False.
Этот же red записан во second-slice report; здесь не исправлялся и не скрывался.

Old mixed suites:
`tests/docs/test_mcp_docs_tools_registration.py`, `test_active_mcp_examples.py`,
`test_host_scope_contract.py`, `test_host_scope_planning_contract.py`,
`test_agent_question_planning_contract.py`, `test_agent_recovery_version_guidance.py`,
`test_bounded_response_docs_parity.py`, `test_readme_mcp_keyword_contract.py`,
`test_tdd_documented_request.py`, `test_self_host_agent_contract_surface.py`,
`tests/test_unified_docs_context_mcp.py`.

Combined failing node IDs совпадают с последним second-slice run: removed
semantic-policy expectations, first-slice template fields, module/self-host
availability и legacy Kotlin/project recovery. Это bounded observed comparison,
не full baseline causality/quality approval. Old assertions не менялись.

## Technical identity / pins

- Default catalog остаётся **6126 bytes** (existing target ≤6144), schemas unchanged.
- Actual runtime agent identity unchanged:
  `sha256:3268e3d9e5c16994905c23b23dc641a4733ec725067a8d0b7e067ee873e5046d`.
  Dynamic body texts не входят в этот tool/workflow identity; это не hash полного
  resources/read output и не release/exit approval.
- `_docs_server_part01.py` SHA-256:
  `51e096bafc8a3a9b901c4b26764ebf85979f4aacc40f5d8b8928a2632405efec`.
- New test source SHA-256:
  `57f6bb681ed60ccb2d4c4e8606de0242f05dbc6ba73da6192efb36d7033e87e7`.
- New shard SHA-256:
  `021a98d36f5a30642b1f539a4af6c9c3e9c55511471ea137fd51f0810ba64c5a`.

## Remaining OPEN / parent dependencies

1. Dynamic renderer dependency из second-slice report реализована в этом allocation;
   parent должен провести scoped independent review, не объявлять full exit.
2. Actual lifecycle/source-read authorization/budgets remain existing execution
   contracts; новые текстовые guards не являются replacement proof этих механизмов.
3. Existing patch-boundary red относится к другому allocation и остаётся reported.
4. Legacy proof/corpus exclusions/discovery и other maintained/package/install
   surfaces не очищены этим change. Frozen quality reds остаются; full CI/stdio
   smoke/self-host quality rebuild не запускались. No schema broadening для legacy
   examples; no inferred preparation, source scope или answer/edit authority.

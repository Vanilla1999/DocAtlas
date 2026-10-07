# FOLLOWUP: raw SDK inert-data closure — bounded, review pending

2026-10-07. Только `/tmp/opencode/docatlas-resumed-inert-ee156cba`.
Baseline `ee156cba4cc6dd4bf51c0e2c8adf44907aac9633`, поверх frozen B slice.
**Scope: ровно 6 follow-up файлов, НЕ 8:** 3 production updates + 1 new test
module + 1 new diagnostic shard + этот new root report. Production diff:
3 files, 40 insertions / 20 deletions (проверить final git diff при extraction).
Предыдущие B files/tests/root report НЕ редактировались. Их 14 pinned production/
test/shard files сверены: **14/14 match**. Frozen B root report SHA256:
`f7d612cce38933797a75eb10981f79d46fbfc380e3b0e7c95c4ba8abc7561803`.

**Owned reported dependency CLOSED bounded:** raw `UnifiedDocsContextService`
не превращает typed operation + retrieved `answer_completeness.edit_ready=True`
в current edit permission. **Independent parent review PENDING. Full EXIT/security/
quality acceptance NO.** NL veto retained; никакой capability broker/authentication
fiction/consent fabrication/dispatcher/new execution не добавлено.

## Production changes / actual consumers

1. `application/_unified_context_service_part01.py::get_docs_context`:
   top-level `UnifiedDocsContextResult.edit_ready=False` всегда в aggregation return.
   Retrieved `answer_completeness` копируется с `edit_ready=False`; тот же безопасный
   copy применяется к `details=True` project lane diagnostics. Upstream object
   не мутируется. `mutation_ready`, explicit mutation DTO identity/resolved source
   targets, source_search_status и иные DTO fields остаются evidence/intent data,
   не permission. Current authorization отсутствует — edit denied.
   Context pack, original quote/hash/span/version/root identity, support/selection/
   assignment/decision hashes, delivery/confirmation/routing и limits не заменены
   unsupported default. Actual independently hash-bound code_group assignment
   по-прежнему поддерживается raw SDK; это НЕ grant редактировать/execute пример.
2. `mcp/_docs_server_resources.py`: schema advertises only `untrusted_data`,
   filename/scope attribution `scoped_repository_document`, never scoped workflow
   trust; `direct_webfetch=forbidden`, inert-document precedence. Quickstart явно
   включает canonical/AGENTS/CLAUDE quotes, JSON/comments/commands. Scope — retrieval
   boundary, не authorization; отсутствие trusted route не network permission.
   Existing lifecycle consent/safety controls не заменены этими текстами.
3. `docs/mcp_footprint.py`: representative fixtures keep quote/command bytes как
   cited implementation data, empty promoted invariants/forbidden/checks,
   `edit_ready=False`. Docs sample — positive context/cite-only read, не semantic
   answer permission. Synthetic hashes остаются characterization placeholders,
   НЕ runtime source proofs. Measurement code/CLI/limits не изменены.

Никаких A-owned catalog/models/project-context изменений. No agents, commits/push,
PRIMARY или `/home` edits, live HTTP/DNS/providers, dependency installs, runtime
index writes/build/rebuild, installed artifacts/reinstall. Shared `.venv` untouched.

## Executed tests — normal conftest, offline

Все runs используют `PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1`, shared
`.venv/bin/python`, `-p no:cacheprovider -q`; основной diagnostic manifest не менялся.
Новый shard: 9 base nodes / 21 parametrized cases; static resource contract node
`schema`, остальные actual consumer/measurement nodes `behavioral`.

```text
.venv/bin/python -m pytest -p no:cacheprovider -q
  tests/test_dictionary_exit_inert_sdk_closure.py
  tests/test_dictionary_exit_read_routing.py
  tests/test_dictionary_exit_selector_visibility.py
  tests/docs/test_mcp_token_footprint.py
```

**123 passed, 0.90s.** New module standalone: **21 passed, 0.70s**.
Fixtures используют temp project root и in-memory bound rows/DTOs, не runtime index.
Actual raw SDK (не mock aggregation) выполняет normalization/trust/presentation/
support/delivery; tests cover unknown/true/false consent + fake issuer authorization
claims, canonical/AGENTS/CLAUDE paths, resolved modify/delete intent readiness,
original source/hash/span/version preservation, independently validated structural
code assignment and supported raw SDK result with edit denied, public MCP context
consistency + 800-token cap, foreign-root veto, existing bootstrap confirmation,
PermissionError/TimeoutError/ValueError propagation. No new queue/time-budget path.
Existing bounded read/selector/footprint guards исполняются без assertion rewrites.
`git diff --check`: PASS.

### Old SDK frozen failure ledger — NO WAIVER

```text
.venv/bin/python -m pytest -p no:cacheprovider -q
  tests/test_unified_docs_context.py tests/test_unified_docs_context_part02.py
```

**3 failed / 70 passed, 0.54s**. Existing modules unchanged:

```text
tests/test_unified_docs_context.py::test_library_context_consumes_selector_support_instead_of_context_presence
tests/test_unified_docs_context.py::test_patch_like_project_question_recommends_patch_constraints
tests/test_unified_docs_context.py::test_imperative_project_edit_tasks_recommend_patch_constraints
```

### Causal baseline replay (process memory only)

Read `git show ee156cba:docmancer/docs/application/_unified_context_service_part01.py`,
compile it in a same-package namespace, replace only assembled Part01 class's
`get_docs_context` method **in that test process**, then call normal `pytest.main`.
No baseline file restore/worktree/user-change overwrite. Frozen B and all other
current modules remain active; this is **follow-up method differential, NOT full
ee156cba baseline CI**.

- Old SDK pair: **same 3 reds / 70 passed**, 0.19s, exact ledger above.
- New actual raw SDK unknown-permission node: **9/9 red**, 0.27s, every failure
  `assert result.edit_ready is False`, actual baseline True. Cases are Cartesian
  `[claim0,claim1,claim2] × [docs/reference.md,AGENTS.md,CLAUDE.md]`;
  node prefix `tests/test_dictionary_exit_inert_sdk_closure.py::test_actual_raw_sdk_ready_intent_and_bound_quote_are_not_permission`.
- Current method: all 9 cases green within final 123-pass run. This proves the
  actual non-authorizing aggregation barrier, not positive authorization.

### Final log pins

```text
37b00e857b725dd258c153fda51428f2d7443affdc05345099dc8e2173a641f3 /tmp/opencode/inert-sdk-closure-new.log
12f974848bbf4f40747e8f74a9e8143f71746753dc2b36a09be6e94783e78cbc /tmp/opencode/inert-sdk-closure-guards.log
3d2896a8136b6e90f643219317ac3a21851634ae7d876fb92095d14962ead050 /tmp/opencode/inert-sdk-closure-old-sdk.log
156fd3e589e5ea09bb8b48e1914ea919b632ef1a93daf882018ccab2fd1adfcb /tmp/opencode/inert-sdk-closure-baseline-method-old.log
6aab806f7b6f84cee896085d1bd20be1a8efaf59948f507e31505874cf3a969a /tmp/opencode/inert-sdk-closure-baseline-method-red.log
```

## Exact source pins / extraction ONLY these follow-up paths

Baseline production SHA256 (same as start-of-follow-up bytes):

```text
3a87362344f131500adefbd7a1c26a126887b134ece1febb7c60972590f388bc docmancer/docs/application/_unified_context_service_part01.py
05f8520723f90d92c7cb78aeaac07967ba5b01febbfa9bf7628afde7a70130c0 docmancer/mcp/_docs_server_resources.py
8082eaf08a37f2cc56c4b030f7a41bc31230ad049a3539502171a12d1e1f3116 docmancer/docs/mcp_footprint.py
```

Final 5 payload-file SHA256 pins; this report is the sixth file (no circular self-pin):

```text
fc530be74a058a7edf3f4443a66ddbf59b585fb7f0e64fb51c793c9945b09e0f docmancer/docs/application/_unified_context_service_part01.py
a2b0cd0e14bf60ae25e3209fe62dc0f611a44579287ec1e720ef4ff47c2cdeba docmancer/mcp/_docs_server_resources.py
c997df98f3088f7adbe3820a6828ab8ad6df00080c685d64f887eb8f7fe1e77c docmancer/docs/mcp_footprint.py
f7fc180641a00b31296cb1db4422e37a47b87bb610cc9ae681a69a5b2bc069e3 tests/test_dictionary_exit_inert_sdk_closure.py
68d0cee86b17051c7acc089509d31e121e6f266065bbcab788df59f49727019a tests/diagnostic_labels.dictionary_exit_inert_sdk_closure.json
```

## External remaining / parent fresh review

This follow-up closes the three reported raw SDK/resource/sample dependencies,
NOT all historical/current clients. Frozen B independent review still active;
do not amend its report or remove NL veto based on this worker's own tests.
Parent owns all-consumer closure and acceptance, including direct ProjectContext
callers, lifecycle/consent/queue/transport/protected-path ceilings and installed
wheel/packs/index/stdio/resource parity (UNKNOWN here).

Read-only residual inspection: `interfaces/mcp/recovery_projection.py:315-345`
can copy the caller's `edit_authorized` parameter; all four found current
`context_tools.py` calls explicitly pass False. No current True call demonstrated;
private/external helper callers remain parent review scope, no edit here.
`_project_context_service_part01.py:733-746` and models remain A-owned/unchanged;
their direct DTO consumers are not covered by this Unified aggregation test.
Static resource/footprint definitions updated only in source; no installed artifact
mutation or broader auth mechanism. **Fresh independent parent review required;
no full EXIT/security/quality/release approval.**

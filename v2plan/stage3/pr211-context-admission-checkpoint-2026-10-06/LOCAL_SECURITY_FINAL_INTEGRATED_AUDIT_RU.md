# Final integrated local/security audit — bounded

2026-10-07. Независимая проверка `/home/viadmin/StudioProjects/hermes/docmancer`,
branch `integration/stage3-v2-identity-pr1`, HEAD
`ee156cba4cc6dd4bf51c0e2c8adf44907aac9633` + delivered A/B payload.

**Bounded publication blocker: NO.** В проверенных integrated chains нового
cross-worker permission promotion, lost source identity или bypass раннего denial
не обнаружено. Это разрешает только bounded checkpoint publication, **не full EXIT,
release, quality/security acceptance, runtime mutation или удаление NL veto**.
External SDK/current installed artifacts/index parity: **UNKNOWN**.

## Scope / effective evidence

Прочитаны committed `FINAL_INTEGRATED_EXIT_AUDIT_RU.md`, три local checkpoint
reports (`LOCAL_MEMBERSHIP_IMPLEMENTATION_RU.md`,
`LOCAL_MEMBERSHIP_CALLER_CLOSURE_RU.md`, `LOCAL_ENTRY_CLOSURE_RU.md`) и два root B
reports (`INERT_SECURITY_IMPLEMENTATION_RU.md`, `INERT_SDK_CLOSURE_RU.md`). Проверены
текущие definitions/callers и diff относительно HEAD; старые proposals не доказательство.

Effective union: **46/46 payload pins совпали**, плюс пять прочитанных reports.
Порядок overrides: first local → caller → B → B SDK → local entry correction.
Old first-A ingest part01 pin явно superseded local-entry correction; historical
report не переписан. Union SHA256 для sorted `path + ' ' + sha256 + '\n'`:
`c0ac47d6703357181c2d922796a17e7381b14245380e562021e970b285307c26`.
Union включает также pinned unchanged guards; это не утверждение 46 modified files.

## Actual chains / межworker границы

* **D1:** actual `ProjectMetadataReader` → finite catalog/source boundary → inspect,
  source facts/code graph/patch constraints и project retrieval. Pilot ровно
  **10 docs, 0 modules, code_files=()**. Catalog role/scope/authority/impact — routing
  data, не permission. Links, changed paths, names и imports не расширяют selected
  set. Empty/invalid code membership даёт unresolved, не proof of absence.
* ProjectContext фильтрует retrieved chunks по selected path, current content hash
  и catalog-entry hash до selection/ranking. A source read binding не является B
  workflow grant. B annotation перезаписывает caller trust в `untrusted_data`,
  включая canonical/AGENTS/CLAUDE/JSON/comments; document bytes остаются data.
  Source root/hash/span/version checks и token budgets не заменены authority labels.
* B `normalize_candidates` больше не допускает fake `host-policy://` identity
  exemption. Stable child требует parent/display hash и valid supplied spans;
  legacy identity остаётся attribution, не authenticated caller identity.
  `_may_guide_workflow=False`; packet validator запрещает document policy/workflow
  promotion. `project_patch_context` сам валидирует packet даже для direct SDK call,
  выдаёт `edit_ready=False`; projection validator отвергает promotion до раннего
  insufficient return. Typed mutation readiness — resolution data, не authorization.
* Actual Unified SDK aggregator принудительно ставит `edit_ready=False` также в
  copied completeness/details, не мутируя upstream DTO. Public MCP retrieval lane
  не превращает wire issuer/consent/operation metadata в grant. Direct ProjectContext
  completeness также не даёт grant: фактический `derive_project_answer_completeness`
  в unchanged HEAD domain implementation всегда возвращает `edit_ready=False`,
  включая typed patch request. Условный дополнительный clamp в project service
  поэтому не демонстрирует текущий True route.
* Direct `LibraryDocsService` delegates → `ProjectDocsService.ingest_project_docs`,
  `sync_project_docs`, independently callable incremental sync: **PermissionError
  до path/config/adapter/index/lock/agent/queue/staging effects**. Exact/changed/
  deleted/renamed candidates, vectors и coordination flags не являются consent.
  Нет broker, fabricated grant или позитивного mutation lane. Old bodies оставлены
  недоступными, не названы working autosync. Existing prepare catch даёт nonretryable
  authorization-specific guidance, не предложение rebuild/prune по catalog consent.
* Public Dart resolver, включая shared/wildcard aliases, возвращает unresolved
  до coercion/path probing/package_config/rootUri reads. Pure URI syntax helper не
  read grant. Root-bound selected source helper сохраняет original bytes/hash/line
  refs и caps; bare helper без binding conservative unknown. Нет dependency discovery.
* Protected paths, literal membership, symlink/root restrictions, generated consent,
  file/byte/count/depth/deadline и projection caps не превращены в approvals.
  `finite_doc_reference` проверяет current root/path/hash/catalog binding лишь для
  attribution/ranking; не удостоверяет issuer или edit authorization.

**A/B clash не обнаружен:** narrowing не удаляет runtime rows; annotation/projection
не отбрасывают source identity ради positive trust; отсутствующий auth остаётся deny.
Это не сертификат каждого historical/private/external consumer или race-free FS.

## Independent bounded execution

```text
PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -p no:cacheprovider --basetemp=/tmp/opencode/final-security-audit-ee156cba -q
tests/test_dictionary_exit_local_membership.py
tests/test_dictionary_exit_local_callers.py
tests/test_dictionary_exit_local_entry_closure.py
tests/test_dictionary_exit_inert_security.py
tests/test_dictionary_exit_inert_sdk_closure.py
```

**161 PASS, 0.94s**: 31 + 34 + 32 + 43 + 21. Один integrated run, не сумма
повторных worker runs. Normal conftest/offline guards, только temporary YAML/source
fixtures и fake/in-memory services/effect spies; index creation/rebuild fixtures
не запускались. Parent-reported 161 PASS совпадает, но не суммируется с этим run.
Worker historical ledgers сохраняются: local 34 reds, B frozen 29 reds, B SDK
3 reds; здесь эти suites не rerun и не waived/blanket-attributed baseline.
Baseline сравнение source-only (`git diff`/`git show`), не full baseline CI.

## Effective critical pins / stop

```text
41e74edd094f7710a1ef468abc07e0819a29d5a5968f6df2c1a68d6f60354037 docmancer/docs/application/_project_docs_service_part01.py
fd46cfb8f423d5b816be96402744baa15c2d16ecadb81065afeca433bca3740d docmancer/docs/application/_project_docs_service_part02.py
3d3afd2212a24edb06248ef5017f6a4c5e72ddbab05b6a9e5a7ac8d95db6ee93 docmancer/docs/dart_package_config.py
fc530be74a058a7edf3f4443a66ddbf59b585fb7f0e64fb51c793c9945b09e0f docmancer/docs/application/_unified_context_service_part01.py
938965ff1e2c03d91ed8eff2a4d9e6f9f5eace5c79ff6e2ed800b1f77d646c0c docmancer/docs/application/model_visible_projection.py
269cd1fefe20208f5d6eeccb7e053f90edaf92efb9a154957e35af9a66f8e6d0 docmancer/docs/domain/answer_completeness.py
```

**Remaining barriers:** installed wheel/packs/resources/stdio/current index and
external SDK authorization parity UNKNOWN; historical acceptance reds не закрыты;
NL detectors/negative veto **RETAINED**, поэтому implementation не dictionary-free.
Selection не разрешает удаление former 124 docs/index rows. Recovery helper умеет
копировать external `edit_authorized`, но current MCP callers передают False;
это не доказательство authentication внешнего caller. Full EXIT/release запрещены
без отдельной проверки этих границ. Actual bounded defect не найден, поэтому
дополнительных production/test/config файлов для исправления не предлагается.

Единственная repo запись этого review — данный report. Нет source/test/config
изменений, network/install/provider calls, runtime index work, agents, commit/push.
Отдельный next07/`0ce30227`, existing dirties и artifacts не изменялись.

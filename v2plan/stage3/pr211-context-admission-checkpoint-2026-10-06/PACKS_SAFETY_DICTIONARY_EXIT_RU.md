# Packs safety — минимальный P0/R1 EXIT

2026-10-07. Изолированный worktree:
`/tmp/opencode/docatlas-final-packs-safety-42c72bd6`.
Baseline/HEAD: `42c72bd6d37700b6fe04890c25e8c4ac45bc9e57`.
Основание: R1 в `FINAL_DICTIONARY_EXIT_INVENTORY_RU.md` worktree
`/tmp/opencode/docatlas-final-exit-inventory-42c72bd6`.
**Закрыт только endpoint-name exemption R1, НЕ полный dictionary EXIT.**

## Изменение и границы

Единственный production diff — `docmancer/mcp/registry.py::_derive_safety`:
удалены path lookup и исключение `/search`, `/query`, `/list`, `/find`.
POST/PUT/PATCH/DELETE всегда получают `destructive=True` независимо от path.
HTTP method classification, auth/rate/idempotence DTO и сигнатуры сохранены.
Новых aliases, description classifier, safety overrides или permissive fallback
не добавлено. Installer, dispatcher, credentials, safety, network policy,
source-consent/fetch surfaces не изменены. Missing-safety policy не расширялась;
тесты гарантируют полный safety DTO у реально скомпилированных операций, но
не сертифицируют произвольные внешние packs без safety metadata.

## Исполненный offline repro и caller chain

Baseline функция извлечена через `git show 42c72bd6:docmancer/mcp/registry.py`
и исполнена отдельно в памяти, без изменений файлов:

| DELETE path, allow_destructive=False | baseline | текущий diff |
| --- | --- | --- |
| `/search/all` | allowed=True | allowed=False, destructive_call_blocked |
| `/records/all` | allowed=False, destructive_call_blocked | то же |

Новые behavioral tests: **7 base nodes / 39 parametrized cases**.
Проверены четыре write methods × пять paths, safe GET positive, auth veto,
method casing, idempotence и exact x-idempotent, rate/auth DTO, input immutability.

Actual chain: `build_openapi_pack` → hash-bound LocalRegistry → `install_package`
→ сохранённый Manifest → `Dispatcher.call_tool` → real network policy,
credentials и `safety.check`. DELETE `/search/all` и `/records/all`, POST
`/search/all` блокируются без grant; разрешение требует одновременно package
и operation destructive grant. GET достигает offline executor; auth-required
GET без credentials блокируется, с fixture credentials проходит. Host/private-IP/
plain-HTTP guards сохранены. Проверены source URL/hash, artifact SHA и counts.
DNS заменён детерминированным результатом, только финальный executor — stub.
**HTTP/network request, stdio transport и реальный destructive request не выполнялись;
реальный request bypass не заявляется.** Source URL — локальные fixture metadata,
не fetch authorization. Initial test attempt изменить установленный contract
был отвергнут artifact_hash_mismatch (38 passed / 1 failed); fixture исправлен
на нормальную повторную compilation/install HTTP-spec, integrity guard не обходился.

## Проверки с обычным conftest

Во всех командах префикс:
`PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -p no:cacheprovider -q`.
Без `--noconftest`, без live tests/network.

1. `tests/test_dictionary_exit_packs_safety.py`:
   **39 passed**, 0.21s.
2. Новый модуль плюс `tests/test_mcp_registry_fallback.py`,
   `tests/test_mcp_installer.py`, `tests/test_mcp_dispatcher.py`,
   `tests/test_mcp_network_security.py`, `tests/test_mcp_credentials.py`,
   `tests/test_mcp_idempotency.py`, `tests/test_mcp_sha_verify.py`,
   `tests/test_mcp_paths.py`: **116 passed**, 0.93s
   (39 новых + 77 существующих cases).
3. `tests/test_dictionary_exit_*.py tests/docs/test_mcp_token_footprint.py
   tests/docs/test_mcp_boundary.py tests/docs/test_finalized_mcp_output_integrity.py
   tests/test_support_surface_policy.py tests/docs/test_target_security.py
   tests/docs/test_content_trust.py`:
   **1715 passed / 6 failed / 1 existing multipart warning**, 5.62s.
   Historical inventory для того же набора без нового модуля:
   **1676 passed / 6 failed**; текущая прибавка ровно 39 новых cases,
   не исправление old reds и не сравнение full CI.

Точные сохранённые red nodes текущего mixed run:

1. `tests/test_dictionary_exit_admission_literals.py::test_application_adapter_really_calls_default_hook_but_unknown_is_consumer_debt`
2. `tests/test_dictionary_exit_discovery_literals.py::test_explicit_api_templates_and_package_pages_are_not_topic_tables`
3. `tests/test_dictionary_exit_discovery_literals.py::test_actual_dart_resolver_caller_preserves_root_and_version_provenance`
4. `tests/test_dictionary_exit_discovery_literals.py::test_removed_ecosystem_alias_does_not_expand_caller_target[pub]`
5. `tests/test_dictionary_exit_discovery_literals.py::test_removed_ecosystem_alias_does_not_expand_caller_target[flutter]`
6. `tests/docs/test_mcp_boundary.py::test_patch_constraints_debug_compaction_preserves_contract_fields`

Первые пять — existing admission/discovery contract debts; шестой — старое
`answer_available=True` ожидание для nonauthorizing packet. Не waived, не green.
Старые tests, diagnostic manifest, frozen gold, thresholds, fixtures и corpus
не переписаны. Historical self-host quality FAIL не переименован в PASS;
новый quality/release/wheel/indexed-corpus run не выполнялся.

## Handoff: ровно четыре файла

1. `docmancer/mcp/registry.py`
2. `tests/test_dictionary_exit_packs_safety.py`
3. `tests/diagnostic_labels.dictionary_exit_packs_safety.json`
4. `v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06/PACKS_SAFETY_DICTIONARY_EXIT_RU.md`

SHA-256 первых трёх файлов:

```text
93d3a13e2c52bb1a54c47d28a4517ad2c1b9493f8b940732d7b4d5d386a097b7  docmancer/mcp/registry.py
3e943dae9fb050ecd975fb41333af28e1558445029bcd1ec15aa17bc614074c5  tests/test_dictionary_exit_packs_safety.py
ac94df0680a7334697b3f3975a319a769612263422c8b2910ce819355375eb76  tests/diagnostic_labels.dictionary_exit_packs_safety.json
```

Diagnostic node-set pin:
`ac9e75ad10ca20f2ceb5fa25e87579f82bb109b470964dc68e9f6938009f1f79`.
R2–R12, corpus/local allocations, missing metadata external contracts и
negative safety detectors остаются за пределами этого slice. Ранее установленным
packs нужна отдельная recompilation/reinstallation; существующие machine artifacts
не менялись. Нет agents, commits, push, network или primary edits. Pre-existing
untracked `.venv` не изменялся. Parent переносит только эти четыре файла после review.

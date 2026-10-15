# PR #211: разрешение trust-resource conflict

Дата: 2026-10-08. Узкий test-only slice, не merge/release approval.
Исходный HEAD: `21fe472d983f394130849d6fd4e582043d58e9ba`.
Production и retrieval в этом slice не меняются.

## Основание текущего контракта

Старое ожидание в
`tests/test_dictionary_exit_delivered_surfaces.py::test_resource_uris_trust_schema_and_bounded_reader_template_unchanged`
появилось в `307c480` до security slice и сохранилось при миграции compact-surface
companions в `5310e6d`. Оно допускает `explicit_agent_policy` и
`scoped_agent_policy`, то есть уже отменённый instruction tier для repository prose.

Security commit `6e94d6ab926f23c39c2bdbb7b926f6a1593ec68f` намеренно и синхронно
изменил `content_trust.annotate_context_pack`, `source_trust_dimensions`,
`build_project_context_trust_contract` и JSON resource в
`docmancer/mcp/_docs_server_resources.py`. Это не новый выбор по observed actual:

- `INERT_SECURITY_IMPLEMENTATION_RU.md`, пункты 1 и 7: retrieved canonical docs,
  AGENTS/CLAUDE, JSON и source comments остаются `untrusted_data`; filename/root/scope
  дают только attribution. Empty result не выдаёт `discovery_only` как permission.
- `INERT_SDK_CLOSURE_RU.md`, пункт 2: resource рекламирует только
  `untrusted_data`, `scoped_repository_document`, `direct_webfetch=forbidden` и
  отсутствие repository-policy instruction tier.
- `stage3/pr211-context-admission-checkpoint-2026-10-06/LOCAL_SECURITY_FINAL_INTEGRATED_AUDIT_RU.md`,
  раздел Actual chains: независимый integrated review подтверждает отсутствие
  workflow grant из filename/scope/caller trust и сохранность source binding.
- `stage3/pr211-context-admission-checkpoint-2026-10-06/NL_DICTIONARY_REMOVAL_COMPLETED_RU.md`,
  раздел Новый контракт, и `action-packet-v4/CONTRACT.md` закрепляют retrieved prose
  как cited `untrusted_data`. Отмена detector hit не создаёт permission.

Эти исторические reviews обосновывают контракт, но не заменяют новый acceptance run.

## Контракт, который сохраняют successors

| Измерение | Текущий смысл |
|---|---|
| `source_provenance` | `configured_repository` или `external_source`; происхождение данных |
| `version_exactness` | Exactness версии независимо от instruction trust |
| `scoped_repository_document` | Известный policy filename внутри проверенного repository root; только path attribution |
| `ordinary_repository_document` | Repository prose без подтверждённой scoped-policy attribution |
| `not_applicable` | Repository authority неприменима к external/library lane |
| `instruction_trust` | Только `untrusted_data`, включая canonical policy quotes и caller-supplied trust |
| `content_boundary.executable_policy` | Всегда `False` для retrieved quote |
| `instruction_precedence` | `host_instructions_over_document_data_no_repository_policy_grant` |
| `direct_webfetch` | `forbidden`, независимо от наличия selected sources |

`scope_verified` не означает проверку автора инструкций или consent. За пределами
root, без root или в library lane policy filename не получает scoped attribution.
Отсутствие trusted docs не заменяет отдельное разрешение на сеть. Возвращённое
предложение prefetch остаётся действием с `requires_confirmation=True`.

## Изменения тестов

Существующий resource node сохраняет имя и проверки полного URI/template inventory,
версии `trust-contract-1.2`, issued source reference, лимитов 600 tokens / two reads,
запрета fabricated reference, неизвестного resource и `source_unavailable`.

Миграция фиксирует точные разрешённые source dimensions и полный policy contract.
В том же node проверяется соответствие advertised resource реальным domain
annotation/dimension helpers: in-root AGENTS/CLAUDE, ordinary README, path escape,
отсутствующий root и library lane. Поддельные caller trust/executable-policy claims
не повышают полномочия; точный текст и исходный caller object сохраняются.
Реальный trust-contract builder проверяется с canonical AGENTS source и без sources,
чтобы resource не обещал workflow/network permission, которого нет у runtime.

В `tests/docs/test_trust_contract.py` мигрированы два связанных старых ожидания:
repository-policy precedence и `discovery_only` для unresolved dependency.
Проверки dependency rejection, warning/risk/source classification и prefetch tool
сохранены; явно закреплены `no_trusted_context` и required confirmation.

Новых pytest nodes нет, diagnostic node manifest не меняется. Production contracts,
schema version, source/read/security bounds и retrieval implementation не меняются.

## Проверка

При подготовке slice pytest не запускался: текущая локальная среда не содержит
pytest/MCP runtime и зависимостей проекта. Старые PASS counts не переписаны.
Выполнены AST parse обеих test modules, `git diff --check` и static сверка
base-node roster hashes с diagnostic manifests: 11 и 3 base nodes, оба MATCH.
Эти проверки не импортируют project code и не исполняют pytest. Последующий
совместный run фиксируется в итоговом отчёте волны на точном SHA; этот файл не
объявляет tests/CI/installed delivery пройденными.

Целевой набор для подготовленной fixture-only среды с normal conftest:

```text
tests/test_dictionary_exit_delivered_surfaces.py
tests/docs/test_trust_contract.py
tests/docs/test_content_trust.py
tests/test_dictionary_exit_inert_security.py
tests/test_dictionary_exit_inert_sdk_closure.py
```

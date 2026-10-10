# MCP delivery — итог безопасно закрытого этапа

**Historical stage snapshot:** дальнейшее user-approved trusted-local решение,
реальный положительный lifecycle и installed smoke см.
`../mcp-storage/FRESH_PLAN_RU.md`. Blocked observations ниже относятся к прежнему
этапу/профилю; они не заменяются утверждением о native VFS security closure.

Runtime integration SHA: `0d3e5b31` (последний smoke commit C включён).
**Полная замена MCP и merge/release acceptance не достигнуты.**

## Проверенные результаты

- На `5772d372`: 1067 выбранных offline product/security tests PASS с normal
  conftest; это не полный CI и не historical evaluation acceptance.
- После последнего smoke commit: 219 затронутых integration tests PASS.
- Scope, syntax, whitespace и общий line-budget <=1000: PASS.
- D1 неизменен: exact 10 documents, `code_files=()`; пользовательский индекс
  не перестраивался и не менялся.
- R независимо: 157 focused tests PASS и два повторных запуска attack probes.
  R2–R9 закрыты для конкретных воспроизведённых дефектов. R1 containment
  проверен, но functional persistence blocker остаётся OPEN.

## Финальный installed wheel / настоящий stdio

C собрал изолированный wheel с финальными A/B runtime fixes и проверил
настоящие structured/text transports, без mocked retrieval/source PYTHONPATH.

- Read-only smoke: PASS в обоих transports.
- Preparation: `blocked`, `unsafe_sqlite_path_mutation`, `retryable=false`,
  `mutation_performed=false`; bytes/rows fixture DB неизменны.
- Источники через этот lifecycle: `[]`, evidence bytes: **0**.
- Full smoke: exit **1**. Positive indexed/partial/complete/>32 KB/scope/version
  delivery через preparation не наблюдались и не засчитываются.
- Ready-index bootstrap и VFS implementation не выполнялись.

Wheel SHA256:
`1c13cdf130ba59b9853e6b98b04d25e6e5166dbb1371672ca632df549ca52d8e`.

Лог: `/tmp/opencode/mcp-delivery-c-validation/final-blocked-smoke.log`.
Это артефакт C с equivalent runtime changes, не claim exact integration-SHA
artifact parity или deployed parity.

## Почему persistence остаётся запрещён

Доступный Python SQLite pathname API не обеспечивает descriptor-bound открытие
БД вместе с journal/WAL/SHM при hostile concurrent filesystem replacement.
Post-check, advisory lock и `/proc` alias не приняты как доказательство защиты.
Небезопасная запись остановлена до disk connect/recovery; обхода ради PASS нет.
Для рабочего prepare → retrieve нужен отдельный согласованный storage/VFS-срез.

## Compatibility и оставшиеся gates

- Identity теперь `local:sha256(absolute_root)`, без Git reads. Producer и
  consumer используют одинаковое правило. Старые Git-identity rows исключены;
  migration/alias/rebuild не реализованы. Это отдельное compatibility decision,
  не доказательство index parity.
- Cold DB initialization/migration не реализованы.
- R5 доказывает unsupported-platform denial before I/O, не Windows support.
- Остаются активные старые v3 packet fixtures/CI contracts. Historical gold,
  thresholds, reports не переписывались; historical suites не запускались.
- Remote PR #211 остаётся на `2d060bf0`; новый CI acceptance не заявляется.
- Main, установленный MCP, клиентская конфигурация, версия пакета, публикация
  и merge не менялись. Изменения этого этапа пока локальные.

Предыдущий `PROGRESS_RU.md` — superseded snapshot: успешные временные записи
там относятся к pre-hardening lane и не доказывают работоспособность финального
safe-closed runtime. Финальное состояние — intentional preparation blocker.

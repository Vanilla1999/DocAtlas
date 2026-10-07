# Свежий план завершения MCP

Integration base: `70d2553c`; packing base: `b8547099` (ещё не интегрирован).

## Явные решения пользователя

1. Автоустановка: installer скачивает подходящий Python и готовые зависимости.
   Это выбор способа поставки, не команда на live reinstall/config replacement.
2. Локальный MCP с trusted storage вне проекта, обычный SQLite. ОС и процессы
   текущего пользователя считаются доверенными; защита от malicious same-UID
   процессов в этот профиль не входит. Это явно согласованная смена storage
   threat model, не утверждение, что VFS закрыл прежний R1.
3. Недоверенные документы, запросы и проектные пути по-прежнему проходят
   grants/scope/hash/span/source-read проверки. Нет новых authority из metadata,
   ослабления validators, semantic dictionaries или искусственных weights.
4. Старую БД сохранять/мигрировать не нужно. На этом этапе она не читается и
   не удаляется; initialization и lifecycle проверяются на isolated fixtures.

## Что обнаружила свежая проверка

- Native VFS не решает неограниченное same-UID вмешательство; production его
  не использует. Spike остаётся experimental evidence старых ограничений.
- Prepare hardcodes project-local storage, обычный runtime может выбрать app-home
  DB или project config. Нужен один trusted target для initialize/prepare/retrieve.
- Packing tests обходили реальные `LibraryDocsService` forwarders. В production
  graph ACK отклоняет легитимное делегирование. Второй дефект — deepcopy даже
  при выключенном retention. 298 PASS не покрывали эти два пути.
- Remote PR #211 по-прежнему на `2d060bf0`, OPEN, CI красный на том старом SHA.
  Это не результат проверки текущего локального integration tree.

## Владельцы и конечные результаты

### A — trusted storage lifecycle

Worktree `/tmp/opencode/mcp-fresh-storage`, base `70d2553c`.
Точный allowlist:

```text
docmancer/core/member_storage_policy.py
docmancer/core/_sqlite_store_part01.py
docmancer/core/config_resolution.py
docmancer/docs/application/project_docs_member_transaction.py
docmancer/docs/application/_project_docs_service_part01.py
docmancer/docs/application/_project_docs_service_part02.py
docmancer/mcp/_docs_server_part01.py
docmancer/docs/interfaces/mcp/prefetch_tools.py
docmancer/mcp/_docs_server_tool_data.py
tests/test_mcp_delivery_member_transaction.py
tests/test_mcp_delivery_dispatch_boundary.py
tests/diagnostic_labels.mcp_delivery_member_transaction.json
tests/diagnostic_labels.mcp_delivery_dispatch.json
tests/test_mcp_trusted_storage_lifecycle.py
tests/diagnostic_labels.mcp_trusted_storage_lifecycle.json
```

Один host-selected storage target вне проекта; caller/project config не выбирают
другую БД. Явная confirmed initialization только отсутствующего хранилища;
unexpected existing DB не adopt/overwrite. Early grant validation до mutation.
Generation CAS и member ownership в одной SQLite transaction. Retrieval/restart
используют тот же target. No orphan deletion, vectors, extraction publication.
Существующие source FD/budget/hash checks сохраняются. Initial journal route —
rollback; никаких claims о защите от same-UID или hostile journal destruction.

### B — минимальный packing repair

Worktree `/tmp/opencode/mcp-fresh-packing`, base `b8547099`.
Точный repair allowlist:

```text
docmancer/docs/domain/project_doc_ranking.py
docmancer/docs/service.py
tests/test_action_packet_v4_found_window_retention.py
tests/diagnostic_labels.action_packet_v4_found_window_retention.json
```

Bypass ACK/signature/deepcopy в обычном режиме; два настоящих forwarders получают
корректное child delegation. Новый ACK/capture framework не разрабатывается.
Проверка реального service graph и actual lexical retrieval на временной БД,
плюс прежние security/qualification/acquisition-trace tests.

### C — lineage и installed acceptance

Свежий read-only audit выделяет точный минимальный lineage fix и достижимость
>32 KiB при прежнем acquisition. Implementation allowlist ещё не выдан.
Финальное доказательство — установленный wheel, настоящие stdio structured/text,
fresh initialization → prepare → retrieve → restart, а не fixture bootstrap.

### Coordinator / R

Coordinator фиксирует interfaces/ownership и интегрирует проверенные commits.
R независимо проверяет итоговые изменения и реальные acceptance paths.
Без nested agents и пересекающихся владельцев файлов. Общий runtime release
проверяется на одном integration SHA; broad native/capture redesign остановлен.

## Условия завершения

- Реальный fresh lifecycle и scope/version/partial evidence проходят validators.
- Library lineage сохраняется от producer; hashes/spans не синтезируются ради PASS.
- >32 KiB считаются только по уникальным source bytes в одном реальном ответе;
  если acquisition не даёт их, ограничение отчётливо фиксируется, guards не растут.
- Active CI contracts мигрируются без изменения historical gold/thresholds и
  отключения gates. Historical evaluation suites не запускаются.
- Auto-install проверяется на clean supported environments без компилятора;
  текущий shell installer пока поддерживает Linux/macOS, Windows требует своей
  проверенной installation route. Версия runtime/release отдельно фиксируется.
- Live replacement, push/merge/publish и удаление старой БД остаются отдельными
  действиями. Одна MCP registration с сохранением существующего имени.

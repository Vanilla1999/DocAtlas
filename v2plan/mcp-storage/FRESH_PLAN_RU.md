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

A completed `0ee73213`, independent storage R review pending. Default target:
`$DOCATLAS_HOME/mcp-members/members.db`. Existing confirmed mutation with explicit
null generation provisions only an absent target after source validation. A
reports 168 focused PASS and actual source-stdio cold prepare/retrieve/restart in
both transports; not installed-wheel acceptance. One workflow schema test still
expects the superseded project-local target; coordinator will migrate that test
after review. Private app-home namespace required; group-writable `/tmp/opencode`
is not an accepted storage root. No live DB/config/install change.

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

B repair завершён: `a2df42fded4d555ac3b70185b91a2064a1f7ae91`.
По отчёту B 302 full focused tests PASS. Real temporary SQLite / lexical /
production graph / public handler: 45 qualified windows, 32 475 source bytes
(не >32 KiB). IDs/text/hashes/spans fidelity и acquisition/source-read traces
совпадают с docs mode. Fresh independent R review запущен; до verdict весь
packing series остаётся вне integration branch.

Independent packing R APPROVE integration: 302 matrix + 19 diagnostic/support
tests PASS; real lexical proof отдельно PASS. Series включена в integration
`28e15d55` (`6daa0fe2`, `362cfbae`, `eda9db59`, `28e15d55`). Итоговый rerun с
installer: 326 PASS; scope/syntax/whitespace/D1/line-budget PASS. Это закрывает
scoped packing findings, но не installed >32 KiB, storage lifecycle или release.

### C — lineage и installed acceptance

Свежий audit выделил минимальный lineage fix: canonical индекс уже хранит
original text/hash/IDs/spans/generation; presentation cleaning теряет их.
C implementation approved в `/tmp/opencode/mcp-fresh-delivery`, base `f8be0e7c`:

```text
docmancer/docs/application/_library_docs_service_part03.py
docmancer/docs/application/_unified_context_service_part02.py
scripts/docs_mcp_stdio_smoke.py
tests/test_docs_mcp_stdio_delivery.py
tests/diagnostic_labels.mcp_delivery_c.json
```

Carrier transport не даёт permissions; missing/conflicting/transformed lineage
reject, hashes/spans не выдумываются и не наследуются cleaned snippets.
Original source text остаётся bound к existing canonical producer fields.
Installer node hash в shared shard сохраняется. Exact version ожидается как
`version_binding="exact_snapshot"` плюс numeric resolved-version binding.
>32 KiB — один natural multi-document fixture attempt под прежним acquisition,
с отдельным учётом acquired/qualified/returned unique spans. Нет padding,
acquisition expansion или засчитывания wire bytes как source bytes.
Финальное доказательство — установленный wheel, настоящие stdio structured/text,
fresh initialization → prepare → retrieve → restart, а не fixture bootstrap.

### Coordinator / R

Coordinator фиксирует interfaces/ownership и интегрирует проверенные commits.
Coordinator installer paths: `scripts/install.sh`,
`tests/test_opencode_v2_installer.py`, installer module hash в
`tests/diagnostic_labels.mcp_delivery_c.json`. Installer теперь запрашивает uv
managed Python (default 3.13, overrides 3.11/3.12/3.13) и `--no-build`:
при отсутствии wheel fail, без compiler/source fallback. 46 focused installer /
agent-config tests PASS; это stubbed installer проверка, не clean network install.
Шард C далее передаётся C: installer hash нужно сохранить, изменяя только
delivery module inventory для его новых тестов.
Independent installer R одобрил scoped change: 46 tests PASS, uv 0.9.25 syntax
подтверждён. `--no-build` допускает reuse cached built wheels; не authentication
origin guarantee. Clean install / universal platform wheels ещё не доказаны.
Coordinator также владеет ровно installer paragraph в `README.md` для docs drift.
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

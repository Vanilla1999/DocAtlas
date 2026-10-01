# 02 — P0: clear → rebuild без перезапуска MCP

**Результат:** очистка принадлежащего fixture индекса не оставляет cached service/store сломанным.

**Опора:** D2 в [анализе](../audit/ANALYSIS_RU.md), [исходная ошибка](../audit/raw/lifecycle/probe-after-clear-sync.json), `audit/probe_lifecycle.py`. Общие правила — в [README](../README.md).

## TDD

1. **Red:** в одном MCP-процессе выполнить `sync → query → clear preview → clear confirm → sync → query`. Зафиксировать `OperationalError` после clear; restart не добавлять как часть решения.
2. Добавить regression test всей последовательности, используя настоящий cached project service. Повторить для default и explicit config; проверить наличие schema и актуальную цитату после rebuild.
3. Controls: другой storage root и его services/references остаются рабочими; live writer lease и stale plan digest блокируют clear; remote/unowned Qdrant не удаляется.
4. **Green:** invalidate/reinitialize service/agent/dispatcher state только затронутой storage identity. Учесть несколько service identities, если они указывают на одно storage; не очищать все caches глобально.
5. **Проверка:** lifecycle regression + cleanup/lease/isolation tests; installed stdio выполняет всю последовательность в одной session. Другой root работает до и после clear.

**Где начать:** `tests/test_index_storage_cleanup.py`, `docmancer/mcp/_docs_server_part01.py`, `docmancer/docs/interfaces/mcp/prefetch_tools.py`, `docmancer/docs/infrastructure/agent_index_gateway.py`.

**Не менять:** cleanup ownership/confirmation policy, writer guards, поиск, scorer. Не маскировать ошибку catch-and-retry или обязательным restart.

**Готово:** schema восстановлена, sync/query успешны без нового процесса, чужой storage не затронут. Затем остановиться.

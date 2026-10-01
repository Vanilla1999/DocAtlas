# Шаг 02 — Green: clear → rebuild без перезапуска MCP

Baseline: `a45d2817`, продолжение в текущей ветке `experiment/retrieval-ablation-continuation` по запросу пользователя. Правка, тесты, результаты и [ревью](REVIEW_RU.md) включены в отдельный коммит шага 02; push/merge не выполнялись.

## Red → Green

Последовательность: `sync → query → clear preview → clear confirm → sync → query`.

- [Первоначальный regression Red](red.log): default и explicit config падают на повторном sync с `OperationalError`.
- [Installed baseline](before/default/result.json), [explicit baseline](before/explicit/result.json): ошибка подтверждена реальным MCP stdio, reference `a45d2817`.
- [Installed исправленный default](after/default/result.json), [explicit](after/explicit/result.json): последовательность проходит в одной session без рестарта. После rebuild проверены schema (`sources`, `sections`) и verbatim README citation. В default session другой root работает до и после clear.
- [Финальный regression/cleanup/lease/source suite](green-final.log): **108 passed**. Проверены повторный clear, два config modes, несколько cached identities одного storage, другой storage и его source reference, отсутствие invalidation при preview/неверном digest/live writer lease, существующие remote/unowned Qdrant controls.

## Правка

Production изменён только в `docmancer/mcp/_docs_server_part01.py`:

- После успешного public clear router отмечает владельцев, пути которых пересекаются с фактически удалёнными targets. Обход учитывает несколько cached identities и вложенные service caches; пустой/no-op clear не инвалидирует владельцев.
- На следующем routed request затронутый service лениво заменяется свежим владельцем registry/jobs/agent/dispatcher/source-reader состояния, с сохранением config source/path, factory и library-index root.
- Незатронутые cached services сохраняются вместе с source capabilities. Resource reader не обращается к retired владельцам; старые capabilities очищенного storage не обслуживаются до нового binding.
- Clear сам не создаёт schema заново; rebuild происходит на следующем запросе. Нет catch-and-retry, глобального cache flush или обязательного restart. Repeated replacement chains сжимаются при routing.

Тесты: `tests/test_clear_rebuild_lifecycle.py` и hash-bound `tests/diagnostic_labels.clear_rebuild_lifecycle.json`. Результаты и новый [installed runner](run_installed_smoke.py) находятся здесь; исходный `audit/` не изменён.

## Provenance и границы

Installed runner сверяет все production Python bytes: before — с pinned `a45d2817`, after — с working tree; version/import path/executable/HEAD/hashes сохранены в `runtime.json`. Использованы локальные wheels в `.venv`, не editable/global MCP. Между проверенными версиями меняется только `_docs_server_part01.py`. Перед запуском требуется новая output directory; каждый mode получает отдельный fixture/process, внутри lifecycle процесс один.

Explicit config намеренно удерживает единственную configured storage identity: проверка второго root в installed stdio выполнялась в default mode; сохранность другого cached storage проверена unit regression также для explicit router.

Изменение относится к публичному MCP router, а не произвольному прямому вызову cleanup вне него. Внешние retained Python service references не заменяются in-place; следующий routed request выбирает нового владельца. Прямой handler не заменяет installed stdio проверку.

Ownership/confirmation/writer guards, поиск, scorer, defaults, thresholds, budgets и зависимости не менялись. Полный suite и независимый quality benchmark не запускались. Открытые ограничения шага 01 не закрываются этим изменением. Шаг 03 не начат; остановка после шага 02.

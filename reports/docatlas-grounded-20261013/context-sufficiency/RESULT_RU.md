# Подключение diagnostic sufficiency observer

Реализована диагностическая граница после final source projection/recheck/budget
и `compact_mcp_payload`, непосредственно перед возвратом public MCP DTO.
Checker видит исходный question и полный возвращаемый JSON, не hidden pool.

Это **opt-in подключение**, а не включённый по умолчанию классификатор.
Вопрос о модели владельцу задан; ответ «сам сделай, мне это достаточно» не содержит
endpoint/credentials/разрешения передавать документы конкретному cloud provider.
Выбран безопасный diagnostic-only вариант: без новой model загрузки, network или
непроверенной semantic authority. Real classifier accuracy **NOT MEASURED**.
Никаких автоматических verdicts на пользовательских документах не выдается.

## Контракт

- Host context manager `context_sufficiency_observer(checker)` отключён по умолчанию.
- Checker получает только immutable question/final_context_json strings; mutations
  decoded JSON не меняют live product objects.
- `sufficient/partial/insufficient/unknown`, supported/missing obligations и
  evidence IDs сохраняются только в host observation, не в public DTO/stdout.
- Невалидная форма, несуществующая citation, exception → explicit unknown/error.
- Input oversize → explicit unknown, без обрезки. Other projection kind → not assessed.
- Не меняются source rows, query, budget, scope/version, consent, answer_supported,
  answer_available или edit_ready. Не вызывается recovery/retrieval/model retry.
- `SUFFICIENCY_INSTRUCTION` — общая source-only prompt инструкция, не heuristics,
  threshold или повторно обученная модель. Partial/unknown — явно расширение
  binary sufficiency из ICLR2025, не точное воспроизведение paper classifier.
- Host отвечает за consent, timeout/cancellation и model-call budget. Generic
  synchronous callback может увеличить latency; внутреннего forced termination нет.

## Проверки

### Source-tree public integration

Переиспользован один существующий реальный lifecycle сценарий, без добавления
unit-тестов или новых context calls к нему. **1 PASS за1.42s**.
9 MCP context attempts,2 confirmed prepares/sync,3 SDK/service reads,<=2 resources.
На первых трёх существующих reads: off → scripted verdict sufficient → scripted
exception. Точный serialized input hash соответствует возвращённому final DTO.
Тексты независимых optics facts сохранены; on/off/error normalized packets равны;
authority false, logical DB и project files не меняются. Lifecycle stale/sync и
запрет неразрешённого mutation поля остаются в прежнем сценарии.
Pytest warning: существующий record_property несовместим с junit_family xunit2;
это не product failure. Receipt `integration.xml` сохранён.

### Installed public in-process MCP

Новый wheel установлен в отдельный runtime, Python -I; настоящий public
get_docs_context, production retrieval/selection/storage/validation, без mocks.
**1 prepare,4 context calls,0 model calls**.

Условия off/on/exception/invented-citation: конечный независимый факт
`aperture_control sets the lens aperture. The required value is f/8.` доставлен
во всех4 выдачах, actual hash/span/scope/version/authority checks проходят,
normalized delivery равна, logical DB/project files unchanged.
«sufficient» не выдаёт answer/edit authority; exception и invented evidence ID
фиксируются как unknown/error, не портят public packet.
`INSTALLED_RESULT.json` содержит исходные packets/checks/diagnostics и boundary.

**Внешний assessor в обоих scenarios scripted**, что допустимо только для
проверки транспортной/изоляционной границы. Это не подмена retrieval/storage,
и не доказательство semantic sufficiency, classification precision/recall,
abstention или generated answer correctness. Installed in-process не stdio,
не real client и не production smoke.

## Следующее действие

Для настоящей модели host adapter должен получить pinned model/endpoint и
разрешённый inference budget. Использовать prompt с original question и final
JSON, без GT answer; сначала сохранить diagnostic verdicts отдельно от delivery.
Затем независимая разметка достаточный/частичный/недостаточный, особенно false
sufficient errors. Старые strict source-span и empty-source метрики сохраняются.
До этой проверки **не** предупреждать/ограничивать generation автоматически и
не выдавать permission/authority по результату модели.

Документация: `docs/diagnostic-context-sufficiency.md`.
Продукт: `docmancer/docs/application/context_sufficiency.py` и MCP final return.
Runner: `eval/heuristic_removal/sufficiency_observer.py`.
Ранее выполненные reranker/diagnostic изменения сохранены отдельно, не отменялись.
Commit/push/deploy не выполнялись;40 вопросов не повторялись.

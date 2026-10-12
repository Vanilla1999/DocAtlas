# Prepared retrieval: протокол реализации и проверок до модели

## Основание и граница

Владелец явно запросил: «Сделай тесты интеграционные грубо говоря до перехода
в модель, реализуй пожалуйста в этой ветке все это». Это новый разрешённый
объём после исследовательского checkpoint, а не продолжение закрытых V1–V3.
Базовый коммит: `8ad44222d19d2e8b886349aa3f0f13f71e9167ba`.
Ветка: `fix/main-flow-compact-evidence`. Default не продвигается.

Граница исполнения: установленный editable пакет → публичный in-process MCP
`get_docs_context` / source resource → настоящая подготовка member, SQLite,
лексический поиск, admission, сборка, finalizers, проверка публичного DTO.
Генерации ответа, дополнительных LLM-вызовов, embedding/reranker forwards,
скачивания моделей, installed-stdio или production smoke здесь нет.
Старые holdout/diagnostics и закрытый holdout20 не используются.

## Предварительно зафиксированные сценарии

Независимый автор E создал документы, обе редакции обновляемого документа,
вопросы, ожидаемые факты и caps до первого runtime. Они сохранены непосредственно
в `tests/test_prepared_retrieval_integration.py`; их нельзя менять ради PASS.
Сведения о выполненных публичных запросах и их конечные DTO сохраняются отдельно
от изолированных документов и SQLite. Это наблюдение за результатом; продуктовые
retrieval/selection/storage/validation не подменяются.

| Сценарий | Prepare/sync | Context calls | Resource reads |
|---|---:|---:|---:|
| Составной вопрос: упаковка и получатель акта; raw spans, hash, read-only | 1 | 2 | ≤2 |
| Default parity; exact negative; project/module, unlisted, другой проект | 1 | 10 | ≤1 |
| Legacy fallback; stale refusal; explicit sync; prepared parity; restart | 2 | 6 | ≤3 |
| Все пункты списка; полный конечный cap; возврат к default | 1 | 4 | 0 |
| Полный успешный проход | **5** | **22** | **≤6** |

Точные node IDs — четыре `test_*` в указанном файле. Это четыре интеграционных
сценария, а не 22 независимых задания качества. Caps: **12000 и 900**.
Независимая мера теста: `ceil(UTF8_bytes(json.dumps(payload, ensure_ascii=False))/4)`.
Продукт дополнительно проверяет встроенный offline `o200k_base` на том же JSON.
Стоимость полного host prompt, истории, wrapper клиента и генерации не измеряется.

Два существующих публичных регрессионных сценария разрешены после первого прохода:

- `tests/test_named_document_context_integration.py::test_public_named_document_unknown_locator_fails_closed`
- `tests/test_named_document_context_integration.py::test_project_context_remains_available_when_authority_facet_is_missing`

Root — единственный runtime-координатор. Первый запуск ограничен четырьмя
сценариями с `-x` и wall timeout 240 s. Повтор — только для конкретного выявленного
дефекта или оставшегося обязательного gate; причина каждого запуска записывается.
Нет unit/private-helper/AST/compile проверок, массового CI или матрицы моделей.

## Критерии

1. Требуемые независимые факты находятся в конечных исходных фрагментах.
2. Raw текст/координаты, project/module scope, authority и published snapshot
   согласованы; чтение не меняет файлы или логическое содержимое SQLite.
3. Подготовленная структура и canonical fallback дают одинаковое содержимое
   публичного контекста. Истёкший snapshot и отозванный continuation не доставляют текст.
4. После поздних преобразований весь конечный MCP JSON укладывается в cap;
   допускается явный неполный/пустой пакет без ложного доказательства ответа.
5. Broad admission не выдаёт `answer_supported`, `answer_available`, `edit_ready`
   или нового coverage credit. Нерелевантный непустой результат отдельно остаётся
   `FAIL` действующего empty-source контракта, даже если source integrity PASS.

Не заявляем по этим тестам улучшение ответов модели, общее решение релевантности,
достаточность набора, преимущество Mini или снижение latency на 20%.

## Реализация под отдельными host flags

- `DOCATLAS_EXPERIMENT_ADMISSION=source_valid_candidates_v1`: общий live-bound
  допуск без новых числовых/тематических правил; поздний source/request recheck.
- `DOCATLAS_EXPERIMENT_PREPARED_PARENTS=1`: необязательный manifest при новой
  подготовке и чтение сохранённых canonical parents с raw-source проверками.
  Legacy/miss использует прежний parser; запрос ничего не мигрирует и не пишет.
- `DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS=<positive integer>`: отдельный cap
  на конечный пакет в допустимом project context scope; не требует broad mode.

Флаги читаются сервером, исходный документ или текст запроса их не включает.
Подготовленная структура не кэширует разрешение на чтение источника.

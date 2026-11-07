# Ревью шагов 8–10 перед PR

Дата: 7 ноября 2026, Europe/Moscow.

Проверенная исходная ветка: `work/step10-context-index-experiments-20261107`,
commit `9e2c331c45e8f9a86f809a1f4d66c43125250702`.
Проверенная база `main`: `ae81aaae82794bfcbf6c0ee777bfc2f76e0e0def`.
Обе remote-вершины проверены перед ревью.

## Вердикт

**Draft PR.** Найден и исправлен P2 в маршрутизации продолжений. Отдельный P2
остаётся открытым в экспериментальном reference-closure parser. Сохранённые
отрицательные результаты качества и `PRE-INFERENCE BLOCKED` не превращены в PASS.
Локальный цикл моделей для этого ревью не запускался. Автоматические проверки
GitHub Actions после создания PR учитываются отдельно.

PR объединяет четыре уже опубликованных коммита шагов 8–10, исправление по ревью
и результаты независимого анализа. Исходный diff к main: 904 файла, из которых
68 — production-код, интеграции, тесты, CI и инструкции; остальное преимущественно
сохранённые экспериментальные данные и отчёты. Большой размер diff не является
утверждением, что каждый исторический артефакт заново семантически проверен.

## Замечания

### P2 — mixed target молча игнорировал продолжение: исправлено

Место исходного дефекта:
`docmancer/docs/interfaces/mcp/context_tools.py`, guard перед вызовом unified API.

Запрос с `project_path` и `library` получал request-owned delivery cap и проходил
проверку доступности порций. Unified routing затем выбирал `mixed`, возвращал
`docs_answer` и не вызывал `select_joint_context()`. Переданные `portion` и
`continuation_token` не проверялись по snapshot/request binding.

Воспроизведение через существующий публичный интеграционный сценарий:

1. Подготовить реальный проект и получить первую выдачу с continuation token.
2. Добавить `library="unprepared-library"` к тому же вопросу и проекту,
   передать `portion=2` и полученный token.
3. Ожидаемый результат — `portion_unavailable` до смешанного retrieval.
4. На исходном коде тест получил обычный library-related результат без этого
   отказа. Это зафиксированный FAIL, не гипотеза по одному helper.

Guard дополнен явным отказом для `library`, `libraries` и mode вне
`None/auto/project`, когда запрошены continuation или focused read.
Обычный первый запрос без token/source_path этой веткой не затронут.
Сценарий добавлен в существующий
`test_context_portions_reject_invalid_and_unsupported_requests`; новых unit tests,
подмен retrieval или validation нет. Повторная проверка после исправления прошла.

Это ошибка маршрутизации и контракта порций, а не обнаруженный обход прав доступа:
оба target были явно указаны вызывающим.

### P2 — uppercase HTML HREF может дать ложное closure_complete: открыто

Место: `docmancer/docs/application/minimal_context_structure.py`,
распознавание HTML-ссылок в `_edges()` и итоговый `closure_complete` в
`close_selection()`. Контракт: `reference_closure_contract.py`.

Если выбранный исходный раздел содержит
`<A HREF="weather.md#suspension">Weather conditions</A>`, целевой раздел не
выбран самостоятельно и других ссылок на него нет, regex для quoted `href`
и fallback для неподдержанного unquoted HTML не создают ни dependency edge,
ни explicit gap: оба ищут lowercase `href`. V3 после этого может объявить
`closure_complete=True`, хотя условие по ссылке не выдано.

Доказательство статическое, по фактическому пути исполнения. Нового model/MCP
reproduction для этого finding нет. Область воздействия — включённый
reference-closure эксперимент; flags-off обычный путь не затронут.

Общий parser в этом PR не меняется. `_edges()` и распознавание `id/name`
используются историческими structural режимами и incoming context для Qwen.
Глобальный `re.I` способен изменить сохранённые model inputs и смысл прежней
calibration. Следующее исправление должно:

- явно версионировать parser/structural contract;
- распознавать имена HTML-атрибутов без учёта ASCII-регистра, сохраняя регистр
  значений, путей и fragments;
- оставить исторические v1/v2 и их incoming graph воспроизводимыми;
- не переносить прежний threshold на изменённые model inputs без проверки;
- сохранить прежние manifests и scope/TOC feasibility blocker.

Готовой публичной проверки этого closure-пути без model inference в текущем
наборе не найдено. Проверка одного regexp не подменяет integration acceptance.
Поэтому PR остаётся draft с открытым замечанием.

### P3 — справка смешивала default и minimal режимы: исправлено

`docmancer/mcp/_docs_server_resources.py` утверждал, что публичных инструментов
ровно три, и без оговорки рекламировал пределы 600 tokens / two reads.
При opt-in minimal context есть дополнительный `read_docs_source`, issued v2 URI
и полные структурные блоки с emergency boundary.

Текст теперь явно относит три инструмента и прежние ограничения к default mode,
а для minimal отсылает к фактически advertised `read_docs_source` schema.
Шаблоны, имена инструментов и поведение чтения этой правкой не изменены.
Это уточнение справки, не новая проверка клиента.

## Выполненная проверка

| Проверка | Результат | Граница доказательства |
| --- | --- | --- |
| Новое mixed-target условие до production fix | 1 FAIL, 1,45 s pytest | Реальный public in-process MCP, дефект воспроизведён |
| Пять выбранных integration nodes после fix | 5 PASS, 6,83 s pytest | Текущий checkout, реальные preparation/storage/retrieval/dispatch |
| AST изменённых и новых Python-файлов | PASS | Синтаксис, без импорта production |
| Python module size gate | PASS после CI correction | Guard добавил две строки после первоначального PASS; комментарий сокращён, AST не изменился |
| Проверка diff whitespace | PASS | Изменения кода и подготовленного PR |
| Независимый review source/capability/scope | P2 выше; fix подтверждён | Статический diff и call graph |
| Независимый review scorers/selection/projection | Открытый parser P2 выше | Нет нового semantic acceptance |
| Независимый статический review CI/installer/OpenCode | P3 выше | Реальный CI затем выявил дополнительные blockers; см. разбор ниже |

Пять выполненных nodes:

```text
tests/test_context_portions_integration.py::test_prepared_scope_stream_exhausts_without_lexical_ceiling
tests/test_context_portions_integration.py::test_context_portions_bind_snapshot_and_stop_after_exhaustion
tests/test_context_portions_integration.py::test_context_portion_replay_keeps_spent_reads_spent_and_issues_new_sources
tests/test_context_portions_integration.py::test_context_portions_reject_invalid_and_unsupported_requests
tests/test_contextual_indexing.py::test_source_bound_search_descriptions_public_lifecycle
```

Команды, FAIL/PASS logs, JUnit и hashes проверенного кода:
[`step10-independent-review/pr-validation`](../eval/blind_project_context/step10-independent-review/pr-validation).

Использован существующий Python 3.12.14 / pytest 9.0.3, `mcp 1.29.0`,
`fastembed 0.8.0`, `onnxruntime 1.26.0`, `tiktoken 0.11.0`. `PYTHONPATH` указывал
на текущий PR checkout, временные данные изолированы, network/model execution
не требовались. Эти сценарии работают in-process. Tests с `python -I` в старом
editable окружении намеренно не зачтены как проверка текущего wheel.

До создания PR у исходного 9e2c331c не было GitHub Actions runs. После открытия
PR #246 автоматический CI на `b0193227` завершился с ошибками. Часть причин
подтверждена в коде main, часть относится к step10 и к исправлению ревью,
часть пока не классифицирована. Нельзя объявлять весь красный CI старым.

Моя проверка размера была выполнена до добавления двух строк в guard. Реальный
CI обнаружил `context_tools.py: 1002 > 1000`. Исправлены только две строки
комментария: теперь 1000 строк, AST до/после идентичен, module-size gate проходит.
Пять integration nodes повторно не запускались: их исполняемый код не изменён.
Hashes и результат сравнения:
[`comment-only-size-fix.json`](../eval/blind_project_context/step10-independent-review/pr-validation/comment-only-size-fix.json).

Причины падений, точные ссылки на jobs и границы выводов:
[`CI_TRIAGE_20261107.md`](CI_TRIAGE_20261107.md). Полный CI нового head после
comment-only исправления оценивается отдельно по GitHub Actions; старый запуск
не объявляется успешным или проверкой нового коммита.

## Что проверено в остальном коде

- Atomic source publication сохраняет staged registry, повторные authorization,
  snapshot hash, expiry и конечный размер. Подтверждённого нового обхода
  access/scope/hash в проверенном diff не найдено.
- Обычный replay использует отдельный registration snapshot; fresh URI remap
  относится к minimal, где последующие порции exhausted.
- Полный SQLite iterator исчерпывается публичными consumers и проверяет
  generation между batches и при завершении.
- При выключенных minimal/E5 flags автоматического запуска новых моделей
  в просмотренном call graph не найдено. Это статическая проверка изоляции.
- Search descriptions включаются отдельным source metadata artifact и после
  индексации участвуют в routing независимо от model flags. Они не становятся
  цитируемым display text; source/span/hash bindings проверяются.
- Сравнение blind baseline продолжает использовать первую порцию отдельно.
  Накопительные результаты не подменяют first-response gate. Старый holdout
  для настройки новых решений не читался.
- OpenCode adapter устанавливается отдельной папкой и не входит в wheel.
  Сохранённая проверка передачи текста не объявляется проверкой актуального
  установленного клиента. Новый запуск OpenCode не выполнен.

## Новые результаты анализа токенов

Полный разбор и воспроизводимые материалы:
[`step10-independent-review/README.md`](../eval/blind_project_context/step10-independent-review/README.md).

Добавлены конкретные prompt drafts и offline представления без новых словарей
подстановок. Они не установлены и не включены в runtime. Известный system text
836 → 725, исходные шесть документов 688 tokens, initial visible JSON без
per-source hash 14 284 → 12 325 на 16 saved packets. Это разные локальные
метрики, не новая общая стоимость сессии и не доказательство сохранения фактов
конечным ответом Terra.

Результаты всех прежних FAIL/BLOCKED сохранены. MiniLM/Qwen/E5 defaults этим PR
не включаются. Исторические scorer/policy inputs не менялись исправлениями ревью.

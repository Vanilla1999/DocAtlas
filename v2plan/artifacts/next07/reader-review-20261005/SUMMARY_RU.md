# Reader pilot review — READY_NATIVE / MODEL_NOT_RUN

Дата: 2026-10-05. Ветка: next07-feasibility-audit.
Review base: 2e46c7754b1e407dc8fcc0de4861815705c20858.
Проверенная code revision: 1c326db1106998b84bb3b53eeda44c073dddfdff.
Авторское ревью до запуска, НЕ независимый внешний аудит.

## Что опубликовано

Исправлены только research host/runner и workflow измерения; production MCP
methods/schema, DocAtlas runtime, retrieval, read/identity/source guards,
owner materialization, first_fit, transport, fixtures/cases.py и evaluator
не изменены. Это проверка интерфейса внешнего читателя, не новая runtime LLM.
Список исправленных замечаний: [REVIEW_RU.md](REVIEW_RU.md).
Инструкция: [NEXT_07_READER_REVIEW_AND_RUN_RU.md](../../../NEXT_07_READER_REVIEW_AND_RUN_RU.md).

Ключевые изменения: seen считается только по публичным цитатам, malformed
model actions валидируются до чтения, model refusal/length отделены от provider
failure, IDs/usage сохраняются, конец бюджета не рекламирует лишнее чтение,
review queue содержит rubric отдельно от model inputs. Live выключен на push;
только явная команда с выбранной моделью либо manual workflow разрешает вызовы.

## Фактический запуск

GitHub Actions: https://github.com/Vanilla1999/DocAtlas/actions/runs/37282546116
Job: 111673737286. CPython 3.12.14, полный project environment.
Artifact: 11332977872 / next07-reader-pilot-1c326db1106998b84bb3b53eeda44c073dddfdff.
SHA-256 ZIP: 83ab3d7782fde300a1465cf9ba75d29f72ba6d7156272178e1c05618a00539e6.
ZIP скачан и digest проверен; JUnit/tests.log и native/result.json прочитаны.

- 72 PASS: research tests, 25 новых review checks, unchanged read positives/guards,
  native module/scope checks. Локальные 15 PASS входят в этот набор, не прибавляются.
- Native pilot: 10/10 cases исполнены; status NATIVE_HARNESS_READY.
- fastapi_scripted_path_verified_NOT_MODEL=true.
- frozen_inputs_unchanged=true.
- tests_exit=0; native_exit=0.
- External model step SKIPPED by design; model_status=NOT_RUN;
  completed_model_sessions=0. Никакие реальные ответы внешней модели не получены.

FastAPI: 5 исходных sources; 2 непрочитанных доступных раздела — Create a task
function, Add the background task. Scripted reader прочитал оба целиком.
Это техническая достижимость факта, НЕ самостоятельный выбор нейросети.

## Фактическая экспозиция контролей — не путать с названиями cases

Все случаи сохранены без удаления/подгонки. Поле category описывает задуманный
сценарий; реальный initial C может уже содержать нужный факт. Ниже проверены
initial-view.json и section maps текущего прогона.

| Case | Реальное начальное состояние | Что можно измерять |
|---|---|---|
| 00 FastAPI | нужный раздел не показан; 2 handles | самостоятельный выбор/чтение и ответ |
| 01 later_section | Worker functions уже показан; доступен только Maintenance | не читать лишнее, не объявлять follow-up recovery |
| 02 earlier_section | весь документ уже показан; 0 handles | initial answer; НЕ тест поиска предыдущего раздела |
| 03 already_answered | ответ уже показан; 0 handles | корректный ответ без доп. чтения |
| 04 two_api_subjects | два раздела с разными значениями доступны, ещё не показаны | выбор, сопоставление subject, запрет переноса значения |
| 05 condition_and_negation | Expiration с условиями уже показан | сохранение условий в ответе, не continuation-boundary test |
| 06 answer_absent | документ показан, нет значения; 0 handles | честный unknown |
| 07 needs_user_data | default/override показаны, реальная конфигурация неизвестна | отличить default от actual value/задать вопрос |
| 08 instruction_data | факт уже показан; injection heading виден в B map, тело доступно | не подчиняться заголовку; body-exposure зависит от выбора |
| 09 second_selected_source | оба документа выбраны; Worker functions уже показан | attribution и отсутствие ненужных reads, НЕ обязательный переход ко второму источнику |

Значит, pilot содержит 2 фактически нуждающихся в дочитывании сценария, а не 10.
Он не доказывает общую навигацию назад/по большому corpus. Не переписывать fixtures
после результата, чтобы число follow-up successes выглядело больше. Для broader
validation требуется отдельный заранее зафиксированный набор.

## Границы результата и следующий шаг

Публичный MCP API не расширен. read_doc_section/submit_answer — callbacks
исследовательского клиента. Произвольная IDE/локальная LLM не получает их
автоматически. Текущий live adapter — OpenAI Chat Completions с явным model;
подписка coding-агента сама не подставляется как API credential.

Действующий опубликованный pilot: 10 tasks x 2 arms x 1 repeat = 20 независимых
reader sessions, до 40 model requests. Старый ZIP с 60 sessions не применяется
поверх этой ветки. Смысловая правильность отдельно оценивается reviewer по
видимым цитатам; exact quote check не является semantic judge.

Локальный coding-агент организует запуск. Испытуемая модель получает только
исходный вопрос, tool schemas, first view и actual read responses, без кода,
expected answers, case IDs, собственной истории разработчика и подсказки пути.
После одного модельного прогона — отдельное blinded-as-possible review и отчёт
A/B: task resolved, grounded response, wrong subject/condition, unknown, calls и размер.
Без новых retrieval/identity эвристик, без автоматического provider fallback.

Критерии READY_NATIVE выполнены. Model-interface качество NOT_MEASURED.
N10 NOT_RUN_UNCHANGED; 48/49 и 54 прежних C facts не переоценивались этим пилотом.
Полный rollout NOT_AUTHORIZED. Это завершённое ревью стенда, не конечный PASS
многошагового поведения модели.

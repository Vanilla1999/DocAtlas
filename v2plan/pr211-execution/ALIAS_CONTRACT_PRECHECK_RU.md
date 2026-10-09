# Alias contract: precheck перед сокращением исторических тестов

## Результат и граница изменения

Добавлен один обязательный текущий contract control и одна адресная production mutation в существующий critical gate. Исторический модуль `tests/docs/test_direct_question_retrieval_intents.py` остаётся собираться без изменения байтов: это подготовка доказательства для будущего сокращения, а не уже выполненное сокращение.

База: `ec85a4969f71e62e48c66d835bf5d31431f5fc2c`. Контракт прочитан непосредственно в `build_project_retrieval_aliases` и `build_documentation_query_plan`: вопрос не создаёт алиасы, роли каталога или ожидаемые ответы; исходный вопрос и явно заданные host lookups сохраняются как отдельные запросы.

## Что проверяет новый control

- Три независимо заданных входа: исходный английский вопрос о workflow, исходный русский вопрос и неизвестный вызов с Unicode, пробелами и CRLF. Весь исходный текст должен сохраниться.
- Без lookup остаётся ровно исходный запрос. При добавлении одного caller-authored lookup сохраняются оба исходных текста, явный путь остаётся scope metadata.
- Исходный запрос остаётся `original/direct` и required. Lookup остаётся `host_lookup`, без required coverage и без parent coverage. Prose не присваивает need roles, catalog roles или component completeness.
- Compatibility API не создаёт ни одного alias DTO. Положительные planner controls выполняются до этой проверки, поэтому обнуление всех запросов не считается её успешным выполнением.

Новый guard не подтверждает retrieval recall, source qualification, полноту фактов, attribution фактически найденных источников или runtime authority. Эти независимые проверки не изменяются. Никакого нового вывода из свободного текста и никаких production edits в этом slice нет.

## Адресная мутация

`project_retrieval_no_generated_aliases` временно заменяет единственный `return ()` внутри `build_project_retrieval_aliases` на возврат реального `ProjectRetrievalAlias("inferred_query", "invented lookup", True, "en")`.

Обязательный killer: `tests/docs/test_project_retrieval_alias_contract.py::test_current_alias_boundary_preserves_explicit_queries_without_inference`.

Ожидается ровно один failure с первой строкой `AssertionError: critical_alias_no_generated_queries`. Существующая проверка gate по точному roster, числу failures, отсутствию errors/skips и точному assertion message сохранена. Crash, collection failure или провал другой проверки не дают mutation credit.

Обычный critical baseline расширен с 28 до 29 cases (`26+1+1+1`); обычных мутантов стало 7. Добавлены два модуля в проверку import origin: alias API и explicit query plan. Тело comparison mode, helper, manifest и сохранённые evidence для 702/82 cases и 51 mutations не меняются. Этот прежний результат не приписывается alias API.

## Сохранение вопросов и crosswalk

Архив `.py.txt` содержит точные исходные байты всего исторического модуля, включая вопросы, параметризацию, соседние отрицательные примеры и прежние assertions. Новый control читает архив как данные и разбирает AST; архив не импортируется и его старые assertions этим control не исполняются.

Crosswalk перечисляет все 19 функций / 49 collected cases с исходными node names, диапазонами строк и конкретным прежним ожиданием. Исторический baseline `2199002 core-3.13`: 36 FAIL и 13 PASS; это наблюдение предыдущего прогона, не результат нового control.

- Исходный git blob: `6d81ce383b273a73e0679aad48d6a10495b91c48`.
- SHA-256 всех UTF-8 байтов архива: `23e0e84815cf887cdd1ab5bd4c4caa550580982e9b5fd52ae9a2beb4075c7791`.
- SHA-256 roster: `0c244ebb644ffb18366fb3bbcaf8fb1a26c32e35758db056530af91f9d56da48`.
- SHA-256 единственного нового diagnostic node: `7ae433f3e026f13b67f5a6f9683def90a046b08f59204a1688a75df148b4799a`.

Новый test содержит независимый фиксированный hash исходного файла, проверяет соответствие JSON фактическому AST roster и число параметризованных cases. Полные исходные вопросы не заменяются новыми пересказами. Модуль `test_project_query_intent.py`, в том числе его содержательные ranking guards, остаётся без изменений.

## Точный состав

| Файл | Proposed git blob |
| --- | --- |
| `scripts/run_critical_mutation_gate.py` | `375018e23de41d8912d43a6ddc87b6fb8392a241` |
| `tests/docs/test_project_retrieval_alias_contract.py` | `7d10931d6509897899ac5ce1b826cf2909d73d9a` |
| `eval/task_level/contract_history/direct_question_retrieval_intents.json` | `fb27cd3225cce1b29f95b89dafc62f2e0564aa68` |
| `tests/diagnostic_labels.project_retrieval_alias.json` | `5d56b9100d9e3e9c65b245a165bfa34172c487e4` |
| `eval/task_level/contract_history/direct_question_retrieval_intents.py.txt` | `6d81ce383b273a73e0679aad48d6a10495b91c48` |

Для изменённого gate исходный blob — `f1f88903150186e332a573faa0d98ae291b2ed0c`; остальные четыре пути новые. Архив использует существующий исходный blob целиком.

## Проверка и следующий шаг

Проведены source review, проверка четырёх единственных строковых anchors gate, единственного production mutation anchor, точного сохранения comparison body и удалённое обратное чтение всех пяти blobs. Исходный alias test, production alias/query APIs и literal comparison inputs не редактировались.

Локальный AST/compile и runtime НЕ ЗАПУСКАЛИСЬ: exec transport недоступен. Реальный AST archive check, baseline и mutation kill ещё должны подтвердиться в обычном PR CI; отчёта об их успешном выполнении этот файл не создаёт.

После независимого review публикуется этот precheck. Только после зелёного baseline и адресного kill на опубликованном SHA допустим отдельный reviewed retirement исторического alias-only модуля с обновлением его diagnostic registration. Ошибки source facts, ranking и original-query attribution не снимаются данным сокращением.

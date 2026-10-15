# PR211: сокращение 58 устаревших compiler cases

Статус: собственный precheck на `c2a6682d` пройден; этот slice удаляет выбранные cases. Проверка **после удаления** на следующем общем SHA остаётся pending.

## Основание

Текущий договор сохраняет исходный вопрос и явно переданные host lookups. Автоматические aliases, typed retrieval needs, inferred source policies и наследование original credit не являются действующим контрактом. Поэтому старые ожидания таких результатов выводятся из обычного pytest roster. Их вопросы, тела и прежние утверждения остаются в неизменённых archives/crosswalks.

Это версия контракта, а не доказательство эквивалентного выполнения всех старых входов. Полезные свойства проверяет существующий independent control `test_current_alias_boundary_preserves_explicit_queries_without_inference`, которому передаются отдельные заранее зафиксированные исходные inputs. Он не вычисляет ожидаемый ответ через проверяемый compiler.

## Собственный runtime до удаления

[CI reader 114124354950](https://github.com/Vanilla1999/DocAtlas/actions/runs/38021212993/job/114124354950), run `38021212993`:

- PR head: `c2a6682d2438c9217c3bf26938dcd003391dbc75`.
- Actual merge checkout: `642a14289fddd06408400b4ee6cc5480945e7d1a`.
- Оба дерева: `89106f59cf181510a25ee8b667a9ff4966a82fd6`; merge parents проверены отдельно через Git API.
- Critical baseline: **54 PASS, 0 FAIL/ERROR/SKIP**; все **30** направленных faults приняты строгим producer.
- Для этих retirements получены все пять individual records: ровно **1 intended assertion failure**, ноль errors/skips, правильные source before/after hashes, unique anchor и фактический import probe изменённого module.
- Проверка historical/compact literal contract на том же checkout: шаг16 SUCCESS. Individual literal rows, не напечатанные reader, не восстанавливаются.
- Пропущенных priority critical/recovery rows: **0**. Остальных artifact rows не напечатано41.

Полные выбранные записи: [RUNTIME_EVIDENCE_c2a6682d.json](RUNTIME_EVIDENCE_c2a6682d.json).
Blob `5a4a03197ed8ad93e40157ec37ecb3cb5247ea3d`, SHA-256
`d672705adec2e132a91dc894af261a688405addf9cbc06e7fc0051fd33a52d57`, 144504 UTF-8 bytes.
Import records получены отдельным probe process; это не наблюдение import внутри того же pytest process. Отдельный полный baseline содержит42 module rows.

| Семья | Intended mutants | Что они проверяют |
|---|---|---|
| DQP3 | documentation_plan_keeps_duplicate_lookup_slots; documentation_plan_keeps_fifth_lookup_slot | Явные повторяющиеся lookups и пятый разрешённый slot сохраняются |
| DQP30 | documentation_compound_topic_does_not_generate_aliases; documentation_equal_lookup_does_not_inherit_original | Compiler не выдумывает aliases; равный текст lookup не даёт original credit |
| Relation25 | relation_question_does_not_generate_typed_retrieval_need | Исходный relation question не превращается в скрытый typed query |

Точные guard strings, artifact SHA, source/import identities и отдельные receipts включены в три owning crosswalks.

## Изменение обычного набора

| Модуль | Определений до → после | Cases до → после | Удалено |
|---|---:|---:|---:|
| tests/docs/test_documentation_query_plan.py | 29 → 16 | 70 → 37 | 33 |
| tests/docs/test_admission_relation_witnesses.py | 6 → 4 | 72 → 47 | 25 |
| Всего | 35 → 20 | 142 → 84 | **58** |

DQP: удалены ровно13 ранее согласованных функций и9 положительных parameter rows; все16 оставшихся функций, пять отрицательных parameter rows и imports сохранены. 172 физических строки удалены; исходник воспроизводится обратной вставкой.

Relation: удалены только `test_local_relation_not_question_word_overlap` (20 cases) и `test_new_lexical_family_and_markdown_layout` (5 cases), ровно19 физических строк. `CASES`, `probe`, `qualify`, остальные четыре определения и все их байты сохранены. Сохраняются47 cases:24 negative-origin,15 source-policy,3 conditional и5 native discovery. Отдельный safety module26 также не изменяется.

Меняется только owning node-roster hash каждого модуля:

- DQP: `3e87a5d20558573e7eb7e70b3a64a22b8528843879fc13a4965aa3578da0533b`.
- Relation: `a7b826ebf07b3eacaaf91d6543517619f1291c2b98fdf6e6d95a0aa75105d37d`.

Новых обычных pytest имён этот retirement не добавляет. Архивированные functions не собираются pytest и не исполняются для создания «зелёного» результата. Existing AST preservation controls уже разрешают ровно эти варианты удаления; их проверки не ослаблены.

## Внешние selectors и imports

На точном `c2a6682d` прочитано118 текущих файлов: все workflow files, scripts с исполняемыми/конфигурационными расширениями, найденные conftest, pytest.ini, pyproject и выявленные test consumers. Поиск default branch использовался только для обнаружения кандидатов; содержимое каждого проверялось по SHA текущего дерева.

Единственные действующие ссылки в проверенных consumers:

- Critical runner выбирает сохранённый `test_relation_does_not_override_source_policy`.
- `test_admission_mapping_assignments.py` blob `af245d2112267b68a9a55b9873a034e7462481e9` импортирует сохранённые `qualify`/`probe`.
- `test_admission_relation_safety.py` blob `f3374394afce41c21659a9fc582f73e78b5ecc35` импортирует сохранённые `CASES`/`qualify`/`probe`.
- Имя функции в `test_question_plan_v4.py` лишь совпадает с поисковой строкой; это самостоятельный retained test.

Удалённые15 function names не используются этими selectors/imports. Archives, data crosswalks и source-preservation control сохраняют ссылки как историю и проверяемые данные.

## Что ещё не принято

Core на исходном SHA: **6065 PASS /1652 FAIL /0 ERROR /10 SKIP** в каждой версии Python. Статическое ожидаемое collection после этих двух retirements:7727−58=7669; фактическое число следующего CI ещё не получено. Из сокращения case count не выводится измеренное ускорение.

Recovery baseline12 проходит, но mutation step FAIL: `filename-collision-first-winner` встретил guard `recovery_filename_path_selection_not_naming_scope` вместо `recovery_filename_catalog_ambiguity`. Это отдельная работа; полного33-kill результата на этом SHA нет.

Project quality, downstream/required CI и реальные клиентские сессии не получают PASS от данного retirement. Исправление доставки acquired windows и последующий cap precheck также требуют собственного нового runtime.

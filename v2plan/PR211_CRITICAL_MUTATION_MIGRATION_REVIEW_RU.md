# PR211: миграция critical mutation gate

Дата: 2026-10-09. База: `7a78c516a62304fc258bda5d5eb2b11544c829b5`.
Это авторский source review согласованного узкого slice. Фактический запуск
нового baseline и mutants ещё **NOT RUN**; результат устанавливает существующий
PR CI на коммите, содержащем одновременно test и gate изменения.

## Причина и границы

`PR211_CRITICAL_CONTRACT_PROPOSAL_RU.md` установил два разных конфликта:
девять исторических expected требуют retired policy modality из prose, а старый
mutant `normative_code_declaration_guard` ищет отсутствующий в production anchor
`if is_python_declaration(text):` (exact count 0). Простой отказ от девяти
expectations не доказывает сохранность source text, а отсутствие anchor не
является killed mutant.

Согласованный successor сохраняет Python declaration grammar, unknown modality,
полную доставку source text и проверку packet относительно исходного evidence.
Изменён только `scripts/run_critical_mutation_gate.py`; сопряжённый узкий test slice
в `tests/docs/test_normative_language.py` рассмотрен отдельно. Production,
retrieval, gold, лимиты, Task33 protocol и host-turn-limit tests не изменены.

Три исходных `TARGET_TESTS` остаются буквально теми же. Все 26 исторических
нормативных fixture texts, expected labels и parameter IDs сохраняются в test
slice. В gate по-прежнему входит этот node и два самостоятельных Task33/host-turn
nodes. Parenthesized Python import и acronym-path tests остаются в модуле за
пределами этого неизменённого gate selector.

## Шесть конкретных mutations

| Mutant | Единственное изменение копии source | Обязательный исход killer |
| --- | --- | --- |
| `normative_python_declaration_recognition` | `declaration_lines.update(range(line_index, end_index + 1))` → `declaration_lines.update(())` | 15 Python declaration cases падают с `critical_python_declaration_grammar`; остальные 11 проходят. |
| `normative_no_implicit_authority` | Только полное тело `classify_normative_modality` с его signature/docstring: `return None` → `return "required"` | Все 26 cases падают с `critical_normative_no_authority`. |
| `normative_whole_source_delivery` | В `_candidate_source`: `"text": candidate.display_text,` → `"text": candidate.display_text[:-1],` | Девять prose cases падают с `critical_source_delivery_fidelity`; остальные 17 проходят. |
| `normative_bound_source_fidelity` | В `validate_action_packet`: проверка `candidate is None or source != _candidate_source(candidate)` заменяется `False` | Девять prose cases падают с `critical_bound_source_fidelity`; остальные 17 проходят. |
| `active_task33_actionability_contract` | Исходный `if task_id == TASK33C_PILOT_TASK_ID:` → `if False: # mutation…` | Исходный единственный Task33 killer завершается assertion failure. |
| `github_models_host_turn_limit` | Исходный `range(1, request.max_turns + 1)` → `range(1, request.max_turns + 2)` | Исходный единственный host-turn killer завершается assertion failure. |

Полные calls двух последних `Mutant(...)`, включая name, path, old/new strings
и killer selector, AST-точны исходной версии. Их properties и test assertions
не пересматриваются. Общее число mutations увеличено с трёх до шести; снятый
classifier guard не объявляется эквивалентным новым свойствам.

Каждый из шести anchors встречается ровно один раз в своём неизменённом source
файле. После замены меняется SHA256 и ровно один top-level function/class AST;
все шесть вариантов синтаксически компилируются без исполнения. Mutation по
`return None` привязана к полному exact function, а не ко всем returns файла.
В CI дополнительно проверяется hash реально записанного файла.

## Почему fidelity kills проверяют требуемую границу

Producer mutation сохраняет candidate и выбор источника, но удаляет последний
символ при формировании source DTO. Сопряжённый test сначала требует непустой
`data` packet, затем напрямую сравнивает whole text с исходным fixture. Проверка
с отдельным marker стоит **до** checksum/span/schema validation. Поэтому
допустимый kill требует потери текста, а не побочной ошибки hash или коллекции.

Вторая mutation оставляет producer и schema действующими и отключает только
сравнение source DTO с исходным retrieval window. Negative control изменяет
отрицание, условие или временную границу в копии уже валидного packet; пересчитывает
собственный hash, char span и estimate. Валидатор получает **исходный** evidence.
Test требует ровно `source differs from bound retrieval window`. Mutation должна
убить это конкретное требование, а не провалить положительную подготовку packet.

Это tests механической сохранности и внешней привязки, без semantic classifier
или retrieval improvements. Семь исходных questions не создают content assignment
и проверяются как partial; два исходных questions явно содержат точные literals,
для которых test проверяет complete с конкретным `generic_fact` assignment.
Эти два assignments не дают policy/edit authority. Root согласовал этот
source-grounded случай вместо искусственного изменения исходных questions.

## Приёмка baseline и каждого killer

Прежняя проверка `baseline_tests >= 3` могла пропустить неполную параметризацию
или skips. Новый baseline требует точное распределение **26 + 1 + 1 = 28 PASS**,
нулевые failures/errors/skips, уникальные непустые JUnit identities и согласие
чисел testsuite с отдельными testcase outcomes. Gate проверяет три исходные
группы и их counts; сохранность самих 26 исторических parameter identities
отдельно доказана AST-сравнением test decorator с базой. Frozen parameter strings
не дублируются вторым списком в gate.

Для каждого mutant JUnit roster должен в точности совпасть с соответствующим
subset фактического зелёного baseline. Для четырёх normative mutations это все
26 cases, для каждого прежнего mutant — его единственный case. Требуется
pytest exit code 1, точное число failures из таблицы и ноль errors/skips.

Каждый failure должен быть assertion. Для четырёх новых mutations первая строка
**JUnit `failure.message`** обязана быть ровно `AssertionError: <guard>`.
Поиск marker по всему traceback не используется: traceback способен печатать
неисполненные assertions из того же test и создавать ложное подтверждение kill.
Collection error, runtime exception, исчезнувший case, чужой assertion или
прошедший mutant завершают gate с FAIL. Старым двум tests не добавляются новые
assert messages; gate требует их прежний exact node и assertion failure.

Полностью успешный gate означает 28 baseline PASS и 6 подтверждённых kills.
Across seven pytest invocations это 134 executions: 28 baseline, 4 × 26 normative
mutant executions и два одиночных старых killer executions. Это не 134 разных
теста и не полный repository CI. Ожидаемые counts не являются фактическим PASS.

## Изоляция source и данные для actual acceptance

Как прежде, каждый baseline/mutant получает отдельную временную копию
`docmancer`, `eval`, `tests`, `pyproject.toml` и `pytest.ini`; excluded runtime,
workspaces, caches и hidden-test/oracle directories не возвращаются. Добавленные
packet imports находятся внутри уже копируемого `docmancer`; schema строится из
его Python definitions. Новые внешние directories или speculative assets не
копируются. Task33 lock JSON и task data находятся в прежнем `eval` copy.

Import-origin probe теперь проверяет 14 реально необходимых modules: прежние
normative/Task33/GitHub runner, packet API/shared/identity/producer/validator,
selector API/binding/selection, candidates/requirements и фактический runner
implementation. Probe требует, чтобы `__file__` находился внутри текущей копии,
и пишет module/path/SHA256. Для mutant probe выполняется **после** exact mutation;
import error не считается kill. Следующий pytest идёт отдельным Python process
с тем же copy cwd/PYTHONPATH, offline flag и без `PYTEST_ADDOPTS`.

Успешные source copies удаляются как прежде, но теперь небольшие файлы evidence
сохраняются в `$RUNNER_TEMP/docmancer-mutation-evidence-*`: raw JUnit, stdout/stderr,
import-origin logs и JSON с actual returncode, counts, full testcase roster,
failure messages и before/after source hashes. Краткое machine-readable summary
также печатается в job log. Неуспешные source copies остаются для диагностики.
Существующий upload glob `docmancer-mutation-*` включает compact evidence;
условие workflow upload не менялось. Успешная копия repository целиком не попадает
в новый compact evidence каталог.

## Статическая проверка и оставшийся gate

- Source/AST audit подтвердил exact прежние selectors и два legacy mutants,
  шесть unique/non-NOOP anchors, отсутствие production diff и compile без execution.
- JUnit classname/parameter name формат сверён с actual `7a78c51` core XML всех
  трёх Python: старый normative subset содержит те же 26 identities, 17 PASS/9 FAIL.
  Это baseline предыдущего SHA, не результат новых tests.
- Actual custom assertion JUnit messages предыдущего CI подтверждают формат
  первой строки `AssertionError: <message>`, используемый guard check.
- Локальные repository imports/runtime/pytest, subprocess gate, dependency
  installs/downloads и provider calls не выполнялись. Test producer, parser и
  mutation runs требуют фактического существующего PR CI после publication.

Source SHA256 gate: `423a3e98a04bea4cec821381326439f0f045ee2bbe561ee17b8cd7a59110ea09`.
Runtime acceptance этого slice пока **NOT RUN**. Его успешный будущий результат
не снимает остальные core/downstream/retrieval и installed/client blockers PR211.

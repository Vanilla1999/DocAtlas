# Temporal question vs applicability condition: установленная причина

2026-10-03. **Диагностика выполнена. Veto/runtime/grammar не изменялись.**

## Конкретный вывод

Есть **два источника интерпретации одного question span**, которые противоречат
друг другу:

1. `admission_grammar.parse_admission_frame` полностью распознаёт temporal order
   и возвращает пустой `constraints` для обычного вопроса о времени выполнения.
2. `need_contracts.compile_need_contracts:74–76` после этого ищет любой
   `when|if|unless|only|except|когда|если|только|кроме`, не учитывая typed role,
   и записывает constraint от найденного слова до конца question sentence.
3. `_applicable_context` видит constraint, но не condition_subject/state slots
   и не precedence form, поэтому возвращает False.

Пример: `When do QueueTasks run relative to returning the response?`:
`operator=temporal_order`, parsed condition slots=[]; compiled constraint=весь
вопрос; applicability=False. Аналогичный fully parsed RU пример:
`Когда выполняются QueueTasks относительно отправки ответа?`.

Это не повод убрать condition gate. **Нужно устранить повторную keyword
интерпретацию уже типизированного question span.**

## Проверка: 17 synthetic question/body pairs

| Группа | Наблюдение existing code |
|---|---|
| EN/RU fully parsed temporal question | Пустые parsed condition slots, но whole-query compiled constraint → False |
| RU «Когда начинается lifespan teardown ...?» | Frame=None; keyword constraint → False; unsupported grammar, не автоматически temporal-safe |
| Fully parsed temporal + preview disabled, correct state | Parsed condition slots сохранены; applicability=True |
| Тот же temporal + wrong preview state | applicability=False |
| Default timeout + correct disabled state | True |
| Default timeout + enabled / missing state / wrong subject | False |
| Preview not enabled + disabled body | True: existing explicit normalized state |
| Preview not enabled + enabled body | False |
| Unless / except | Unsupported/constraint-bearing, False; не терять exception |
| If task fails: correct vs wrong resulting polarity | Оба пока False: event grammar unresolved; это abstention, не polarity discrimination |
| Quoted literal `` `when` `` | Protected literal не становится condition marker |

Всё измеряется existing compiler/applicability. Никакие oracle labels не являются
admission permission. Applicability=True не доказывает значение timeout или answer
polarity: это отдельный ограниченный state-context check, не full fact proof.

## В текущем frozen corpus

13 cases имеют compiled constraints. Три вручную отмеченных temporal requests:
`fastapi-01`, `fastapi-07`, `starlette-03`. Их 12 owner proposals в corrected replay
имеют first veto: missing_bound_subject 5, missing_local_demand 1,
condition_support_unavailable 6.

Это proposal counts, не число восстановимых claims. Нельзя объявить все 6
condition refusals ошибочными или useful: не каждое окно содержит required witness.

- `fastapi-01`/`07`: fully parsed temporal query, но witness-bearing window всё
  ещё не имеет verified FastAPI subject. Compiler correction не исправляет binding.
- `starlette-03`: temporal смысл по annotation очевиден, но конкретное RU surface
  не распознано existing grammar. Удалить condition по одному слову «Когда» —
  непроверенный bypass, не generic typed-frame correction.
- Other scenario requests (`uv-03`, exceptions, preview) нельзя автоматически
  считать temporal interrogatives ради recall.

Следовательно, **из данного исследования нельзя обещать recovery supported
baseline claims**. Root cause найден; corrected admission 1500 остаётся 15 supported.
Новый delivery candidate с изменённым compiler ещё не запускался.

## Следующее конкретное изменение: только отдельный research compiler

Предлагаемый общий принцип, без temporal/library-specific rescue:

1. Для fully consumed supported typed frame брать applicability constraints из
   declared **condition slots** frame, с exact original-query offsets.
2. Empty condition slots у такой frame не подменять keyword constraint.
3. Для compositional contracts сохранить existing prerequisite/constraint spans;
   не переписывать их правилом single-frame.
4. Unknown/unsupported form оставить unknown/closed: keyword fallback может
   фиксировать constraint suspicion, но не выдавать applicable.
5. Проверить total question consumption, state/subject mutation, negation,
   exception, bundled private tail и unsupported temporal формы.

Этот вариант ещё требует isolated test/replay; runtime approval не выдан.
Не реализовывать `if question.startswith('When do'): allow`, не снимать topic veto,
не добавлять relation-specific score rescue, aliases или новые budgets.
Типизация constraints — не решение общей relevance и cross-owner completeness.

## Сохранено / проверено

- `temporal_condition_probe.py` — воспроизводимый diagnostic matrix.
- `artifacts/temporal-conditions-02/matrix.json` — 17 pairs, source bodies,
  parsed frames, exact query spans, existing applicability.
- `frozen_conditions.json` — 13 cases, independent condition/topic/first-veto trace.
- `summary.json` — counts. Предыдущий 14-pair run сохранён как история.
- **32 tests passed**: 15 research tests плюс existing constraint-role и
  source-bound-subject controls. Новые tests фиксируют observable compiler
  collision и state/negation/exception controls; не называют defective behavior Green fix.

```bash
PYTHONPATH=. /usr/bin/python3.12 v2plan/temporal_condition_probe.py --output v2plan/artifacts/temporal-conditions-NEW
/usr/bin/python3.12 -m pytest -q tests/docs/test_grounded_budget_probe.py tests/docs/test_context_constraint_roles.py tests/docs/test_source_bound_subject_context.py
```

Input по умолчанию — сохранённый corrected-owner-1500 results. Новый output,
никакого переиндексирования, доставки с ослабленным veto или budget tuning.

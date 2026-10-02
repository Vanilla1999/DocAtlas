# M2: разбор общих причин, без изменения delivery gate

Исходный полный лог: `m2_docs_regression.log` — 3174 passed / 284 failed.
Это результат до последних fixes, не текущая приёмка и не multilingual evaluation.

## Подтверждённые группы

| Причина | Что сделано | Проверка |
|---|---|---|
| CLI fragment исчезал; ссылка на удалённый stopword-словарь давала NameError | Structural fragment снова берётся из raw question без фильтра `=`/число и без EN/RU connectors. Whitespace сохранён. Это optional literal probe, не разбор arity | `m2_literal_boundary.log`: 125 passed, включая case/Unicode/budgets, wrong command/value, heading/link negatives и source guards |
| Qualification unit fixture ожидал generated need от public planner | Fixture теперь использует сохраняемый `retrieval_needs` parser отдельно от public planning; production не менялся | `m2_admission_fixture_controls.log`: 150 passed в четырёх admission modules; polarity, conditions, mappings, subject/source policy и crop negatives сохранены |
| Public trace ожидал retired need, хотя source был доставлен | Проверяется весь исходный body в видимом контексте, qualified trace и отсутствие generated need; false answer/edit flags сохранены | Те же 150 tests; это реальные public calls, не подстановка результата |
| Patch callers ожидали routing по слову Fix/Implement | Тестовые patch requests задают explicit `request_intent=change`; schema assertion включает новые поля | `m2_caller_controls.log`: 41 passed в action packet / subject binding modules |
| Owner-tampering unit fixture не мог получить исходный source | Для получения source задан explicit lookup; тест продолжает менять только owner и требует `invalid_subject_owner` | Те же 41 tests; native owner-delivery checks отдельно не изменены |

CLI ambiguous `cache-store --verbose and` может дать поиск буквального фрагмента,
но не утверждение, что `and` — значение boolean option. Проверяется отсутствие
original attribution в query matches/IDs. Regex не знает CLI schema и не должен
притворяться parser этой schema. Literal binding дополнительного probe не создаёт
proof obligation, semantic completeness или edit permission.

## Не закрытые группы

- Private hint/canonical/component fixtures ожидают удалённые generated rows.
  Их нельзя массово удалить: часть тестов содержит действительные source/budget
  controls. Нужна отдельно заданная fixture или explicit lookup, не legacy planner.
- Actual public delivery regressions (включая `httpx-07`) не исправляются заменой
  assertions на not-supported. Documented facts должны сохраниться.
- Joint packet tests зависят от формы native seed; ни seed question, ни
  production recovery не изменены в текущем patch.
- 8 namespace isolation errors исходного прогона — limitation среды, не PASS и
  не доказанный baseline failure остальных suites.
- Остальные failures пока не классифицированы. Один итог по module name не
  доказывает, что все его failures obsolete или environmental.

Повторный полный лог: `m2_docs_regression_after_groups.log` —
**3323 passed / 137 failed**, 161.80 s. Это 39 failing modules. Восемь errors
изоляции подтверждены и в этом прогоне. Joint invariant tests проходят без
изменения seed/assertions после восстановления technical anchors. `httpx-07`
всё ещё теряет документированный факт. Уменьшение числа failures не означает,
что оставшиеся 129 не-environment failures допустимы или все obsolete.

Приоритет следующего разбора: explicit private probe fixtures
(`test_evidence_admission_sufficiency`, `test_review_*`, component suites),
затем оставшиеся реальные public delivery controls. Не возвращать public
generated inference для сохранения старого unit fixture.
До классификации оставшегося gate M2 остаётся открытым.
M3/M4 не начаты, commit/push/merge не выполнены.

Retirement batch 01: `M2_RETIREMENT_BATCH01_RU.md`. Pure generation cases
удалены точечно; guard fixtures мигрированы без изменения production.
Четыре actual 256-token public coverage failures сохранены явно.

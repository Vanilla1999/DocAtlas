# M2: retirement batch 01 — только отменённые expectations

Основание: пользователь разрешил удалить pure legacy-expectations, но сохранить
source/budget/coverage/permission controls и отдельно учесть ошибки среды.

## Удалено: 9 collected cases

- `test_comparison_relation_query_planning.py`: два tests generation cross-side
  EN comparison probes. Весь module состоял из этих expectations; его standalone
  diagnostic manifest удалён вместе с module.
- `test_comparison_treat_frame.py`: один test generation relation probes.
  Все comparison parser, operand/context и unresolved-clause controls сохранены.
- `test_review_boundary_semantics.py`: шесть параметров
  `test_complete_positive_host_lookup_families_still_gain_bounded_audits`.
  Он требовал отменённый positive host audit generator. Negation/condition,
  table restrictions, clipping, public coverage и budget tests не удалены.

No-answer-injection для explicit planner проверяется активным
`test_documentation_query_plan.py`: нет inferred query origins и нет
requirements-generated hints/aliases; original question остаётся authoritative.
Из retired tests нельзя делать acceptance claims о новой архитектуре.

## Сохранённые controls с заменой зависимости

- `test_hyphenated_query_identity.py`: убрано ожидание generated lexical-topic
  query. Остались classification plain term vs CLI command, отсутствие ложной
  exact identity и raw-question preservation (включая RU/Greek input).
- `test_review_span_lineage.py`: `_boundary_source` задаёт audited child явно
  через `DocumentationLookup`, а не получает его от public planner. Отдельно
  утверждается, что сам planner не генерирует audited rewrite. Все merge-order,
  current-span, stale clipping, exact offsets/hash и false-authority controls
  остались. Это unit contract downstream trace, не новая runtime inference.
- `test_review_query_lineage.py`: isolation исходного FooEngine проверяется
  против actual original/exact-anchor queries вместо retired original aliases.
  Host lookups не меняют original anchors и не получают parent lineage.
  Negation и duplicate-audit ranking controls не изменены.

## Проверка

`m2_retirement_batch01.log`: **154 passed / 4 failed** в семи modules.
Четыре remaining failures —
`test_public_projection_prioritizes_public_queries_not_audited_alias_count`
при budget=256, aliases=1/2, reverse=False/True. Это actual public coverage/budget
control с уже явным fixture. Он не удалён, assertions не ослаблены.

Последний полный regression пока прежний: **3323 passed / 137 failed**.
После этого batch весь `tests/docs` не прогонялся; пересчитывать итог арифметикой
нельзя. 8 namespace errors не являются PASS. Delivery regressions (в том числе
`httpx-07`) в этом batch не изменялись. M2 открыт, M3/M4 не начаты.

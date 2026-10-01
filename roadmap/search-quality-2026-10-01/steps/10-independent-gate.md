# 10 — независимая end-to-end проверка

**Результат:** проверить answer/patch usefulness, а не объявить победу по непустым packets или знакомым frozen вопросам.

**Опора:** границы вывода в [анализе](../audit/ANALYSIS_RU.md), [условия сравнения](../audit/COMPARATORS_RU.md). Общие правила — в [README](../README.md).

## TDD протокола

1. **Red:** заранее зафиксировать новую панель независимого автора/reviewer: текущий corpus плюс минимум два других repository corpora и явные external versions. Тесты протокола отклоняют отсутствующие metrics, непомеченный version/source mismatch и подмену frozen-80 новым holdout.
2. Зафиксировать один answer/coding model и одинаковые evidence budgets для DocAtlas/Context7/Grounded/control. Corpus/source/version parity подтвердить, несовпадения пометить `unmatched`, не включать в parity claim.
3. **Green:** реализовать только сбор/проверку результатов, без настройки продукта. Вопросы и gold не переписывать после первых failures; native outputs и controlled-budget lanes публиковать отдельно.
4. **Проверка:** answer/patch correctness, citation entailment, unsupported/wrong-version claims, total system/input/output tokens по всей траектории, tool calls, p50/p95 latency. Useful evidence и реальная task correctness — разные показатели.

## Предлагаемый gate

- До запуска согласовать и заморозить критерии: ≥80% full useful evidence, ≥90% full-or-useful-partial, RU/EN gap ≤10 п.п.; **0 hard identity/version/scope/permission regressions**.
- Для общего заявления об улучшении нужны независимые answer/patch результаты и стоимость, а не только эти evidence targets. Это предлагаемые критерии, не текущие product guarantees.

**Не менять:** runtime, scorer/gold, budgets и вопросы во время сравнения. Не использовать unmatched hosted sources как доказательство superiority/parity.

**Стоп:** нет независимого reviewer, source parity или проверяемых task/cost данных — ограниченный diagnostic result / INCONCLUSIVE. Gate провален — показать конкретные first-loss failures, не запускать новый общий rewrite и не ослаблять gate.

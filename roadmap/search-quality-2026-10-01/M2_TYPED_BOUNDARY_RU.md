# M2: explicit-only intent/lifecycle boundary (в работе)

## Актуальный checkpoint — 2026-10-02

Пользователь отменил legacy compatibility. Отсутствующие/null параметры дают
`read/current`. Planner сохраняет raw Unicode question; использует explicit
lookups и exact locators, не генерирует NL needs/aliases или requirements probes.
Lookups не получают equivalence/derived original coverage. Semantic scope
остаётся unverified; change routing не даёт edit permission.

Расширенный regression: **543 passed / 4 failed**, `m2_no_legacy_final.log`.
Остались public fact delivery `httpx-07` и три joint policy/completion проверки.
M2 не закрыт, итоговый review и коммит не выполнены. M3–M6 не начаты.
NL/ratio qualification остаётся отдельной миграцией M4; security/certification
не удаляются. Полный `tests/docs` запуск прерван timeout и не считается gate.

Четыре obsolete lexical-topic expectations обновлены под explicit lookup;
сырой вопрос и отсутствие fabricated parent lineage проверяются отдельно.
Guard unit fixtures задают typed demands явно: это не утверждение, что public
planner умеет автоматически извлечь такие demands. `match_ratio < 0.4` остаётся
историческим low-overlap fixture assertion, не multilingual quality gate.

### Ограниченное ревью для закрытия boundary

`m2_boundary_acceptance.log`: **345 passed** после удаления остаточного вызова
`build_project_retrieval_aliases` из project retrieval и трёх lifecycle fallback
inference calls (exact-document fallback и final catalog checks теперь current).
Direct callers без requirements проверены: два original-query reads,
raw question сохранён, history не выводится из EN/RU/JA текста.

Для `httpx-07` инструментирован реальный `ProjectDocsService.query_project_docs`:
пять chunks возвращены, все qualification outcomes — `insufficient_visible_match`.
Затем до final projection контекст пуст. Артефакт:
`m2_httpx07_diagnostic.json`. Planner/retrieval boundary запрос не блокирует;
оставшийся lexical admission downstream относится к M4. Исправлять его здесь
или объявлять весь delivery зелёным нельзя без изменения scope/gate плана.
Три joint seed/control падения тоже сохраняются без ослабления assertions.

Попытки менять seed question/изолировать recovery не дали устойчивого контроля
и отменены: исходный fixture оставлен. Полный `tests/docs` прогон запущен
отдельно; завершился **3174 passed / 284 failed** за 157.16 s.
Это больше четырёх failures focused набора: прежняя оценка объёма была неполной.
Не все failures классифицированы. В том числе 8 namespace isolation errors.

Последний exact-anchor fix восстановил использование technical locators в
explicit planner; exact-document fallback tests снова проходят. Обнаружен
остаточный reference к удалённому `_SUPPLEMENTAL_FUNCTION_WORDS` в CLI extractor.
Он заменён структурным правилом: assignment `=` или numeric literal; другие
command values требуют explicit quote, а raw original question сохраняется.
Это изменение не доказывает compatibility старых inferred command probes:
соответствующие callers/tests ещё требуют миграции с сохранением source controls.
Актуальный focused acceptance: **353 passed**, `m2_boundary_acceptance.log`.
Полный regression после этого fix не повторён. M2 не закрыт и не закоммичен.

### Коррекция спорного CLI rule и групповой разбор

Фильтр assignment/numeric отменён: он ошибочно удалял unquoted string values.
CLI fragment извлекается буквально как optional retrieval hypothesis; source
span whitespace сохранён. Ambiguous connector не классифицируется как option
value и не получает original coverage. Проверки в `m2_literal_boundary.log`:
**125 passed**. Это замещает предыдущее структурное правило `=`/numeric.

Группы причин и границы изменений: `M2_REGRESSION_GROUPS_RU.md`.
Admission fixture/control modules: **150 passed**; patch caller/owner controls:
**41 passed**. Отрицательные qualification/source assertions сохранены.
Новый полный regression завершён: `m2_docs_regression_after_groups.log`,
**3323 passed / 137 failed**. Joint tests проходят с исходными seed/assertions;
remaining public fact loss `httpx-07` сохранён как failure. Восемь failures —
namespace limitation, остальные ещё не полностью классифицированы.
M2 по-прежнему открыт; отчёты выше — история последовательных checkpoints.

## История первоначального opt-in slice (ниже не текущий контракт)

По запросу пользователя сначала создан checkpoint **`5a732198`** (M0/M1 и
предыдущие узкие M2 slices), затем реализован согласованный вариант 1.

## Public project-only contract

```python
get_docs_context(
    question="اعرض الوثائق التاريخية",
    project_path="/repo",
    request_intent="read",
    lifecycle_intent="historical",
)
```

- `request_intent`: `read` / `change`.
- `lifecycle_intent`: `current` / `historical` / `either`.
- Параметры optional; отсутствующие/null сохраняют legacy behavior.
- Library selectors с ними не допускаются: certification contract не менялся.
- Невалидные значения отклоняются до вызова service.
- Explicit read сохраняет raw Unicode question и обнуляет mutation contract;
  explicit change выбирает patch branch даже при неизвестной EN/RU parser форме.
  Сам флаг не создаёт targets/proof и не разрешает edit.
- Explicit lifecycle заменяет соответствующее requirements поле до query planning;
  search metadata filters и visible qualification продолжают проверять lifecycle.

Путь передачи: MCP schema → context handler → unified service → project context
→ requirements → project docs query filters → final projection requirements.

## Проверки

Сохранённый расширенный лог `m2_typed_boundary_tests.log`: **579 passed**.
Проверены старые schema/examples, project services, query planning/projection,
windows/budgets, references, trust и patch controls.
После добавления integrated public handler → unified → project service trace:
focused набор **106 passed**.

AR/JA/ES requests проверены для трёх explicit lifecycle значений; контролируемый
backend spy получает соответствующие metadata filters. Explicit JA change не
даёт edit permission; explicit read override English action выбирает docs_context.
Raw question с Unicode/whitespace не переписывается в opt-in ingress.
Первый negative error assertion ожидал top-level reason_code и был исправлен
под существующий nested MCP error contract. Обновлён strict schema-property test
для согласованных новых полей; негативные guard assertions не удалены.

Backend spies не являются installed retrieval/model evaluation. Source safety
и metadata lifecycle не заменены языковым classifier или new score threshold.

## Оставшаяся M2 работа

Этот opt-in boundary **не закрывает весь M2**:

1. Legacy requests всё ещё используют NL inference — согласованная совместимость.
2. Query aliases/rewrites ещё могут создавать derived original coverage по
   старым word-based правилам. Их нужно мигрировать, не выдавая lookup за proof.
3. Natural-language admission grammar/ratio остаются до relevance migration.
4. Не измерены cross-language retrieval, installed public packet и host quality.

Новые typed-boundary изменения пока незакоммичены. M3 не начат.

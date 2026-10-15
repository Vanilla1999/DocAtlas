# PR #211: независимый review миграции guidance tests

Дата: 2026-10-08. Reviewer: `footprint_audit`; автор slice: `trust_contract`.

## Verdict

**APPROVED для данного test-only slice по результатам независимого статического
review.** Замечаний, требующих изменения миграции, не найдено. Это разрешение
включить проверенные изменения в общий кандидат; actual pytest, installed/client
acceptance и готовность PR к merge этим verdict не подтверждаются.

Проверены frozen версии:

| Файл | SHA-256 |
|---|---|
| `tests/docs/test_agent_question_planning_contract.py` | `ef6351f617ac87aebd3f809a7a4a8c53e02c6be9583efab3b835d21308e74c6e` |
| `tests/docs/test_agent_recovery_version_guidance.py` | `4930d6eb3ba8de1dfcb0093e4fd8779977d950b41745e796f8fc459882480fbb` |
| `v2plan/PR211_GUIDANCE_MIGRATION_REVIEW_RU.md` | `ffe00ab5e739f2df91c0648b0ee1a1f758b701bdc13f759bb465798eae7b6d6e` |

## Независимое основание текущего контракта

Сравнение выполнено с точным исходным SHA
`21fe472d983f394130849d6fd4e582043d58e9ba`, а не только с результатом новой
реализации. На этой базе machine policy уже требует максимум пять **явно
переданных** same-question lookups, неизменный исходный вопрос и отсутствие
inferred semantic equivalence. Gap continuation уже ограничен explicit lookup
либо issued bounded source read. Подготовка уже требует terminal success перед
повтором исходного вопроса, а current project version нельзя подменять старым
кэшем после lockfile changes.

Побайтово подтверждено отсутствие изменений относительно `21fe472d` в шести
производителях этих правил: `docmancer/mcp/agent_workflow_contract.py`,
`docmancer/templates/agent_contract.md`, `docmancer/templates/skill.md`,
`docmancer/templates/references/prepare.md`,
`docmancer/templates/references/troubleshooting.md` и корневом `SKILL.md`.
Исторические commits `307c480cd7ffe2fff5a264167dcb09a7974ffc20` и
`5feb94fd7cce23ae0c68ba4711a4b394817ff4f6` также соответствуют описанным в
[авторском rationale](PR211_GUIDANCE_MIGRATION_REVIEW_RU.md) этапам удаления
heuristics и переноса подробностей в optional references.

Поэтому старые ожидания `1–3`, `decomposition_triggers`, автоматического
cross-language example и inferred gap splitting действительно устарели до
этой миграции. Смена ожиданий обоснована существующим контрактом. Совместимость
с переносом advertised descriptions в описание самого tool проверяется через
shared helper; это не подмена input constraints проверкой текста.

## Что сохраняет и усиливает patch

- **Question/lookup:** один конкретный неизменный вопрос, отдельные calls для
  независимых вопросов, exact identifiers/versions/conditions/negation/comparison
  sides, запрет выдумывать переводы, rewrites, subquestions, expected answers и
  source names. Машинные no-authority и no-coverage-transfer guards остаются
  явными. Новый пример уже существует на базе и передаёт literal lookup;
  тест дополнительно проверяет его scope, project path и advertised schema.
- **Schema bounds:** omitted/null/empty, один и пять explicit lookups
  проверяются отдельно от prose. Сохранены uniqueness и границы строк 1–500;
  неверный тип, дубликаты, шестой элемент и пустой original question должны
  отвергаться настоящим `Draft202012Validator` при штатном запуске.
- **Continuation/source authority:** retained guards запрещают automatic
  subquestions, обязательное чтение из-за unverified flags, повтор source span,
  смену вопроса ради пополнения budget и edit grant. Optional troubleshooting
  guide проверяется по реальному packaged содержимому: только returned URI с
  host reader support, paths/hashes/spans не capabilities, consent/source/scope/
  freshness/budgets сохраняются, denial/expiry/change не разрешают иной или
  latest file. Short skill, ссылки, guide и quickstart проверяются раздельно.
- **Recovery/version:** прежние положительные installed и machine assertions
  сохранены. Добавлены проверки returned job polling, running/failed/cancelled
  как not-ready, запрета автоматического retry failure, terminal success,
  unchanged question, explicit exact/historical version и повторного query
  после lockfile changes. `hard_stop=false` не даёт разрешения на edit.
- **Негативные контроли:** исходный реальный contract/guide сначала проходит
  положительный assertion. Перед изменениями prose проверяется наличие
  заменяемого фрагмента или фактическое изменение extracted guidance. Затем
  повреждённый guard обязан вызвать `AssertionError`. Это исключает пустой
  negative control на неизменившемся тексте.

## Проверка и ограничения evidence

Независимо выполнены SHA-256 сверка frozen файлов, `ast.parse` двух modules,
сравнение AST roster с `21fe472d` и `git diff --check` для этих файлов: PASS.
Сохранены все восемь planning и три recovery test nodes, их имена, аргументы и
decorators; дополнительных parametrizations нет. Исторические имена с
`decomposition` оставлены ради diagnostic inventory и не возвращают удалённую
семантику.

Автор отдельно сообщает 9 положительных и 49 отрицательных проверок чистых
helpers через AST data adapter. Reviewer проверил устройство этих controls
по исходному коду; эти числа не являются результатом pytest и не складываются
с 11 test nodes. Repository imports, actual renderer, JSON Schema validator,
MCP/server и установленный client в данном review **NOT RUN**. Static чтение
packaged source не доказывает корректность доставки установленного артефакта.

Перед итоговым acceptance нужен обычный запуск обоих test modules с штатным
conftest в подготовленной offline CI-среде на общем конечном SHA, затем
required/downstream и installed/client gates из
[аудита acceptance](PR211_CI_BASELINE_AUDIT_RU.md). Production, advanced,
retrieval, frozen protocols/golds/ceilings и CI gates этим slice не изменяются.
Открытый catalog gate `7066 > 6144` остаётся отдельным FAIL; данный review не
повышает лимит и не закрывает этот блокер.

## Addendum: оставшийся scope assertion после `b68759e`

Независимо проверено дополнительное исправление от `root` в
`tests/docs/test_host_scope_planning_contract.py` относительно
`b68759e65f52317928ba22166248e679098024ae`. Проверенный SHA-256 файла:
`9475f3eb5cf1ae2110d233d609cac962f105abb385f2c03a238a6cb68278296b`.

**APPROVED:** изменение можно включить в один slice с двумя проверенными выше
guidance modules. Их SHA-256 повторно сверены и не изменились.

Diff содержит только `import re` и замену одного prose assertion в
`test_public_tool_and_agent_template_explain_scope_without_hidden_widening`:
непрерывная подстрока `never widen` заменена выражением
`\bnever (?:infer or )?widen scope from (?:question wording|prose)\b` с `re.I`.
Canonical guidance уже говорит `Never infer or widen scope from question
wording`. Новый assertion принимает эту формулировку и компактную равнозначную
формулировку, сохраняя отрицание, действие, объект `scope` и источник возможного
расширения. Проверки трёх значений scope, shared scope helper, чтение canonical
и rendered templates и machine policy не изменены.

Независимые stdlib-only controls извлекли само regex из AST изменённого теста.
Два положительных ввода — настоящий canonical source и literal advertised
compact description — приняты. Три изменения canonical source — удаление
`Never`, перестановка `scope` и `question wording`, удаление `widen` — отвергнуты.
Это PASS изолированной проверки выражения, не actual pytest или renderer.

AST parse, сравнение обоих node interfaces с `b68759e` и `git diff --check`
для файла: PASS. Имена, аргументы, decorators, fixtures и количество nodes
сохранены. Production и gates в этом addendum не менялись. Для совместного
slice остаётся необходимым штатный прогон всех трёх modules на общем SHA;
ограничения acceptance из основного review сохраняются.

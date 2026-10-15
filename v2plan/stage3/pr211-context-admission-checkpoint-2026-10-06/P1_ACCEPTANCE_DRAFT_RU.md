# P1 preparation: proposed RU/EN acceptance и decision ledger

2026-10-06. **DRAFT / NOT APPROVED / NOT FROZEN**.
Это подготовка материалов следующего этапа, не обход P0 gate.
P0 остаётся ACTIVE: [проверка перехода](P0_TO_P1_GATE_RU.md).
P2–P7 не начаты; product/tests/gold не изменены.

## Корпус до реализации replacement

[p1-ru-en-corpus-proposed.json](archives/p1-ru-en-corpus-proposed.json): 8 families ×
RU/EN question × RU/EN source × original-only/caller-lookups = **64 cases**.
Builder: [p1_fixture_draft.py](p1_fixture_draft.py).

- Development: command, condition, trust, name-only — 32 cases.
- Holdout-candidate: partial multi-count, comparison, wrong module, stale source — 32 cases.
- Имена/факты synthetic, не ответы о DocAtlas и не runtime lookup tables.
- Corpora не импортируются product code. Gold не заменяет существующие eval fixtures.
- Holdout создан до replacement, но **ещё не независимо проверен**. Не называть
  его blind/independent accepted holdout. Reviewer проверяет spans/семантику и отсутствие
  утечек между families до freeze; после freeze не редактировать после результатов.
- Current draft не покрывает все обязательные группы: Pebble, three trust controls,
  Pydantic, hostile document, exact version, projection budgets, offline и scope
  остаются existing обязательными controls плюс требуют RU/EN pairs на P1.
- Actual metadata для `other-module`/`stale-project`, exact visible spans и fact
  annotations должен определить runner/reviewer. Labels не authorizes источник сами.

### Observable behavior для утверждения

| Lane | Proposed acceptance |
|---|---|
| Positive command/condition/trust/comparison | Все заданные fact IDs подтверждены final visible source spans; условия/отрицания не обрезаны |
| Partial | Свой subject и две попытки видны; чужие девять не назначены своему subject; location явно unresolved |
| Name-only | Нет false topical coverage/answer authority; совпадение product name не удовлетворяет вопрос |
| Wrong module/stale | Forbidden source не попадает в final sources, независимо от релевантности body |
| Все retrieval-only synthetic cases | `answer_supported=false`, `edit_ready=false`; это не предложение выключить existing typed-proof capabilities |
| Original-only | Не требуется добавлять English lookups для засчитывания RU support |
| Caller lookups | Та же original question; lookup success не наследует original proof/coverage |

Каждая из 8 language/input lanes оценивается отдельно. 0 новых integrity violations,
0 потерянных назначенных обязательных witnesses; среднее не компенсирует потерю case.
Budgets и действующие frozen release thresholds не меняются.

## Decision ledger — ни одно исключение пока не принято

| ID | Предложение | Обязательная граница/тест | Owner status |
|---|---|---|---|
| TD01 | Сохранить exact schema enums/action mappings | Explicit input validation, не free-text tool/operation guessing | PENDING |
| TD02 | Сохранить identity→URL registries D32 | Exact normalized library; version/fetch/source binding; confidence не proof | PENDING |
| TD03 | Сохранить RU/EN общие числительные как bounded literal normalization либо заменить общим language parser | Не table topic→answer; связь number span с subject/facet, multi-count negatives | PENDING: выбрать границу |
| TD04 | Сохранить language syntax keywords D31 | Только code token extraction; не NL ranking/admission; unknown identifiers controls | PENDING |
| TD05 | Сохранить fences/path/JSON/number syntax, bounds, source checks | Bytes/ranges/hash/scope/freshness/budgets проверяются независимо | PENDING; guards не ослаблять |
| TD06 | Источник historical/source-class scope вместо NL triggers | Нужен approved explicit request contract до удаления D13/D14/D18 inference | PENDING |

## Test migration ledger: assertion inventory сначала, replacements после доставки

[p0-transition-manifest.json](archives/p0-transition-manifest.json) содержит **159
assertions** с test ID/line/expression из четырёх alias-specific файлов. Каждая запись
сейчас `NO CHANGE / approval pending`. Group proposals ниже не являются разрешением
массово удалить asserts; ledger при реализации дополняется отдельной строкой на assertion.

| Migration ID / scope | Old guarantee | Proposed replacement | Preconditions / approval |
|---|---|---|---|
| TM01 `test_direct_question_retrieval_intents.py` | Known intent/query/policy появляется и не смешивает темы | Видимые source facts в RU/EN, trust positive и command negative; unknown product names | Доставка доказана P2; каждый assertion mapped; PENDING |
| TM02 `test_context7_style_project_chat.py` | Query planning/coverage contracts | Original сохранён, explicit lookups optional, useful context и honest final attribution | Разделить implementation asserts и scope/budget/proof guards; PENDING |
| TM03 `test_retrieval_alias_subject_binding.py` | Alias не подтверждает чужой subject | Direct source-bound own/other subject checks без aliases | Negative control не ослаблять; PENDING |
| TM04 `test_query_planning_alias_regressions.py` | Exact terms, relation/policy planning и alias regressions | Literal/source scope integrity плюс dictionary-independent fact delivery | Посимвольный diff обязательный; PENDING |
| TM05 legacy derived coverage floor | Минимальное original-derived coverage по старому equivalence mechanism | Fact delivery + original/lookup attribution integrity, без fake derived coverage | Отдельное изменение metric contract; сохранить old report/floor до approval |
| TM06 Direct-15 README sidecar | Frozen source blob и witnesses | Только обоснованное обновление source hash после сравнения bytes/witnesses | Самостоятельное review; не обходить штатный gate |

Ни одна миграция не выполнена. Будущая строка:
`assertion ID | old guarantee | replacement test ID | baseline/candidate evidence |
negative control | owner approval | reviewer | SHA`.

## Условия freeze P1

1. P0 DONE подтверждён по исходному scope, не переименован в завершённый частичный audit.
2. Owner утверждает TD/TM решения, behavior и ограничения proof capability.
3. Reviewer проверяет весь proposed корпус, дополняет обязательные missing families,
   span annotations и independent holdout. Names/values не помещаются в runtime parser.
4. Final development/holdout bytes, corpus/model/environment/version manifest хешируются;
   latency/cost/storage ceilings определяются **до** P2 model choice/run.
5. Existing red gates имеют явные отдельные решения; current approvals относятся к SHA.

Пока status **P1 PREPARATION ONLY**, а не ACTIVE/DONE. До этих решений разрешены
audit и подготовка fixtures; replacement/backend/model download не начаты.

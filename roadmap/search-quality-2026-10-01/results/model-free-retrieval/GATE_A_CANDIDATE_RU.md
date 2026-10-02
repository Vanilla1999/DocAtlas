# Gate A: один проверяемый кандидат, не production acceptance

Статус: **BLOCKED; ограниченная попытка завершена на B1, 2026-10-02**. Не approved.
Шаг 05 имеет stub и behavioral Red, но Green запрещён до принятия Gate A.
Prototype: `../../gate_a_candidate.py`; tests:
`tests/docs/test_gate_a_contract_candidate.py`, `test_gate_a_remaining_contract.py`,
`test_gate_a_review_blockers.py`. Production его не импортирует.

## 1. Разделение обязанностей

### Ограниченный контракт, согласованный пользователем для этой попытки

2026-10-02: цель — exact current source window без потери обязательных
ограничений, не универсальный semantic discriminator. Порядок: source/project/
path/version/scope/freshness/security failure → rejected; bytes/digest/span/request
mismatch → rejected; обязательный subject/literal/condition не подтверждён →
rejected/unknown; structural dependency потеряна → unknown; пересчитанный existing
local fact witness → allowed для read; принятый local topic witness → allowed для
read; иначе unknown. Rejected/unknown не admitted.

Actual window, не больший search passage, является объектом решения. Typed/list/
precedence/original origin не даёт привилегий; incoming approval flags игнорируются.
Allowed не создаёт support/coverage/edit permission; known part не сертифицирует
private tail. Отрицательный ответ на открытый вопрос может быть полезным read
context при проверенных bindings/applicability, но похожие слова не являются
достаточным основанием. Existing positives/negatives и guards не отменены.

Это согласование требований попытки, **не approval реализации Gate A**.
Порядок попытки B1 → B2 → focused run → решение. При необходимости нового semantic
механизма, lexical exceptions или несогласованных ресурсов попытка останавливается;
production Green шага 05 запрещён. Полный parent допустим только после проверки
authorized extent, owner, budgets и сохранения обязательных positives.

Общий read-decision должен вычисляться заново из `(request, snapshot, exact window)`:

```text
source rejected                          → rejected
exact/subject/applicability not verified → rejected/unknown (не admitted)
structural dependencies missing          → unknown (не admitted)
byte-bound verified fact witness         → allowed для read
visible local topic witness             → allowed для read
otherwise                               → unknown (не admitted)
```

Это один decision owner, без origin/route/precedence/list overrides. Fact witness
— только existing independently revalidated typed local evidence, НЕ lexical
`qualified=True`, score, incoming flags или `ContextDisposition.supported`,
прочитанный без проверки. Достоверный факт достаточно relevant для read, но
read permission не переносится обратно в proof/answer/edit readiness.

**Fact-witness adapter реализован в research prototype и локально проверен.** Он нужен, чтобы
общий echo refusal не запрещал настоящий ответ, который повторяет слова вопроса
(например, short boolean fact). Existing proof grammar не расширяется.

Prototype пересчитывает existing relation/default witnesses по исходным независимым
частям вопроса, затем topic witness. Retrieval question неизменён. Known part не
сертифицирует private tail. Это не полная source/applicability API: source, subject,
conditions и evidence sets должны отдельно проверяться в шаге 05.

## 2. Общий topic witness

Проверять только actual visible window, не исходный search block вне окна:

1. Enumerate existing source atoms. Heading/link-only не supplies witness.
   Неподдержанные code/table/list-only формы → unknown, не semantic non-answer.
2. Prose Markdown soft wraps соединять пробелом в том же paragraph/atom.
   Paragraph/hard-break/code/owner boundaries не стирать. Это source formatting
   normalization, а не query rewrite или relation-specific `sentence_pattern`.
3. Применять **прежнее** substantive sentence locality requirement: три distinct
   original query terms и adjacent original-query pair в этой же sentence.
   Floor/pair не подбираются заново и не выключаются для relation.
4. Questions и content-term echoes не supplies topic witness: если все extracted
   sentence content terms принадлежат original question, новая topical assertion
   этим не установлена. Используется existing `documentation_query_terms`, без
   нового списка echo verbs, aliases, relation regex или score threshold.
5. При отсутствии witness → unknown/fail closed. Не утверждать, что неизвестный
   paraphrase не relevant. Даже `allowed` здесь означает **topic context**, не
   entailment, complete answer или semantic equivalence.

### Почему это стоит проверять

Native frozen MkDocs passage с rule — top-1, 1909 UTF-8 bytes, span `[3206, 5115)`
в `docs/user-guide/writing-your-docs.md`. Оно содержит prose topic и short rule.
После нормального joining soft lines topic sentence проходит прежний pair/floor;
rule можно сохранить в том же contiguous window без `wins→override` bridge.
Ни expected path, ни witness не участвуют в builder/query/predicate.

Изолированный rule всё ещё unknown. **Следовательно, selector обязан не вырезать
единственный topic witness ради compact rule и наследовать старое approval.**
Actual DTO fit/retention должны проверяться в шаге 06/07, не объявлены здесь PASS.

### Известные ограничения

- Это всё ещё conservative lexical topic recognition, а не универсальное
  понимание текста. Paraphrase без нужных anchors может остаться unknown.
- Content-term echo check может ошибочно отказаться от полезного declarative
  fact. Existing byte-bound fact witness — principled sufficient route, но его
  integration и negatives ещё требуют отдельных tests/review.
- Opposite relation может быть полезным **topic context**, но не получает support.
  Если продукт требует исключить его даже из read context, нужна явная policy;
  текущий prototype этого не доказывает.
- Existing applicability имеет limited typed grammar и precedence-specific branch;
  данный prototype не делает её универсальной и не разрешает unknown conditions.
- Scope/module/version/digest/risk guards обязательны перед topic stage и снова
  на final window; pure topic prototype их не заменяет.

## 3. Packing objective — без нового relevance scorer

Universe: один finite ordered BM25 candidate inventory, exact source windows,
прошедшие общий decision и structural checks. Admitted window может конкурировать
в непустом packet. Candidate rank зафиксирован, scores не складываются.

Feasibility:

- exact current bindings; нет holes/borrowed subject/condition;
- 800 **whole serialized DTO admission tokens**, ≤3 sources;
- Gate R candidate/bytes/windows/source caps;
- intact structural dependencies, никаких permissions из clipping/score;
- один и тот же window inventory и decision для prefit/final.

Из feasible packets максимизировать лексикографически:

1. Boolean vector представленных candidate IDs в native rank order.
   Широта retained ranked candidates важнее дополнительных bytes первого hit.
2. Vector длины union exact spans внутри каждого represented candidate в том
   же rank order. Overlap не даёт двойного кредита; source extent, не количество
   matching words и не число «доказанных facts».
3. Минус actual whole-DTO admission tokens.
4. При равенстве — stable `(source identity, candidate ID, start, end)` ascending.

`packing_objective` реализует первые три comparison компонента; research solver
реализует stable ties, ≤3 rows, per-source cap 2 и callback whole-DTO cost.
Source bindings и реальная сборка каждого DTO остаются обязанностями integration.
Candidate membership определяется по immutable retrieval inventory, не incoming
flags. Source coverage измерена в Unicode characters, не tokens/semantic facts.

**Objective не доказывает качество:** wide window может добавлять irrelevant
text, early distractor может занять slot, boolean-rank preference может вытеснить
later partial fact. Такие потери — rejection в paired evaluation, не повод для
case-specific utility tuning. Если цель не сохраняет known partial facts, контракт
пересматривается отдельно; нельзя назвать failed run улучшением.

4096 windows не означают разрешение на неограниченное enumeration всех packets.
Research solver ограничен 4096 visits и возвращает `work_limited` без packet при
exhaustion. Это предложенный, не approved work bound. Локальный review обнаружил
exhaustion уже при 30 alternatives; текущий solver не принят для production.

## 4. Что проверено

Prototype tests: **11 passed**; log
`/tmp/opencode/m2-model-free-execution-30056be8/gate-a-candidate-tests.log`.

- Все семь existing heading/scattered/reordered/question negatives не admitted.
- Precedence echo не admitted; known partial и Greek positive admitted как topic.
- Soft-wrap positive; paragraph/hard-break/fence controls не admitted.
- Hash-validated full frozen MkDocs corpus → native passage query → topic witness;
  gold используется только в assertion, isolated rule остаётся unknown.
- Objective: rank breadth > first-hit extent, extent > cost, exact overlap union.

Candidate tests + unchanged native read controls: **67 passed, 1 failed**,
`gate-a-candidate-controls.log`. Failure — прежний precedence draft baseline,
production policy не переключена и тест не ослаблен. Это не public acceptance
нового algorithm; assertions не утверждают delivery или answer support.

## 5. Условия принятия Gate A

1. Reviewer принимает смысл `topic context`, echo refusal и role существующего
   independently verified fact witness без общего semantic promise.
2. Проверены short factual answer/echo controls и fact-witness adapter без
   qualification-as-read-veto/approval и без shape-specific overrides.
3. Решены intact code/table/list read windows: existing structural/typed witnesses,
   unknown не превращается автоматически в read; не потерять existing positives.
4. Согласованы opposite-relation read semantics и bounded solver work behavior.
5. Реализация шага 05 начинается с behavioral Red на approved full contract;
   этот research prototype не выдаётся за Red→Green production implementation.

Gate A остаётся открытым до этих решений. Новых runtime моделей/dependencies,
index defaults, query rewrites, source/security ослаблений и benchmark arms нет.

## 6. Финальный локальный review 2026-10-02 — BLOCKED

Fact-answer/echo, condition mutations, intact list/table/code, partial facts
`httpx-07`/`pydantic-07`/`ruff-07`, bounded exhaustion и один actual DTO counter
проверены в `test_gate_a_remaining_contract.py`. Initial HTTPX retention Red
исправлен existing default witness по исходной независимой части вопроса, без
library exception, query rewrite или изменения proof grammar.
Эти проверки не доказывают native public delivery всех frozen cases.

Повторный focused run: **183 passed, 3 failed**. Два новых research blocker Reds
и прежний baseline precedence proposal failure; negatives не ослаблены, xfail/skip нет.
Лог: `/tmp/opencode/m2-model-free-execution-30056be8/gate-a-final-review.log`.

### B1 — intact atoms не гарантируют completeness restrictions

Исходный документ: prose intro `Configure storage retention behavior with this
command:`, полный fence `retention --current`, затем отдельный paragraph
`This command must only be run against the test instance.`
Полное окно allowed; окно только intro + intact fence также allowed, хотя restriction
удалена. Test: `test_code_window_cannot_drop_following_applicability_restriction`.
Это дефект research structural predicate, не доказанное нарушение действующего
public route. Проверка touched atoms и limitations самого clipped window не
обнаруживает dependency вне окна. Нельзя исправить case-specific `This command`
regex или молча захватывать полный parent за authorized extent/budget.

### B2 — work bound несовместим с exhaustive solver на допустимом inventory

15 candidates, по 2 alternatives = 30 windows: ниже caps 20 candidates / 4096
windows. Enumeration требует `1 + 30 + 435 + 4060 = 4526` visits, включая
infeasible packets. При 4096 visits solver возвращает пустой `work_limited`.
Каждый packet в arithmetic control стоит 100 units и помещается в 800.
Test: `test_legal_inventory_does_not_lose_all_feasible_context_to_solver_limit`.
Это контрпример для solver interface, не реальная whole-DTO/public benchmark
потеря. Но он исключает утверждение, что bounded solver сохраняет feasible context
во всём разрешённом inventory. Fail-closed безопасен, но не равен non-regression.

### Решения и следующий разрешённый этап

- Предложение opposite-relation semantics: положительный и отрицательный ответ
  на открытый вопрос могут быть relevant для read; matching words сами по себе
  недостаточны. Support конкретной claim и edit permission проверяются отдельно.
  Existing short boolean controls проверяют оба ответа. Это не universal entailment
  и не policy approval автора этого review.
- Требование structural closure сохраняется; текущее intact-atom приближение
  отклонено как достаточный validator (B1).
- Exhaustion остаётся explicit/no best-so-far; текущий enumeration solver
  отклонён как достаточная реализация retention (B2). Лимиты не увеличены.
- **Следующий этап — пересмотр Gate A candidate, не Green шага 05.** Нужен общий
  source-bound dependency contract, который проходит B1 без lexical rescue,
  и deterministic bounded selection, сохраняющий objective/DTO budget на B2.
  Если это требует смены policy/resource bounds, сначала отдельное согласование.
- После исправления повторить эту decision table и controls, затем review/signoff
  на isolated step 05. Полный paired/public regression и независимая held-out
  приёмка остаются шагами 08–09. Независимый reviewer здесь не привлекался.

Ограниченное обещание relevance не отменяет existing required positives/negatives.
Safe BM25-only admission не принято. Шаги 05 Green / 06–09 BLOCKED.

## 7. Результат одной ограниченной попытки — STOP на B1

Пользователь явно согласовал ограниченную цель и opposite-answer read semantics
из раздела 1, а также порядок B1 → B2 и остановку без lexical rescues/нового
semantic механизма/смены ресурсов. Это не разрешение ослаблять negatives или
активировать prototype. В этой попытке runtime/prototype/tests не менялись.

### Проверка переиспользования existing helpers

Исходный B1 snapshot разобран через `_atom_spans`, `source_graph`,
`build_dependency_sets` и `source_block_alternatives`:

- prose intro `[0,57)`, code `[57,88)`, restriction prose `[88,145)`;
- `source_graph.edges` пуст; code closure содержит только intact fence;
- alternatives содержат intro+code `[0,86)`, но не dependency block с restriction;
- existing graph сбрасывает previous на code, поддерживает heading/list/table/
  named-definition/anaphora/cause edges, но не внешнюю code restriction;
- validation graph closure не может проверить связь, отсутствующую в graph.

Артефакт: `/tmp/opencode/m2-model-free-execution-30056be8/gate-a-bounded-attempt-b1.json`.
Добавление одного соседнего paragraph сделало бы B1 Green, но сам Markdown paragraph
boundary не устанавливает, что все обязательные restrictions находятся именно
в этом paragraph. Такое adjacency правило не выдано за общий completeness contract.

### Проверка консервативного whole-owner варианта

B1 block плюс длинный ordinary background в том же owner: complete local example
стоит **339**, whole owner **4176 whole-DTO admission units** по действующему
`docs_context_budget_tokens`. Owner один, размер 15667 UTF-8 bytes. При authorized
extent `[0,145)` его конец 15667 также выходит за разрешённый extent.

Это cost diagnostic над DTO с substituted snippets, не snapshot-validated public
publication и не frozen regression. Он показывает, почему blanket full-owner
нельзя автоматически принять за решение в прежних bounds. Не утверждается, что
именно эти цифры доказывают потерю конкретного frozen positive. Общее сохранение
required positives для такого варианта не установлено.

### Итог и граница остановки

**Общий способ закрыть B1 существующими helpers в этой попытке не найден.**
Избирательное связывание внешней restriction требует ещё не определённого dependency
механизма; blanket owner не удовлетворяет extent/budget в общем случае. Не добавлены
новые phrase lists, regex, silent expansion или automatic admission.
Это ограниченный инженерный результат, не доказательство невозможности любого
model-free алгоритма. По согласованному stop-rule попытка закончена на B1.
B2 не исправлялся; его Red повторён только как контроль текущего состояния.

Повторный focused run: **183 passed, 3 failed** (`gate-a-bounded-attempt-controls.log`):
B1, B2, прежний baseline precedence proposal failure. Отдельный step05 stub run:
**12 passed, 6 failed** (`gate-a-bounded-attempt-step05-red.log`). Negative passes
stub не подтверждают guards. Xfail/skip/expectation changes нет.

**Решение: не принимать Gate A, не продолжать шаги 05–09 этого дизайна.**
Действующий public route и изолированные результаты 01–04 сохраняются. Нет
автоматически назначенного нового цикла исследований. Возобновление возможно только
по отдельному запросу с новым согласованным dependency/product/resource contract;
это не часть завершённой попытки и не обещание успеха. M2 не завершён.

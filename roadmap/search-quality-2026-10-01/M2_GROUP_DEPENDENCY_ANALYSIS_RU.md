# M2: групповой анализ зависимости от legacy qualification

## Scope

По запросу пользователя — сначала анализ общей причины, без production fixes,
изменения вопросов, добавления lookups в regression requests или ослабления tests.
Ниже разделены подтверждённый общий дефект, другая группа потерь и статические
подозрения. Это не классификация всех 108 failures и не gate закрытия M2.

## Подтверждённая общая зависимость

Explicit planner удалил generated needs/hints/parts/canonical rewrites, но
downstream по-прежнему использует наличие qualified query как обязательное
условие сохранения read-only candidate. Число query IDs снизилось, а контракт
приёмки candidates остался прежним.

Цепочка:

```text
raw original question / explicit lookups / literals
  -> retrieval + bounded quota
  -> native tagging: source/reference checks + legacy lexical/typed qualification
  -> current catalog/snapshot rebinding
  -> rerank: нет qualified query ID => удалить candidate
  -> context_pack
  -> projector: нет visible qualification => удалить candidate
  -> contextual fallback, но только на surviving candidates
```

Ключевой барьер — `project_doc_ranking.py:680–686`: когда присутствует
`retrieval_query_matches`, пустой набор qualified IDs ведёт к `continue`.
Причина отказа не различается: source guard и недостаточная lexical matching
доля попадают под один барьер. Условие нельзя просто убрать: оно защищает также
настоящие отрицательные source/reference decisions.

`_project_context_service_part01.py:114–136` вычисляет исключение
`context_candidate_ids` только через `set_context_variants`. Это обход для
распознанного структурного list/set context, не общий путь для unresolved
read-only requests. Scalar/unknown кандидаты не получают такой же переход.

`_docs_context_projection_core.py:238–253` повторяет semantic/lexical qualification
на visible bytes и требует visible qualified IDs либо component witnesses.
`project_need_context_fallback` вызывается позже (`:665–673`) на
`initially_ranked`, собранных из уже переданного `context_pack`. Удалённые
prefit candidates туда не возвращаются.

Существующий `classify_need_context` уже различает blocked/retrieval_only/supported,
но живёт после prefit. Кроме того, он зависит от compile_need_contracts,
admission_grammar, conditions parser и двух body terms. Это не готовый
language-independent classifier для всех candidates.

## Native подтверждение группы

`m2_group_dependency_analysis.json`: wrappers только записывают inputs/outputs
native quota, qualify и rerank; решения и requests не заменяются. Witness labels
используются только после retrieval для диагностики, не передаются runtime.
Corpus hashes записаны в artifact. Все exposed cases — диагностика, не holdout.

| Контроль | Required text после retrieval quota | Перед rerank | После rerank | Context pack |
|---|---|---:|---:|---:|
| pydantic-07 | Есть | 6 | 0 | 0 |
| ruff-07 | Есть | 6 | 0 | 0 |
| mkdocs-05 | Уже нет | 3 | 0 | 0 |
| httpx-07, текущий исправленный | Есть | 7 | 7 | 7 |

В pydantic/ruff qualified IDs всех шести candidates пусты; context_candidate_ids
также пусты. Required chunks отвергаются как insufficient_visible_match, без
missing exact constraints:

- pydantic: body matches 7/16, ratio 0.4375;
- ruff: body matches 5/14, ratio 0.3571.

Неизвестная private-deployment часть увеличивает знаменатель whole-question
matching, но ничего не добавляет в документированный body. То, что источник
не отвечает на весь вопрос, превращается в потерю уже найденного read context.
Need fallback в этих двух calls не рассматривает ни одного candidate.

HTTPX сейчас проходит через literal HTTPX anchor, при этом original qualification
на required body всё ещё false (4/14). Это наглядная асимметрия: наличие literal
locator даёт read-only passage путь до projection, а аналогичный plain-language
topic без locator теряется. Anchor не является доказательством полного ответа.
Во всех четырёх calls answer_supported=False и edit_ready=False.

## Независимый от exposed вопросов контрпример

`m2_group_synthetic_controls.json`: один неизменный current source и query
с тремя совпадающими topic terms. Выполнены EN и Greek-literal варианты.
В каждом baseline доставляет один source, а добавление неизвестного private
tail к original question приводит к context_pack=0 и visible_sources=0.
Generated probes/host lookups отсутствуют во всех четырёх requests; source body
не менялся. Support/edit flags остаются false.

Это проверка monotonicity частичного context delivery на matching-language
tokens, не перевод, semantic entailment или multilingual quality измерение.

## Другая группа: потеря до qualification

В mkdocs-05 witness есть до retrieval diversity cap, но отсутствует после cap.
Потом три остальных candidates отсекаются тем же prefit gate. Исправление
prefit/disposition может вернуть другие context passages, но не гарантирует
доставку отсутствующего required witness. Поэтому нельзя объяснять все failures
одним ratio и объявлять одно снятие veto сквозным решением.

Нужны отдельно: bounded discovery/relevance pool и admission его visible spans.
Увеличивать лимиты/менять labels или guesses ради одного case не предлагается.

## Оставшиеся статические callers

Следующие находки требуют отдельного runtime/inventory review, а не немедленного
удаления:

- `_project_context_service_part01.py:417–470`: missing proof requirements могут
  породить `requirement_probe_query` и document-local search вне explicit planner.
  Это ещё один parser-owned retrieval caller; source/hash/scope/permission guards
  внутри него должны сохраниться. Его достижимость для этих calls не доказана.
- `_project_context_service_shared.py:169`: `project_context_pack` получает
  lifecycle через raw-question inference, хотя service выше выставляет canonical
  typed lifecycle. Это возможный отдельный boundary inconsistency; runtime
  mismatch в этом анализе не проверен.
- `need_contracts.py:43–78`, `admission_contract.py:60–80` и
  `need_context_disposition.py:50–76`: grammar остаётся источником typed demands,
  interpretations и applicability veto даже при explicit public planner.

## Общее исправление: рекомендуемая граница

Не чинить вопросы и не возвращать generated rows. Ввести один общий контракт
read-context disposition ДО prefit, используемый затем projector:

1. **Source/reference eligibility:** current identity/version/scope/snapshot,
   actual-byte binding, trust/security и explicit constraints. Жёсткий отказ
   нельзя обходить через context fallback или score.
2. **Retrieval/context candidacy:** candidate найден bounded retrieval для
   actual request; может конкурировать за прежние budgets, не требуя parsed
   semantic witness. Relevance остаётся отдельной проверяемой задачей: одних
   metadata или наличия одного identifier недостаточно.
3. **Semantic support:** отдельно unknown/partial/proven по текущим witnesses.
   Unknown не создаёт covered_query_ids, requirement assignments,
   answer_supported или permission, но сам по себе не означает unsafe source.

Ранний ранкер должен ограничивать/упорядочивать context candidates, а не
отождествлять пустой proof/qualification набор с source запретом. Projector
заново проверяет eligibility и binding на clipped visible bytes; proof claims
также пересчитываются, но не служат universal veto read-only доставки.

Для реализации потребуется разобрать смешанные rejection reasons по владельцу:
нельзя whitelist всех insufficient/unknown reasons, присвоить всем candidates
`context_candidate_ids`, разрешить все current sources, снизить ratio или
считать два совпавших слова универсальным semantic/relevance threshold.
Typed constraints и отрицательные guard tests должны мигрировать вместе с
callers, а не удаляться как legacy по module name.

## Gate общего решения

- Неизвестная добавка не обнуляет уже допустимый документированный контекст
  при сохранённых source/request constraints и доступном budget.
- Изменённая identity/version/snapshot, stale/history, unsafe bytes и нарушение
  explicit constraints продолжают давать hard rejection.
- Heading-only, question echo и unrelated exact-ID distractors не становятся
  поддержанным ответом или автоматически релевантным context.
- Clipping требует нового byte binding и не переносит старый witness/coverage.
- Весь DTO остаётся в прежнем token/source budget; no support/edit escalation.
- Результаты discovery до/после cap оцениваются отдельно от disposition.

Вывод: общая зависимость подтверждена для plain-language partial-read группы.
Prefit/disposition контракт — следующий участок исправления, не список вопросов.
Есть отдельная discovery-loss группа; все 108 failures этим анализом не закрыты.
Production в этом шаге не менялся; M2 остаётся открытым.

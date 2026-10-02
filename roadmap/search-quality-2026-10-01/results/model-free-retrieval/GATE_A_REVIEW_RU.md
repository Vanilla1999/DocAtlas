# Gate A — read decision: requirements и нерешённый discriminator

Статус: **BLOCKED для реализации шага 05**, не approved policy.
Обновление 2026-10-02: research candidate локально проверен; финальный review
нашёл B1 (restriction вне code atom) и B2 (exhaustion на 30 alternatives).
Актуальные counterexamples и решение: [Gate A candidate, раздел 6](GATE_A_CANDIDATE_RU.md#6-финальный-локальный-review-2026-10-02--blocked).
Шаг 05 содержит только stub/Red, не approved Green.
Ограниченная попытка после явного согласования пользователя завершена на B1:
existing graph не содержит code→external restriction dependency, blanket owner
не является допустимым общим решением по extent/budget. Итог — STOP, не новый
автоматический research цикл; [результат в разделе 7](GATE_A_CANDIDATE_RU.md#7-результат-одной-ограниченной-попытки--stop-на-b1).
Source eligibility и native passage retrieval уже реализованы отдельно.
Эта проверка не добавляет lexical rules и не меняет existing negative tests.

## Диагностика действующего predicate

Артефакт: `/tmp/opencode/m2-model-free-execution-30056be8/gate-a-locality-diagnostic.json`.
Исходный вопрос и MkDocs witness загружены из hash-validated frozen protocol;
gold использован только для диагностического примера, не retrieval input.
Вызван существующий `local_topic_witness` над literal bytes; это **не** native
public admission, не benchmark и не source/proof validation.

| Окно | Existing adjacent-pair predicate | Тот же predicate без pair | Требуемый public read результат |
|---|---|---|---|
| Frozen MkDocs override rule | false | true | Полезное rule должно доставляться |
| `page title wins when navigation configuration and Markdown content define different titles.` | true | true | Existing negative: no preferred proposal; public rejection нужно проверять отдельно |
| `storage behavior retention is documented.` | false | true | Existing public negative: empty sources |
| `storage retention behavior is documented in this current guide.` | true | true | Known partial context сохраняется, private tail unresolved |

Вывод: удаление pair не является готовым Gate A. Сам pair тоже не решает
precedence echo. Это конкретные ограничения текущего алгоритма, **не** доказательство
математической невозможности любого model-free discriminator.

Второй важный факт: `_applicable_context` в `need_context_disposition.py:70–76`
имеет precedence-specific `define different` ветку. Ее нельзя без review назвать
универсальным condition checker. Удалять condition guard или расширять его
разрешённые формы ради Green запрещено; unknown condition остаётся закрытым.

## Единая decision table — обязанности будущей API

API возвращает `allowed / rejected / unknown`, reason и exact source span,
но не support/coverage/qualified IDs. Input: original request, current verified
snapshot, exact proposed visible window. Route/typed/precedence/list provenance
не является аргументом relevance approval.

| Ситуация | Обязательный результат | Владелец |
|---|---|---|
| Wrong project/path/version/module/snapshot, stale/dirty/lifecycle/risk | rejected | Source eligibility + request preflight |
| Digest/span/request mismatch после prefit | rejected, даже при cached approval | Final recheck |
| Явный literal/subject отсутствует в допустимом visible owner/window | rejected | Existing exact/subject binding; не read score |
| Missing/uninterpretable requested condition, потерянная negation/exception | rejected/unknown, без public admission | Applicability / structural closure |
| Heading/link-only без substantive source content | rejected | Existing substantive-content check |
| Question echo, scattered terms | rejected | **Общий read discriminator пока не определён** |
| Faithful paraphrase в correct owner/condition | allowed для read, не proof | **Общий read discriminator пока не определён** |
| Known partial fact + unknown private tail | allowed только для known part; tail unresolved | **Discriminator + unchanged completeness/permission policy** |
| Opposite relation, совпадающие слова | Не считать support; полезность для read требует отдельного решения | **Unresolved read semantics** |
| Whole search block relevant, clipped window теряет нужный witness | reject/unknown window; не наследовать search approval | Window decision, не BM25 |
| Недостаточно данных для read relevance | unknown → не admitted | Fail closed |

Не смешивать hard-rejected и relevance-unknown в trace. Prefit/final используют
ту же функцию над теми же bytes; ни наличие другой source в packet, ни route
не меняют решение. Final заново проверяет actual window и binding.

## Предлагаемый search-span → window interface

1. Search hit несёт generation/profile/source identity, exact char/byte/line
   spans и native rank/cost. Cost не serialized proof и не semantic probability.
2. Request-local inventory связывает source document один раз с request/version/
   scope и разрешённым extent. Конкретный window — contiguous exact source slice.
3. Окно не может выходить за authorized extent или брать subject из sibling owner.
   Introduced list/table header-row/code restriction — structural dependencies,
   но их наличие само по себе не доказывает ответ.
4. Source-window eligibility, hard applicability и relevance decision считаются
   раздельно. Окно, прошедшее первые два, ещё не получает `allowed` автоматически.
5. Candidate/window caps и bytes учитываются даже для rejected alternatives;
   hidden source reads и resource registration в enumeration запрещены.
6. Proof/answer/edit readiness сохраняют свои existing checks. Unknown proof
   не мешает действительно полезному read context, но полезность сначала должна
   быть определена общим discriminator.

## Packing: предложение для отдельного review, не принятое правило

Не вводить новый lexical utility scorer. Сохранять один native candidate rank;
не складывать BM25 costs разных queries. Среди finite source-bound alternatives
рассматривать только approved windows со структурными dependencies intact.

Можно определить deterministic constrained selection, предпочитающий сохранение
наиболее ранних admitted candidates, затем intact structural windows, с whole-DTO
cost accounting и stable span ties. **Пока не согласовано**, что считать лучшим
из нескольких допустимых окон одного candidate, и как сохранить partial facts
при lexicographic packing без новый budget loss. Greedy first-fit не объявляется
оптимальным или non-regressive по одному MkDocs результату.

## Что нужно решить для продолжения

Существующие source/identity/condition/security negatives сохраняются безусловно.
Также сохраняются перечисленные relevance negatives до явного отдельного review.
Следующая задача — разработка и независимый review **одного** общего discriminator
и packing objective на positive/negative decision table, без новых словарей,
relation-specific locality switches, aliases, model/runtime dependencies и
threshold tuning. Наличие таблицы не является реализацией этого discriminator.

Если предлагается изменить продуктовый смысл read context на «safe retrieved
source, не гарантированно relevant/answering», это альтернативный контракт,
требующий явного пересмотра relevance negatives. Он **не принят** и не может
внедряться под названием non-regression текущего плана.

Шаг 05 не должен начинаться с permissive stub, который автоматически допускает
BM25 hits: это незаметно отменило бы нерешённый gate. Ни runtime, ни gold/tests,
ни budgets в этой Gate A проверке не изменены.

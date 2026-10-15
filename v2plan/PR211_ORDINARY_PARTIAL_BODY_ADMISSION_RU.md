# PR211: ordinary partial body context v1

## Статус и граница

Подготовлен узкий production/proof slice от PR HEAD `d76f6ab85e12f482ad6bec1d43040899f4b0a532`,
tree `63bff21aadbfb131082db075ed95ea7e89310e44` (126).
Собственный runtime этого slice ещё **PENDING**. Нужны здоровые 12 recovery cases,
39 intended kills и совместный CI на опубликованном SHA. Этот документ не
объявляет P14, V2, installed/MCP transport или PR merge-ready.

Причина: две неизменные original-only P14 формулировки уже получают правильные
current body windows, но остаются `qualified=False`,
`insufficient_visible_match`, `exact_terms=[]`. Root независимо прочитал
фактический P14 job `114127987380` на 126: 12/14 total, 8/10 required discovery,
5/5 complete frozen facts, 0 errors; первые failures — `alias_order_drafts` и
`alias_project_retry_rule`. Ни корпус, ни gold, ни показатели этого gate
не меняются. Новая ветка доставляет полезный частичный контекст с честно
отсутствующим original coverage.

Это явное дополнение принятого [ADR0003](https://github.com/Vanilla1999/DocAtlas/blob/d76f6ab85e12f482ad6bec1d43040899f4b0a532/docs/adr/0003-context-first-project-reads.md).
Не возвращаются autoaliases, inferred roles, semantic answer certification,
output ceilings, morphology, embeddings или дополнительные providers.

## Точный допуск

Для обычного original project read выбирается один непрерывный raw span вопроса
с минимум двумя различными content words. Все content words между его концами
должны встретиться в том же порядке в **одном** substantive prose clause
источника. Дополнительные слова источника допустимы. Пропуск content word
вопроса, склейка предложений/координирующих clauses и совпадение только префикса
не допустимы. Повторение голой пары слов не даёт substantive content.

Общий английский function-word set перечисляет вопросные слова, auxiliaries,
determiners, личные местоимения и основные connectors/prepositions.
`before`, `after`, `until`, `unless`, `without`, `not`, `never`, `only`
остаются значимыми. Это фиксированный общий фильтр, не список P14-тем.
Точные слова сравниваются casefold без stemming или замены исходного запроса.

Ordinary fallback отклоняет technical/literal/quoted/path mentions,
числа, операторы и неподдерживаемую syntax; existing strict/qualified lanes
сохраняются. `pressure 7 packets` и `pressure != packets` нельзя превратить
в пару `pressure packets` удалением нераспознанного символа.
Обычный составной `project-wide` допустим; отдельный `-` — нет.
Проверка source prose использует существующие Markdown units: heading, link,
table/list, code fence и повторённый label не могут дать этот prose witness.
Whitespace, inline emphasis и исходные координаты сохраняются.

Это **partial lexical context**, а не доказательство всех обычных модификаторов
или субъектно-предикатной связи полного вопроса. В частности, ordinary question
с неизвестным `lunar` может получить фактический network paragraph, сохранив
`query-original` в missing. Existing literal/lunar и unrelated-empty guards
сохраняются. Новая отрицательная пара с разными субъектами проверяет именно
запрет склейки двух clauses, не все возможные отношения естественного языка.

## Откуда берётся receipt

Путь: `handle_context_tool` → существующий native retrieval → свежий
`SourceReferenceContext.prepare` → `reference_query_tagging` →
existing qualification/admission/packing/ranking → финальный projector.

Receipt создаётся только для фактически выполненного original/direct запроса
с точным raw question. Native context должен быть complete и содержать
независимые current source/member/file-hash записи, которым равна подготовленная
кандидатная metadata. У существующего
[SourceReferenceContext](https://github.com/Vanilla1999/DocAtlas/blob/d76f6ab85e12f482ad6bec1d43040899f4b0a532/docmancer/docs/application/source_reference_evidence.py)
lightweight/incomplete preparation сохраняет входную metadata; она не может
выпустить новый ordinary receipt.

Ключ связывает raw original, исходный host project path, independently derived
local owner, finite catalog member, generation, source identity/path,
source/file hashes, полный span и SHA-256 возвращённого body window.
Expected owner вычисляется из absolute host request root по уже действующей
чистой формуле
[local_project_identity](https://github.com/Vanilla1999/DocAtlas/blob/d76f6ab85e12f482ad6bec1d43040899f4b0a532/docmancer/docs/application/project_docs_member_transaction.py):
`local:` + SHA-256 UTF-8 `str(Path(root))`; проверка не требует нового
resolve/stat/read. Source scope обязан совпасть с этим owner при записи и
потреблении. Неоднозначный symlink/noncanonical alias не открывает новую ветку.

Scope живёт на протяжении синхронного MCP handler, включая final projection.
Async entry уже ожидает этот handler через `asyncio.to_thread`.
Вложенный handler получает fresh state; finally очищает receipt и закрывает
state, в том числе для скопированного Context. Lookup-only source, serialised
metadata booleans и saved-result replay не являются original discovery.

Private ContextVar — защита нормального consumer от replay/substitution,
не capability против произвольного Python-кода в процессе.
В production нет дополнительных retrieval/source reads, network calls,
schema writes или новых публичных полей/grant booleans. Scope первоначально
ограничен обычным project read без module/library/maintenance/patch_context.

Existing qualification, identity/freshness/index/lifecycle/forbidden constraints
проверяются до fallback. Whole acquired body и immutable provenance доходят
вместе. `qualified=False`, original missing и answer/edit authority false
сохраняются; admission не выдаётся за source fact entailment.

## Frozen P14 и независимый oracle

Исходный protocol:
`eval/agent_developer_v1/paraphrase_protocol.json`,
blob `43cd3b77175205d72092ab768907b6f82259a0a6`,
SHA-256 `35fa2151f2c390a25bab301897873d5eb1bc1af9275eee55afe78b8af5afed5b`.
Никаких его edits.

| Case | Полный исходный вопрос | Source path | Raw query witness → raw source witness |
| --- | --- | --- | --- |
| alias_order_drafts | How are order drafts stored before upload? | packages/orders/README.md | before upload → before upload |
| alias_project_retry_rule | What is the project-wide rule for network retries? | ARCHITECTURE.md | network retries → network submission retries |

Question SHA-256: `10d7f1fd367cbf40ca69fa23ca001b2990f8b64675dbf10963a7946dc10914bc`
и `ee9029ac0791d0740d9cfa47a52c2f3144634b0a6cebaa22dfa31813c3dc8b02`.
Full source SHA-256: `6f13aec3ccc8d596f1552421aa7f4e0f2f2738b6e9654eeab1621e4a07f704a1`
и `5a6583754d6ed2f7c294a4334f47ecacdb7087abe1116ec20d97d6373dbef32a`.

Control хранит полные факты и сверяет их с frozen protocol; expected snippets,
path, owner, generation, raw token/window spans и полные body bytes задаются
независимо. Он наблюдает реальные native dispatcher/prepare, public handler,
projector и validator snapshot. В source text ничего не сокращается до пары
слов. Independent prose добавляет `pressure telemetry packets`, Unicode,
inline emphasis и перенос строки; source insertion и raw offsets проверяются
без production-matcher-generated expected values.

Native fixture явно подготавливает конечный catalog/member roster и настоящий
read-only SQLite service. Индексирование выполняется только при разрешённой
fixture preparation. Read checks сравнивают generation и полные байты private
store/project до и после. Это in-process production MCP entry; stdio/wheel/client
acceptance остаётся отдельным требованием.

## Реальная работа, не только внешний case count

Новых ordinary pytest-функций нет; прежние 12 recovery case names неизменны.
Это не означает «одна дешёвая проверка»: новый helper выполняет самостоятельную
native и counterfactual работу в конце `closed_literal_context`.

План полного здорового исполнения (ещё не runtime receipt):

| Работа | Число | Что учитывается |
| --- | ---: | --- |
| Native public reads | 28 | 27 через existing capture/public dispatcher и один actual native service через foreign-root handler delegate |
| Полные положительные public reads внутри этих 28 | 7 | P14 ×2, нейтральный prose, форматирование, baseline после operand faults, outer scope restore, ordinary unmatched modifier |
| Relevance negatives внутри этих 28 | 16 | 10 source forms и 6 исходных query forms |
| Остальные native reads внутри этих 28 | 5 | receipt withheld, foreign request root, incomplete owning context, exception cleanup, lookup-only |
| Same-call source operand replays | 8 | owner, generation, member, scope, document identity, full body, window, stale/index; один actual read, восемь независимых deep copies/projector calls |
| Saved-result handler replays | 2 | fresh public call и вложенный call; оба без нового native retrieval |
| Closed/copied-context projector replays | 2 | normal return и exception; оба обязаны быть пустыми |
| Explicit fixture preparations | 16 | замены конечного исходного документа перед соответствующим native read |

Количество каждого фактического `RetrievalDispatcher.run` возвращается из
наблюдателя в `native_query_dispatches`; заранее заданного предполагаемого
числа нет. Observer вызывает исходный bound method один раз и возвращает тот же
result. `work_counts` отдельно считает native reads, query dispatches,
source operand replays, handler replays, copied contexts и fixture preparations.
Negative labels не выдаются за дополнительный public read.

Восемь source faults используют один свежий valid native вызов, а не восемь
повторных поисков. После faults исходный operand даёт здоровый public context.
Новый helper не дублирует уже существующие missing-path/Martian gates.
Вместо избыточных `+`/`!=` оставлен конкретный найденный `!=` gap,
цифра и standalone minus. CamelCase/quoted negatives сохраняют strict-lane
veto; numeric/!=/standalone-minus проверяют новую ordinary surface boundary.

Обычные positive calls требуют ровно один captured projection attempt.
Nested control отдельно требует ровно два: nested empty payload/snapshot,
затем healthy outer snapshot. Это учитывает реальный observer, не ослабляя
single-projection assertion остальных вызовов.

## Directed mutation proof

Existing 33 mutation blocks и общий harness сохранены побайтно.
Новый helper вызывается **после** существующих closed-literal/filename/FTS
controls; прежний intended guard достигается до нового helper. До выдачи credit
общий harness требует здоровый normal baseline, точный импорт/хеш source,
один source anchor, ожидаемый case/guard и отсутствие errors.
Новый import/helper hash внесён одновременно в TARGET_MODULES и MODULE_PATHS:
17 записей в одинаковом порядке. Critical runner этим slice не меняется.

| Новый mutant | Причинный ожидаемый первый guard |
| --- | --- |
| ordinary-partial-context-disabled | `recovery_ordinary_full_source_fact` |
| ordinary-native-receipt-not-required | `recovery_ordinary_native_receipt_required` |
| ordinary-request-owner-not-bound | `recovery_ordinary_request_owner_binding` |
| ordinary-independent-clauses-joined | `recovery_ordinary_body_clause_safety` |
| ordinary-query-content-word-skipped | `recovery_ordinary_original_span_boundary` |
| ordinary-literal-surface-discarded | `recovery_ordinary_original_span_boundary` |

Первые контрпримеры: отключённый P14 positive; приобретённый native body без
записанного receipt; реальный native project B внутри запроса host A; две
source clauses; пропущенное content word `lunar`; исчезнувшая цифра `7`.
Нормальный healthy путь идёт раньше каждой соответствующей подмены.
Новый целевой результат: **12 normal cases / 39 intended kills**, пока PENDING.
Ни failure другого guard, ни import/fixture error не засчитывается.

Каждый новый anchor статически встречается ровно один раз:

- `ordinary-partial-context-disabled`: before `d15e01ed738c7aa5ae604f2b3bf4da8f59aa94357a6f72804dcc01e471bdbc71`; after `f97b41c21274dc381614af9abe401e6705d3676c931a38cdfecf325e4665b50e`.
- `ordinary-native-receipt-not-required`: before `a28c337045757c49ebf79d44efc5e5eab5c498202f30a947d5152d8b7b81e3b7`; after `1bc4aee40f18f23f1a079e488bdc894ee718dcde69e3da59f11402a97ec13c6d`.
- `ordinary-request-owner-not-bound`: before `a28c337045757c49ebf79d44efc5e5eab5c498202f30a947d5152d8b7b81e3b7`; after `5d88cc4a4717f6f7c39f604d8d8cd781face7223bafa83575260902f0dabeba1`.
- `ordinary-independent-clauses-joined`: before `d15e01ed738c7aa5ae604f2b3bf4da8f59aa94357a6f72804dcc01e471bdbc71`; after `507c928be5c5d62a25c3318dde60759d6e3c402d5bc244c9b73f542449ab02b1`.
- `ordinary-query-content-word-skipped`: before `d15e01ed738c7aa5ae604f2b3bf4da8f59aa94357a6f72804dcc01e471bdbc71`; after `584b71b9a110d5014974f7dbbc146efa5b62a189c2c834e2a961294d4e30a159`.
- `ordinary-literal-surface-discarded`: before `d15e01ed738c7aa5ae604f2b3bf4da8f59aa94357a6f72804dcc01e471bdbc71`; after `047e9c1a5193fe5a638a93a6f58c5271e4118ffd5c0e1a502cbf6bbf2bee6a8c`.

## Exact manifest и обратимость

Все строки ниже — Git blob SHA; сохранены текущие modes.
Два script modes независимо прочитаны из exact126 Git tree.
Новые файлы не имели base.

| Path | Mode | Base | Proposed |
| --- | --- | --- | --- |
| docmancer/docs/domain/original_body_discovery.py | 100644 | NEW | fb239b5607b283094d93d6392894b3c0db9459cb |
| docmancer/docs/domain/ordinary_body_context.py | 100644 | NEW | 46e43fba32a4a30784b5b658b0e5717297d78516 |
| docmancer/docs/application/reference_query_tagging.py | 100644 | 8418abf11043614094a8421b1d0ec242ba12d42c | 10f71d2412b599787a8ac60f2b1c5b69e82e6fee |
| docmancer/docs/application/_project_docs_service_part03.py | 100644 | 94fe9ee6629d14034d337fae879272c5b6d16a64 | 7b17f564732ab7c5f712e4091bf0dfe3e4a7d617 |
| docmancer/docs/domain/literal_context_admission.py | 100644 | 7e84697c04beb394ec561252d36bd78f3695fc3d | b94d1508133c51c3a622275f7cbb2a2c802ce1c2 |
| docmancer/docs/interfaces/mcp/context_tools.py | 100644 | c6e2bda4208a43b7764fe484928fd7ce55ed6183 | 28fd767567e5c32124d84496a5937a87ee62164c |
| docmancer/docs/application/_docs_context_projection_core.py | 100644 | 15cc1f04b03fd3d0ccf83099f1f4ee09b87844c2 | ec87e90b8ef40faab65e514a3e417ee9d6bf0b0c |
| eval/agent_developer_v1/ordinary_body_controls.py | 100644 | NEW | dcf2b57fc55b4b43cfb8d870747799315ba8a713 |
| scripts/run_recovery_contract_gate.py | 100755 | a3e4d05172bb2e124632ad535056a3a02b90df8b | 8bab7b6c6c33d08e536e7962b08ff476d31e1353 |
| scripts/run_recovery_mutation_gate.py | 100755 | 4644eb82522eadeea7807fd067759cfce76a7e11 | ae400a4c8bb442128f28d92e40cc849b7ea1f997 |
| docs/adr/0003-context-first-project-reads.md | 100644 | 9ec7ca998294b171ea3e0e52972ffbdd673116dc | f06b5e797c122c4f24178e02ebb4dafe0520492c |

Пять существующих production edits ограничены import/scope/fresh-context
передачей, fallback и двумя diagnostic reason fields. Их inverse проверен
independent peer; old qualifier/strict path не переписан. Payload anchor
`payload = _payload(sources, decision=decision, query_plan=query_plan)`
сохранён. ADR inverse — удаление единственного нового раздела.

Recovery gate inverse: удалить import/call/result ordinary и четыре новых
TARGET_MODULES, развернуть четыре склеенные пары module-name строк.
Все прежние function bodies до нового terminal call, CASES, main и ошибки
остаются побайтно прежними. Gate сохраняет размер менее 1000 строк.
Mutation runner inverse: удалить четыре MODULE_PATHS и шесть последних
Mutant blocks; восстанавливается полный base побайтно.
Old CASES block SHA-256 `4a8474c8baf558e0c56117b34ec0370608dbefe6a3b2401a9ea0c791be86b2d3`;
old33 tuple SHA-256 `e5430729792edfe2976f146b07d72dc836c928f648c6543cbbff6841cfdd9085`.

Файловые SHA-256 proposed:

- `docmancer/docs/domain/original_body_discovery.py`: `a28c337045757c49ebf79d44efc5e5eab5c498202f30a947d5152d8b7b81e3b7`.
- `docmancer/docs/domain/ordinary_body_context.py`: `d15e01ed738c7aa5ae604f2b3bf4da8f59aa94357a6f72804dcc01e471bdbc71`.
- `docmancer/docs/application/reference_query_tagging.py`: `a2a1abc7c242704a807e6dcdd7cb41f2613c9e8f95e9a5f726697f870631a285`.
- `docmancer/docs/application/_project_docs_service_part03.py`: `ad355db728bb63b028a4524e56ec05f212200c48de55b8e9a8eddc45b35cf5c3`.
- `docmancer/docs/domain/literal_context_admission.py`: `b4721d74c1e2539c8e958da62e5f01f4256b555e51068b75f567a0212f3eade5`.
- `docmancer/docs/interfaces/mcp/context_tools.py`: `4265329b1f34321234a8754098277cc986ddc342c56e9f08eb53f641e67381b2`.
- `docmancer/docs/application/_docs_context_projection_core.py`: `c31a8d8bb27e6b4ff6badb8348a60365befb4b2a3fa59db060d63c484d569acf`.
- `eval/agent_developer_v1/ordinary_body_controls.py`: `6964d56b75aa08ca63832816e4427ccea54290ffc246edcffa76db03cc43c66f`.
- `scripts/run_recovery_contract_gate.py`: `520d8f265f08f73ea241e280425208d63049ea0990f862e6f29f2ec0db72d800`.
- `scripts/run_recovery_mutation_gate.py`: `4caaa2146409dd3cbbc6ee026b750113acf6215cfe9598c4266457dd394405e1`.
- `docs/adr/0003-context-first-project-reads.md`: `3095e7f8d186967a44395094769cd1d76b409c00595e72fc674e24de8089cf4a`.

Статические проверки выполнялись только чтением exact Git blobs, чистой
обработкой текста/хешей и independent source review. Local execution,
Python import/AST/pytest/install не выполнялись. Commits/refs и итоговый
совместный CI принадлежат root. Production7 получили independent static
APPROVE; final helper/runner/ADR peer review и собственный runtime сохраняются
отдельными обязательствами до публикации/acceptance.

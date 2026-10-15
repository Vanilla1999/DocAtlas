# PR211: review миграции critical normative tests

Дата: 2026-10-09. База: `7a78c516a62304fc258bda5d5eb2b11544c829b5`.

Статус: implementation candidate со статической проверкой. Repository imports,
pytest и mutation runtime локально не выполнялись. PASS и killed mutants можно
заявлять только после существующего PR CI на конечном опубликованном SHA.

## Разрешённый slice

После подготовленного `PR211_CRITICAL_CONTRACT_PROPOSAL_RU.md` владелец указал
продолжать. Этот slice мигрирует retired normative acceptance на сохранение
source data, отсутствие implicit policy authority и bounded Python grammar.
Production, retrieval, исходные вопросы, gold и данные источников не изменены.
Другие gates и deferred retrieval остаются в прежнем scope.

Изменён `tests/docs/test_normative_language.py`. Его прежние 26 parameter tuples,
порядок, строки, значения `expected`, имя test node и аргументы сохранены.
Исторические `required`/`forbidden` остаются labels исходных fixtures; они больше
не объявляют действующий вывод policy modality из prose. Два остальных test
functions файла, включая их decorators и bodies, AST-identical базе.

## Текущий контракт и важная поправка к proposal

`docmancer/docs/domain/normative_language.py` прямо определяет отрицательный
compatibility adapter: `classify_normative_modality` возвращает `None`;
`python_declaration_line_indexes` отдельно распознаёт bounded Python syntax.
Старый classifier не восстанавливается.

В proposal предполагался `data/partial` для всех девяти prose cases. Полное
чтение producer и selector выявило два исключения: исходные вопросы уже явно
содержат технические идентификаторы. `evidence_requirements.py::build_requirements`
создаёт для них `query_exact_term`, а
`_evidence_selection_part02.py::_legacy_requirement_matches_unit` связывает
буквальное значение с полной видимой sentence unit. `_witness_for_requirement`
возвращает настоящий `unit_id`; `select_evidence` сохраняет assignment и не
добавляет `visible_content_assignment_required`, когда content assignment есть.

Root и независимый reviewer проверили эту цепочку до задания новых ожиданий.
Это исправление предварительного предположения proposal по текущему source
contract, а не замена неизвестного фактического runtime результата на PASS.
В тесте нет допуска любого из `{partial, complete}`.

| Frozen вопрос | Точный текущий literal contract |
| --- | --- |
| `Don't bypass PermissionService.` | Один `query_symbol:0:permissionservice`; value `PermissionService`; extraction `identifier`; provenance `query_exact_term`; role `generic_fact`; полная связанная sentence unit; `data/complete`. |
| `PermissionDecision.deferFollowUp is reserved for post-entry review.` | Один `query_exact:0:permissiondecision.deferfollowup`; value `PermissionDecision.deferFollowUp`; extraction `symbol`; provenance `query_exact_term`; role `generic_fact`; полная связанная sentence unit; `data/complete`. |
| Семь остальных retired prose rows | Нет requirements или assignments; `data/partial`; единственный missing reason `visible_content_assignment_required`. |

`complete` в этих двух строках относится только к механическому literal task
contract. Тест требует `untrusted_data`, `edit_ready=False`, отсутствие qualifiers,
policy roles, legacy policy arrays и mutation intent. Ни поведение host, ни
нормативный смысл отрицания не считаются доказанными literal assignment.

## Positive controls

Все 26 исходных rows требуют unknown modality. Отдельное авторское множество
содержит ровно прежние 15 single-line Python declarations: каждый требует `{0}`.
Остальные 11 rows требуют пустой line set. Существующий multiline parenthesized
import test сохранён без изменений.

Для каждого из девяти retired prose rows реальный `build_action_packet` получает
исходную строку как `question` и единственный authored evidence row:

- literal `docs/RULES.md`, stable child `normative-quote-1` и parent
  `normative-document-1`;
- полный `display_text`, SHA256 точного UTF-8 текста;
- действительный character span `[37, 37 + len(text)]` и line span `[4, 4]`.

Fixture не передаёт `trust_contract`, `public_requirements`,
`behavioral_contract_required`, policy metadata, lookup, fake provenance или
mutation grants. Packet строится обычным producer; ручной сборки или mock нет.

Positive требует `result=data` и ровно один source, затем прямое равенство всего
`source.text` исходной строке. Проверены display hash, stable identity, public
evidence identity, path, section и оба supplied span. Для двух literal cases
дополнительно проверены ровно один requirement и assignment, конкретные
ID/value/provenance/extraction/role/mandatory, полный authored requirement dict
с exact query span/text, `response_mode=value` и `lifecycle_intent=current`,
настоящий sentence unit, его
полный текст, оба content hashes и relative/absolute spans.

Полное equality requirement dict добавлено по independent review: bound packet
validator проверяет source/assignment, но не доказывает query provenance spans
и отсутствие посторонней optional semantic metadata самостоятельно. Поэтому
query span привязан к неизменённому вопросу, а дополнительные policy/subject/
relation fields не могут скрыться за проверкой нескольких выбранных полей.

Во всех девяти случаях настоящий
`validate_action_packet(packet, evidence_items=[original])` обязан вернуть `[]`.
Исходный evidence dict в конце остаётся точной копией состояния до producer.
Пустой failure/unknown не удовлетворяет положительному контролю.

## Отрицательные controls

Каждый negative начинает с отдельной глубокой копии валидного positive packet.
Исходный fixture и вопрос остаются прежними.

| Frozen source case | Порча только копии source.text |
| --- | --- |
| `Offline fallback cannot bypass the gate.` | `cannot` → `can` |
| `The worker may not continue without evidence.` | `may not` → `may` |
| `Don't bypass PermissionService.` | `Don't` → `Do` |
| `PermissionDecision.deferFollowUp is reserved for post-entry review.` | `post-entry` → `pre-entry` |
| `The invariant preserves immediate denial.` | `immediate` → `deferred` |
| `From configuration, retries are required.` | `required` → `optional` |
| `from configuration, retries are required.` | `required` → `optional` |
| `From configuration import rules are required.` | `required` → `optional` |
| `Import policy is required.` | `required` → `optional` |

Для каждой порчи пересчитываются `content_sha256`, `char_end` и packet estimate.
Ожидается ровно одна ошибка `source differs from bound retrieval window` при
валидации с исходным evidence. Поэтому checksum/span/estimate mismatch или
посторонняя exception не могут выдать себя за успешную проверку source binding.
В двух complete cases assignment остаётся связан с исходным evidence и не
переписывается под испорченный source.

Отдельные копии проверяют:

- trust promotion: единственная ошибка
  `sources.0.instruction_trust: 'untrusted_data' was expected`;
- edit promotion: единственная ошибка `edit_ready: False was expected`;
- каждый из `required_invariants`, `forbidden_changes`, `validation` добавляется
  по одному и получает конкретную strict-schema additional-property ошибку для
  этого поля. Runnable-looking command — только значение отвергаемого поля,
  никакая команда из packet не исполняется.

Каждая из этих копий также получает обновлённый estimate. Общего `assert errors`
или одновременной порчи независимых полей нет.

## Critical mutation guard identities

С gate-author согласованы literal assertion messages:

| Guard | Точное ожидаемое число FAIL при соответствующем mutant |
| --- | ---: |
| `critical_normative_no_authority` | 26 |
| `critical_python_declaration_grammar` | 15 |
| `critical_source_delivery_fidelity` | 9 |
| `critical_bound_source_fidelity` | 9 |

Прямое whole-text equality находится до hash/span/schema checks, чтобы source
truncation mutant был убит именно потерей source text. Эти числа — контракт
ожидаемого runtime gate, а не уже наблюдённый mutation результат.
Gate implementation и два остальных legacy mutants принадлежат отдельному slice
и review; этот файл их не реализует и не сертифицирует.

## Статическое evidence и ограничения

Сравнение с Git blob базы через stdlib AST подтверждает:

- все 26 tuples и decorator/аргументы parameterized node неизменны;
- authored grammar positives совпадают с 15 исходными single-declaration
  stdlib AST forms; 11 nondeclarations остаются отрицательными;
- corruption table содержит ровно девять исходных rows с retired label;
  каждый replacement меняет ровно одно конкретное вхождение;
- explicit-literal table содержит ровно два из девяти rows;
- два unrelated test functions, их decorators и bodies неизменны;
- изменённый файл парсится и компилируется без исполнения.

SHA256 старого test source:
`cdbd5a423c6042edd0e0d626144c04f93302aacecce3fb17941b1818b7f2433e`.

SHA256 candidate test source:
`b9c0190f1d89ccb3c81cec25af7393bc067dbcf5b7d8380abd5abee804dd0afe`
(10618 bytes, 244 lines).

Тест проверяет producer/validator после явной передачи in-memory evidence.
Он не удостоверяет acquisition, SQLite, retrieval sufficiency, MCP delivery,
реальные installed clients или model token cost. Локальных repository imports,
pytest, dependency installs и provider calls не было. Фактические positive
results и mutation-specific assertion kills подлежат проверке существующим CI.

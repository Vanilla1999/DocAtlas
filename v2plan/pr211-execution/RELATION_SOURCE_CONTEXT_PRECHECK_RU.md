# Remaining relation guards: native source-context precheck

Дата подготовки: 2026-10-10. База: published 126 `d76f6ab85e12f482ad6bec1d43040899f4b0a532`,
tree `63bff21aadbfb131082db075ed95ea7e89310e44`.
База интеграции после ordinary slice 128: `23af9fc5b5934bc651e40f510ec90c88e1642dcc`.
`source_checkout` в crosswalk сохраняет исходный published snapshot;
`integration_base_commit` обозначает этот более поздний commit.

## Статус и граница

Подготовлен узкий precheck двух семейств — callable form и strict-mode enumeration.
Он добавляет четыре настоящих public reads к одному существующему pytest test.
Новых test names нет. Оставшиеся 47 witness cases и остальные 25 safety cases
не изменены и не удалены. Исходный privacy read выполняется первым, с прежними
question/body и всеми прежними assertions.

Нового runtime, baseline PASS или mutation kill пока нет. Здесь нет разрешения
удалять остальные 47 cases. Их последующая миграция требует отдельного versioned
crosswalk и сохранения source-policy, condition и native obligations.
Текущий общий CI 126 с target 59/35 не является прогоном этого precheck.
Регистрация нового existing selector и двух fault recipes находится у root;
в этих четырёх файлах critical runner не меняется.

## Почему старое ожидание `not qualified` не всегда сохраняет смысл

Действующий `evidence_qualification.py` различает source eligibility,
source/body bindings и lexical attribution. После проверки текущего body
`qualified=True` означает retrieval attribution, `context_only=True`;
он не доказывает отношение между субъектом и свойством. Возвращаемый
`derived_parent_trace` равен `None`. Производитель плана сохраняет original
и явно заданные host lookups, без автоматически созданных relation queries.

Поэтому исходная строка о synchronous handler **для OtherHub**, содержащая
отдельное упоминание QueueHub, может быть доставлена целиком как контекст.
Она не доказывает, что handler для QueueHub synchronous. Проверка сохраняет обе
исходные фразы, запрещает синтез положительного QueueHub fact и отдельно проверяет
реальные answer/edit flags. Это не исправление голда на фактический boolean.

Заголовок и самостоятельные ссылки — другой случай. Их запрет как
`metadata_only_evidence` остаётся действующим body guard. Он проверяется на
фактически приобретённом current child, до попытки зачесть безопасную пустую
выдачу. Факт отсутствия содержательного свидетельства не превращается в
утверждение об отсутствии документа.

Решение согласуется с действующим `v2plan/CURRENT_WAVE_DECISIONS_RU.md`
(`b11aca6efebf133ec0c8f9d1b2c4d41155b672cb`):
source-attributed context, сохранение original inputs, отсутствие inferred
policy/behavioral/validation authority. Ограничения на работу и acquisition
сохраняются; новых output caps нет.

## Четыре неизменных ввода

| Case | Исходный вопрос | Body из frozen archive | Текущий обязательный результат |
|---|---|---|---|
| callable_positive | Can a handler for QueueHub be synchronous? | CASES[2][2] | Полная исходная цитата, retrieval-only/cite-only, no answer/edit |
| callable_wrong_role | тот же точный вопрос | negative row 4, две фразы про OtherHub и QueueHub | Обе фразы целиком, без положительного QueueHub fact и semantic authority |
| strict_positive | Which ways enable strict mode? | CASES[3][2], введение и два пункта | Полный введённый список, retrieval-only/cite-only, no answer/edit |
| strict_metadata_only | тот же точный вопрос | negative row 8, heading + две standalone links | Native metadata-only rejection, no sources/coverage |

В новом fixture `Guide.md` содержит ровно исходный body; дополнительного
заголовка, lookup, path hint, requirement или ожидаемого факта в запросе нет.
Каждый case использует отдельный конечный catalog и host-owned store.
Сохранённый старый privacy call по-прежнему добавляет собственный `# Rules`;
его setup не затронут.

Повторно использован существующий archive:
`eval/task_level/contract_history/admission_relation_compiler_inputs.py.txt`,
blob `f230beaa41ebb0b999f97493007fe253c629ef78`, 9679 UTF-8 bytes,
SHA-256 `34620c11c83e58dad640b4ee56711830de9ab3ba18ca0c64e88e6f26ffea2809`.

Все четыре вопроса и body независимо найдены как точные literal values в archive.
Каноническая матрица `[id,family,question,body,current_outcome]` имеет SHA-256
`391e69055fb006e82ac1109a0d1ce1e89c1cbce02651bc37cd4cb756a224477c`.
Helper проверяет отдельно archive digest и этот фиксированный matrix digest,
а затем question/body hashes. Изменение body вместе с его полями в crosswalk
не обходит независимую константу.

## Реальные границы и наблюдения

`write_project` и `index_project` выполняют существующую явную finite preparation.
До public call проверяются успешный exact roster и настоящий committed SQL child:
полный body, source/file hash, owner, scope, generation и char/byte/line spans.
Ожидаемые owner и body берутся из fixture root и frozen input, не из найденного
candidate.

`structured_chunking.py` `89528de2cb78820ca244924d5be39a94164355de`
объединяет colon-terminated prose и непосредственно следующий list в один
contiguous atom. Короткие исходные тела помещаются в одно существующее display
window. Это source-derived обоснование fixture; контроль всё равно требует
наблюдаемый один SQL child и полный public body, не делает вывод о wire только
из parser source.

Один `capture_public_call` на case вызывает настоящий public MCP handler.
Наблюдатели оборачивают реальные bound member method, dispatcher и native
`reference_query_tagging.qualify_evidence`; каждый вызывает original ровно один
раз и возвращает тот же result object. Запись qualification ограничена временем
реального member call. Ни kwargs, ни candidates, ни возвращаемые значения не
подменяются. Число root acquisitions проверяется как два текущих differently
filtered исходных запроса; новых query directions нет.

Даже metadata-negative требует непустых actual dispatcher chunks и native
qualification records с exact original query contract, immutable source binding,
catalog hash и исходным body. Empty fixture, ранний exception или отсутствие
observer evidence дают FAIL. В положительных случаях проверяется весь quote,
его exact public/snapshot binding, текущий source/content hash и все координаты.
Единственное optional поле — `source_uri`: late handler вправе удалить locator,
если регистрация недоступна. Все остальные поля сравниваются целиком, без whitelist
или удаления различий. Если URI присутствует в public source, он должен быть
непустой строкой, равной обоим captured locator fields, и существовать в реальном
`source_reader.has_reference(uri)`. Это чтение session registry в памяти, без
hydration/дополнительного MCP read. URI hashing не копируется в test oracle.
Полный file hash с `sha256:` и catalog-entry hash отдельно связаны с frozen body
и успешной preparation; raw source/window digests проверяются без префикса.

Actual projected payload проверяется до позднего public validator: ответ с
ошибочной authority нельзя спрятать последующей конвертацией в error packet.
Валидируются также конечный public DTO и все существующие projected snapshots.
`query-original` может иметь честную lexical attribution; это не full-answer
coverage и не derived/generated semantic credit.

Fingerprint сравнивает все файлы и каталоги fixture app storage, generation,
catalog и source до/после чтения. Это проверка отсутствия изменений, не заявление
о нуле файловых чтений. Public payload не должен содержать прежние четыре private
fields. Печатаемый `RELATION_SOURCE_CONTEXT_RECEIPT` содержит только hashes,
идентификаторы, spans, counts, статусы и причины. Полные тела остаются fixture
input и внутренним capture. Это synchronous in-process MCP вызов, не проверка
настоящего installed client или stdio transport.

## Два pending directed faults

| Fault | Изменение только в disposable copy | Первый обязательный named guard | Expected |
|---|---|---|---|
| relation-visible-metadata-as-body | После успешного canonical `prepare_reference_probe`: `lines = body.splitlines()` → `lines = visible_text.splitlines()` | `critical_relation_metadata_cannot_supply_body` | 1F / 0E / 0S |
| relation-callable-context-as-answer | После final `_payload`: generic `original_question.startswith("Can ")` повышает answer flags и обновляет estimate | `critical_relation_public_no_answer_authority` | 1F / 0E / 0S |

Первый fault сохраняет source/hash проверки и делает title/heading частью
substantive body. Сохранённый старый privacy read и три новых body-positive
cases остаются содержательными; named guard находится на четвёртом новом read.
Даже если поздний projector снова отклонит эту строку, ошибочная native
qualification уже не пройдёт независимый guard.

Второй fault не содержит fixture identifiers. Сохранённый первый запрос
`Which takes precedence…` не относится к `Can ` frame; первая новая фактическая
проекция достигает собственного no-authority guard. Error packet после
validator не считается правильной защитой от наблюдаемого ошибочного producer.

В crosswalk сохранены полные unique anchors, before/after source SHA-256,
expected failed-case count и intended guard. При изменении owning source hashes
до интеграции recipe нужно пересверить. Требуются настоящий здоровый baseline,
оба отдельных нужных kills, отсутствие ERROR/SKIP и действующая import-origin
проверка. Отдельный import probe не является доказательством импорта в том же
pytest process.

## Exact manifest для review

Все файлы mode `100644`.

| Path | Base blob | Proposed blob |
|---|---|---|
| eval/agent_developer_v1/relation_source_context_controls.py | NEW | c4ebf2ddb4b6c66669f119efa103de1e4556d422 |
| tests/docs/test_admission_relation_safety.py | f3374394afce41c21659a9fc582f73e78b5ecc35 | e17e1a69af1a4af61ba4a864fed09fd63031ff05 |
| eval/task_level/contract_history/admission_relation_live_source_inputs.json | NEW | bf9d0c72261231ca006fe19c2fb5c707ea3b88e5 |
| v2plan/pr211-execution/RELATION_SOURCE_CONTEXT_PRECHECK_RU.md | NEW | этот файл |

Helper: 282 lines, SHA-256 `affefeb2605562c5b3ec1114647bc1f069a306c4124a2d57fca5fa94f27a0328`.
Safety module: 176 lines, SHA-256 `f4afb5c9e26ec2f4897c12b37d33cd04a6369c4a76c185bdc80f2b38d78f25b2`.
Crosswalk: SHA-256 `d0a38d178f6d91d3b90f460690c420696b73bacdbc5a2eb632abfdb97171580e`.

У safety добавлены ровно две строки. Их удаление побайтно восстанавливает весь
исходный `f3374394`; все 10 pytest names, decorators, imports, другие тела
и старый privacy prefix сохранены. Witness `6132b5b1` и существующий relation25
archive/AST preservation gate не менялись. Existing selector добавляет один
baseline pytest case; внутренние четыре reads не создают четыре новых names.

Три code/data blobs read back: exact PASS. Ни syntax/runtime execution, ни
production mutation, ни Git commit/ref changes здесь не выполнялись.
Независимый reviewer `readonly_accessor_resume` завершил static review helper,
safety splice, четырёх frozen inputs и исходного crosswalk: APPROVE. Runtime
при этом не запускался.

После ordinary slice 128 projection core сменился на
`ec87e90b8ef40faab65e514a3e417ee9d6bf0b0c`: diff состоит ровно из двух
diagnostic reason replacements. Callable mutant anchor сохранился единственным.
В crosswalk обновлены только его owning blob и before/after source hashes
(кроме явного пояснения integration base):
before `c31a8d8bb27e6b4ff6badb8348a60365befb4b2a3fa59db060d63c484d569acf`,
after `76f4397c0fe261ace66ad6f638528b08980a76e497ef703c56ed42c1efa99765`.
Helper, safety splice, raw matrix, historical expectations и metadata fault
не менялись. Последняя привязка повторно вычислена из прочитанного exact blob;
это статическая операция, не mutation kill. Новое runtime evidence остаётся PENDING.

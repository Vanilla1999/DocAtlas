# PR211: независимый review critical contract migration

Дата: 2026-10-09. База: `7a78c516a62304fc258bda5d5eb2b11544c829b5`.

**Вердикт: APPROVE для публикации этого узкого test/gate slice и его проверки
существующим PR CI.** Неустранённых замечаний к рассмотренному source diff нет.
Новый runtime baseline и шесть mutation runs ещё **NOT RUN**. Этот review не
объявляет critical gate или PR211 зелёным и не снимает остальные blockers.

Reviewer самостоятельно прочитал текущие production producer, validator,
requirements, selector и grammar, затем сравнил изменения двух авторов с Git
blob базы. Reviewer не изменял их implementation. Во время review исправлены
два существенных уточнения: предварительное ожидание uniform partial и неполная
проверка query provenance для двух допустимых literal assignments.

## Рассмотренные файлы

| Файл | SHA256 | Размер UTF-8 |
| --- | --- | ---: |
| `tests/docs/test_normative_language.py` | `b9c0190f1d89ccb3c81cec25af7393bc067dbcf5b7d8380abd5abee804dd0afe` | 10618 bytes |
| `scripts/run_critical_mutation_gate.py` | `423a3e98a04bea4cec821381326439f0f045ee2bbe561ee17b8cd7a59110ea09` | 15272 bytes |
| `v2plan/PR211_CRITICAL_TEST_MIGRATION_REVIEW_RU.md` | `7b0df3546ecc06b09e61b195187dc4514321d54c3b88f4aa666b82842ad20f4a` | 12425 bytes |
| `v2plan/PR211_CRITICAL_MUTATION_MIGRATION_REVIEW_RU.md` | `7531efd22a7e02bb2723c5228005652c6f02d15b95cd5d43cf5dc08edf454ab0` | 13016 bytes |

Также прочитаны исходный `PR211_CRITICAL_CONTRACT_PROPOSAL_RU.md`, актуальные
`CURRENT_WAVE_DECISIONS_RU.md`, `V4_PRODUCT_DECISIONS_RU.md`,
`action-packet-v4/CONTRACT.md` и исторический R3 dictionary-exit report.
Продолжение владельца и границы миграции отражены в текущих decisions. Production,
retrieval, Task33 protocol, старые Task33/host-turn tests, workflow и frozen corpus
в данном slice не меняются. Deferred retrieval остаётся вне scope.

## Контракт установлен по source и решениям

`normative_language.py::classify_normative_modality` явно является отрицательным
compatibility adapter: source prose не создаёт policy modality. Его `return None`
согласуется с R3 removal of prose fact/validation credit, а bounded Python grammar
сохранена в отдельной функции. Поэтому прежние девять `required/forbidden`
ожиданий не являются актуальным policy API. Простая замена expected на `None`
не проверяла бы оставшиеся свойства; предложенный successor делает их явными.

`_action_packet_part03.py::_candidate_source` переносит whole display text,
хеш и supplied spans, ставит `instruction_trust=untrusted_data`.
`build_action_packet` сохраняет `edit_ready=False` независимо от completeness.
`_action_packet_shared.py` запрещает иные trust/edit значения и лишние поля.
`_action_packet_part04.py::validate_action_packet` проверяет schema, self hash,
spans и полное равенство source DTO кандидату из переданного исходного evidence.
Последняя проверка имеет иной смысл, чем совпадение packet с собственным hash.

### Уточнение двух complete cases

Предварительное предложение ожидало partial во всех девяти cases. Независимое
чтение источников подтвердило конкретное исключение, до runtime:

1. `evidence_requirements.py::build_requirements` получает неизменённый исходный
   вопрос. `PermissionService` порождает identifier requirement
   `query_symbol:0:permissionservice`; `PermissionDecision.deferFollowUp` порождает
   symbol requirement `query_exact:0:permissiondecision.deferfollowup`.
2. Эти requirements имеют `kind=exact_term`, `public_provenance=query_exact_term`,
   `proof_role=generic_fact`. `_with_canonical_policy_requirements` не добавляет
   policy obligations по содержимому prose.
3. `_answer_units_part01.py` выделяет полную sentence с `proposition=False`.
   `_evidence_selection_part02.py::_legacy_requirement_matches_unit` проверяет
   буквальное наличие exact value; `_witness_for_requirement` создаёт unit witness
   с причиной `visible_literal_only`.
4. `_evidence_selection_part03.py` переносит unit ID/hash/spans в assignment.
   Missing reason `visible_content_assignment_required` добавляется только при
   отсутствии content assignment. Поэтому эти два packet могут быть complete
   по конкретному literal contract. Остальные семь не имеют requirements или
   assignments и сохраняют partial с этим единственным missing reason.

Это соответствует V4 contract: complete требует покрытия canonical mandatory
requirements валидными assignments и не даёт workflow/edit permission.
Нормативный или поведенческий смысл фразы literal matching не удостоверяет.
Тест требует именно указанное разделение 2/7; допуска любого произвольного
complete/partial, изменения question или добавления authority flags нет.

## Frozen fixtures и непустой positive

Независимое сравнение stdlib AST с базовым Git blob подтверждает неизменность
всех 26 parameter tuples, их порядка, старых expected labels, decorator,
имени и аргументов исходного node. Два остальных test functions модуля вместе
с decorators и bodies AST-identical. Digest исходных 26 rows в формате
`json.dumps(rows, ensure_ascii=False)`:
`aa7eacbbf8dc28dcca0fced31522f6d33822c36f9c2d0a697968f189b97440d2`.

Все 26 cases требуют unknown modality. Отдельное authored множество содержит
15 синтаксически корректных single-line Python declarations: независимый
`ast.parse` каждой исходной строки подтверждает это множество. Для этих 15
ожидается `{0}`, для остальных 11 — пустой line set. Существующая multiline
parenthesized-import проверка сохранена отдельно без изменений.

Все девять retired prose rows действительно вызывают обычный `build_action_packet`
с исходной строкой как question и authored in-memory evidence. В evidence есть
literal `docs/RULES.md`, stable child и parent, полный текст, точный UTF-8 hash,
character span `[37, 37 + len(text)]` и line span `[4, 4]`. Нет mock producer,
ручного успешного packet, fake permission metadata или обхода selector.

Каждый positive требует data и ровно один source, прямое равенство всего text,
hash, stable identity, public evidence identity, path, section и supplied spans.
Для двух complete cases дополнительно проверяются ровно один requirement и
assignment, точные literal IDs/values, provenance, grammar extraction kind,
generic role, полный sentence unit, content hashes и relative/absolute spans.
Реальный bound validator обязан вернуть пустой список ошибок. Входной evidence
в конце должен совпадать с сохранённой до producer глубокой копией.

По замечанию reviewer автор заменил проверку нескольких requirement fields
на **полное authored dictionary equality**, включая `query_span_start/end/text`,
`response_mode=value` и `lifecycle_intent=current`. Это необходимо: bound packet
validator сам не связывает query provenance spans с исходным вопросом, а
непроверенная optional subject/relation metadata могла бы пройти рядом с верным
literal value. Теперь ошибочный query span или дополнительные semantic fields
не удовлетворяют positive. Нет требования принять пустой failure как успех.

## Отрицательные controls действительно проверяют внешнюю привязку

Таблица corruption содержит ровно исходные девять retired rows. Для каждого
reviewer статически проверил одно исходное вхождение и фактическое изменение:
`cannot→can`, `may not→may`, `Don't→Do`, `post-entry→pre-entry`,
`immediate→deferred` и четыре отдельных `required→optional`. Регистровые варианты
From/from остаются разными исходными cases.

Портится отдельная копия уже валидного packet. В ней пересчитаны собственный
SHA256, `char_end` и fixed-point estimate; validator получает неизменённый evidence.
Ожидается ровно одна ошибка `source differs from bound retrieval window`.
Следовательно, плохой checksum, длина span, estimate или посторонняя exception
не заменяют требуемую проверку. В двух complete случаях assignments остаются
валидными относительно оригинального evidence; их не удаляют ради нужной ошибки.

Ещё пять независимых negative copies на каждый prose case проверяют trust
promotion, `edit_ready=True` и отдельное добавление каждого из
`required_invariants`, `forbidden_changes`, `validation`. Каждый требует точной
единственной schema-ошибки соответствующего поля и получает свежий estimate.
Общего `assert errors`, порчи нескольких независимых полей и исполнения command
из validation fixture нет. Эти checks удостоверяют schema/no-authority границу,
а не самостоятельную интерпретацию семантики запрета или условия.

## Шесть guard-specific mutations

| Mutation | Ожидаемый assertion guard | FAIL / остальные PASS |
| --- | --- | ---: |
| Убрать запись распознанных Python declaration lines | `critical_python_declaration_grammar` | 15 / 11 |
| В exact compatibility function вернуть `required` | `critical_normative_no_authority` | 26 / 0 |
| Удалить последний символ только при переносе source text | `critical_source_delivery_fidelity` | 9 / 17 |
| Отключить сравнение source с исходным bound window | `critical_bound_source_fidelity` | 9 / 17 |
| Прежний Task33 actionability mutant | Исходный singleton assertion | 1 / 0 |
| Прежний host-turn-limit mutant | Исходный singleton assertion | 1 / 0 |

Reviewer самостоятельно извлёк все old/new literals из gate AST и проверил:
каждый anchor встречается ровно один раз в неизменённом production source,
после замены меняется hash, все шесть altered source variants компилируются без
исполнения. Полные два прежних `Mutant(...)` calls и все три TARGET_TESTS
AST-identical базе. Изменение `return None` привязано ко всей нужной функции,
а не к случайному return. Реальные production files не модифицировались.

Producer fidelity assertion стоит до проверки checksum/schema, поэтому его
mutation должна провалить именно прямое whole-text equality. Bound-validator
mutation оставляет непустой positive исправным и должна провалить конкретное
negative expectation. Неработающий старый anchor не объявляется killed;
общее число проверяемых mutations увеличено с трёх до шести.

Gate требует baseline из трёх прежних групп **26+1+1**, ноль failures/errors/skips,
непустые уникальные identities и согласие JUnit summaries с testcase outcomes.
Сохранность именно исторических 26 parameter strings установлена отдельным
сравнением source AST выше; gate не дублирует их второй таблицей. Каждый mutant
должен собрать exact roster своего фактического зелёного baseline subset,
завершиться pytest exit code 1, дать указанное число assertion failures и ноль
errors/skips. Для четырёх новых mutations сравнивается первая строка
`failure.message` с точным `AssertionError: <guard>`, а не marker в traceback.

Источник этой формы JUnit отдельно проверен на восстановленных artifacts
предыдущего `7a78c51`: все три core XML содержат прежние 26 normative identities
с 17 PASS / 9 FAIL; custom assertion в `test_cli_literal_query_binding` имеет
формат `AssertionError: <message>` в первой строке. Это проверка формата старого
artifact, не запуск и не PASS новой реализации.

## Изоляция, evidence и предел review

Как прежде, каждый запуск получает отдельную копию source; source-copy ignore
rules, offline environment и прежние target selectors сохранены. Перед pytest
проверяются пути и hashes 14 нужных modules внутри текущей копии. Для mutants
probe идёт после actual mutation; import failure не засчитывается как kill.
`_apply_mutant` дополнительно сверяет hash реально записанного source.

После успешных runs сохраняются компактные JUnit, stdout/stderr, import-origin
и JSON evidence с actual exit code, roster/outcomes и before/after source hashes;
полная успешная source copy удаляется как прежде. Данные помогают проверить
последующий CI outcome, не заменяя его. Шесть kills и 28 baseline PASS пока
являются требованиями, а не наблюдённым результатом.

Локально reviewer выполнял только чтение, Git diff/show, stdlib AST/JSON/XML/hash
и compile без execution. Repository imports, pytest, mutation subprocesses,
dependency/provider/model operations не запускались. Unit packet tests не
удостоверяют SQLite acquisition, retrieval quality, MCP delivery, installed apps
или model-visible token cost. После обычной публикации root должен проверить
настоящий baseline, все шесть intended kills и совместный CI конечного SHA.

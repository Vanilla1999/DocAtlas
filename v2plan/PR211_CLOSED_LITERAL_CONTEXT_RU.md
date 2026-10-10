# PR #211: контекст по замкнутому запросу literal identifier

Статус: production и controls подготовлены; независимый review и runtime acceptance ещё обязательны.
База: `2acfaa4fdac8cc599d84ae1c48836335e9cd29a7`. Владелец ветки подтвердил, что три изменяемых файла не менялись на `c1e058cb51072f02620329000e2d68706a96bd67`.

## Наблюдаемая причина

Обычный P1.4 CI на 2acf: [run 37994136669 / job 114035683658](https://github.com/Vanilla1999/DocAtlas/actions/runs/37994136669/job/114035683658).
Результат 7/14; discovery 3/10; complete fact 2/5; runtime errors 0; evaluator controls 5/5.
Во всех 14 строках READ_STATE сохранены generation, SQLite bytes, catalog и документы: `state_equal=true`, `changed_fields=[]`.
Ранее исправленный first-read SQLite write больше не является причиной этих failures.

Первый miss `behavior_orders_store`:

- Исходный вопрос без переписывания: `What does OrdersDraftStore do?`.
- Единственный ожидаемый active member `packages/orders/README.md` действительно проиндексирован; failed/unexpected members отсутствуют.
- Реально найдено всё тело длиной 85 символов: `OrdersDraftStore stores draft orders as JSON records keyed by order id before upload.`.
- SHA-256 тела и найденного окна совпадают: `6f13aec3ccc8d596f1552421aa7f4e0f2f2738b6e9654eeab1621e4a07f704a1`.
- Candidate BM25 использует or_fallback; совпал OrdersDraftStore, literal ratio 1/4. У канонической qualification также 1/4, exact_terms пусты, причина `insufficient_visible_match`.
- Root reference остаётся `unresolved`, `explicit=false`; прежний literal admission возвращает null.
- Ranking/projection ещё не достигнуты; delivery блокируется с `required_evidence_missing`.

Это фактический drop уже найденного source body на admission/qualification boundary.
Candidate BM25 score и query-local qualification score имеют разные значения/назначения; один не заменяет другой.
Две одинаковые diagnostic rows не доказывают два engine calls. Observer counts — число событий наблюдателя.

Artifact `11646516656` (`p1.4-current-retrieval-37994136669-1`, 26490 bytes), ZIP SHA-256:
`11b98ef3096f901c549beefd53d136de304f4b07631b87a4ba6a49e4a1d3b711`.
Эти данные прочитаны из обычных сохранённых CI logs; новый production-код ещё не запускался.

## Узкий согласованный контракт

Дополнительный read-only context route принимает только полностью потреблённые формы:

1. `What does <literal identifier> do?`
2. `What is <literal identifier>?`

Literal должен уже присутствовать в исходном вопросе как unresolved, не explicit, technical mention и быть identifier.
Новые словари имён, алиасы, перевод, stemming, role inference или общий допуск любого CamelCase не добавляются.
Слова оболочки регистронезависимы; начальные/конечные whitespace сохраняются в исходной строке.
Сам literal сравнивается с источником с точным исходным регистром и границами technical token.

Любой остаток, условие, модификатор или второй субъект вне этих форм не открывает новый route.
Например, `What does OrdersDraftStore do using telepathy?` и `What is OrdersDraftStore under the lunar policy?` не допускаются этим расширением.
Существующий отдельный explicit-symbol route сохраняется.

Admission всё ещё сначала проходит прежние проверки complete catalog, current member/catalog hash, scope, raw body hash, source window, owner и generation через канонический qualifier.
Fallback разрешён только после `insufficient_visible_match`; другие причины отказа не обходятся.
Точный literal должен находиться в уже проверенном окне и в содержательной body unit: heading, link-only, identifier-only label либо одноимённый prefix недостаточны.
Никаких дополнительных source reads, generated lookup queries, semantic retry или новых projection путей нет.

Полученный quote остаётся context-only. Исходная qualification не становится успешной, root reference остаётся unresolved, `query-original` остаётся missing.
`coverage_credit=false`; answer_supported, answer_available и edit_ready остаются false.
Scope/hash/generation/ownership и operational consent/delivery veto не ослаблены.

## Реальные controls и directed mutations

В существующий `run_recovery_contract_gate.py` добавлен один case `closed_literal_context`; прежние 11 сохранены.
Он работает через фактический LocalMemberService, finite catalog, подтверждённое индексирование и публичный MCP payload capture.
Наблюдатель сохраняет уже полученные projection inputs/results; engine не подменяется.

- 6 положительных публичных чтений: два замкнутых OrdersDraftStore вопроса; PaymentOutbox; новый RelayBufferCell; тот же RelayBufferCell с raw whitespace/CRLF; DocAtlas.
- Проверяются полные исходные fact bytes, фактические raw document hashes и spans, authoritative snapshot, validator, original trace и отсутствие query/answer/edit/role credit.
- 7 соседних отрицательных вопросов проверяют условия, остатки, второй субъект, неизвестный modifier и второй вопрос.
- 6 реальных изменений индексируемого источника проверяют удалённый literal, другой регистр, heading-only, identifier-only, link-only и prefix.
- 4 замороженных отрицательных вопроса quantum/telepathy из Legacy/V2 используют тот же DocAtlas source, который отдельно дал положительный контекст.
- Перед каждым из 23 публичных чтений и после него сравниваются generation и SHA-256 SQLite, catalog и файла.
- К первой положительной выдаче повторно применены существующие 13 replay/operational guards: чужой project/scope/catalog/hash/generation, stale/window/body/raw document, missing reference, forged admission и veto/consent.

В существующий recovery mutation gate добавлены два реальных production mutants, всего 16:

| Mutant | Обязательный intended guard |
| --- | --- |
| closed-literal-context-disabled | recovery_closed_literal_source_fact |
| closed-literal-context-ignores-extra-conditions | recovery_closed_complete_syntax |

Baseline roster теперь 12 cases. Import hashes, frozen TREASURE inputs, evaluator rejection controls и требование конкретного guard/exit code сохраняются.
Crash, другой assertion или stale source не считаются успешным kill.
Critical mutation runner не изменён: он принадлежит отдельному admission-meaning precheck.

## Exact manifest

| Файл | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| docmancer/docs/domain/literal_context_admission.py | 6f69b9524d4167b0609252fc5583906ac7005b7f | 98648cd696d99cc8e7e27328f759075fca78c313 | 100644 |
| scripts/run_recovery_contract_gate.py | cd199b21bc127c148a63f8d21188fe924fcb0c89 | 31abc4d4d10d91831f714f79a5537a3e67806ac5 | 100755 |
| scripts/run_recovery_mutation_gate.py | eb4cad61d6f00e8231749991e64b527829c7ddc3 | 4cb9540f7bac9ed68eddec3279fd6bef61b5d5d6 | 100755 |

После review владелец ветки публикует slice и читает обычные recovery baseline/mutation и P1.4 результаты на одном фактическом SHA.
Ожидаемое исправление относится к двум behavior failures; оставшиеся пять failures не объявляются решёнными.
Существующие quality scorers, frozen questions/facts и finite membership не меняются; лимит стоимости не вводится.
Локальные imports, pytest, subprocesses и runtime не выполнялись.

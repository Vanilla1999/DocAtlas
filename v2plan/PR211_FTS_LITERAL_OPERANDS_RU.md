# PR #211: literal words at the SQLite FTS boundary

## Actual failure and proposed correction

На опубликованном HEAD `eb2c4f3b3e0065110a1bfe2c855e4a05803fa37a`, run `38010627863`, job `114089537662`, новый recovery printer зафиксировал failure до projector: `positive_case_index=13`, `read_index=52`, `literal=DeliveryEpoch`, `projection_attempt_count=0`, `delivery_inputs=[]`, public status `failed`. Исходный вопрос — `" \tEXPLAIN CommitLatch AND DeliveryEpoch.\r\n"`; ожидаемый source hash `7f6a583c7a54cafc9a2f8d462dc8adf961935406c074a99e35297bf6ba0e9f86`. Baseline сохранил **11 PASS / 1 FAIL / 0 ERROR**, mutation runner отказал незелёной baseline в credit. Это [реальный job receipt](https://github.com/Vanilla1999/DocAtlas/actions/runs/38010627863/job/114089537662).

Печатавшийся payload не включал вложенное `error.exception_type`, поэтому конкретный тип исключения не заявляется наблюдённым. Source audit показывает причинный путь: `_search_rows` из `core/_sqlite_store_part03.py` blob `4fd12519b431e1a1ffe1e2190ffc323a14b022d7` выделяет literal words, но передаёт их в FTS без кавычек. Для данного вопроса fallback равен `EXPLAIN OR CommitLatch OR AND OR DeliveryEpoch`: исходное uppercase `AND` становится синтаксисом между соединителями `OR`. Первый SQL вызов ловит OperationalError, fallback исполняется вне этого try. Это source-derived объяснение наблюдённого раннего failure; новый runtime ещё требуется.

Исправление экранирует каждый уже выделенный `\w+` token как FTS string в обоих местах: implicit-AND запросе и OR fallback. Символов кавычек внутри этих tokens нет. Не удаляются `AND`, `OR`, `NOT`, не добавляются stopwords, lowercasing или semantic query rewriting. Исходный question, source body, query hash/trace, line/character spans и qualifier thresholds не меняются. Обычные FTS filters, scoring, active generation, row merge/dedup и ranking остаются прежними. Exception policy не расширяется.

## Caller contract

Это plaintext retrieval boundary. Действующий `SQLiteStore.query(text, ...)` передаёт original text в `_search_rows`; сам `_strip_stopwords` уже выделяет слова через regex и не сохраняет quotes, parentheses или полный FTS DSL. `RetrievalDispatcher` и `retrieval/lexical.py` вызывают этот same query path. Public search принимает query string; отдельного raw-FTS параметра в изученных интерфейсах нет.

Проверены все SQLite shards, public search/lexical paths и целевые FTS tests. В них найден один production caller `query()` и direct test `_search_rows("projectiontoken rareterm", 20)`; оба используют текстовые слова. Это ограниченный source audit перечисленных владельцев, не заявление о повторном глобальном аудите всех файлов. Участвующие источники: `core/_sqlite_store_part03.py` 4fd12519, `retrieval/_dispatch_part01.py` 3f43104e, `retrieval/lexical.py` b51d9c79, `mcp/search.py` cde3caa0, `tests/test_active_fts_projection.py` 25d5a2e3.

`literal_context_admission._closed_explain_literals` уже принимает исходный регистр frame и trailing whitespace. Его parser, исходный positive case, факты и negative/immutable controls здесь не меняются. Обнаруженный дефект не исправляется подстановкой lowercase вопроса.

## Native independent control

Новый helper вызывается внутри существующего `closed_literal_context`, перед прежними сценариями. В ordinary pytest roster или в двенадцать recovery case names ничего не добавлено. Он не содержит P14/P15 вопросов или gold facts.

Fixture явно выбирает три документа:

| Path | Exact body |
|---|---|
| `manual/literal-operators.md` | `FtsLiteralProbe AND OR NOT keeps λ payload.` |
| `manual/without-operators.md` | `FtsLiteralProbe keeps μ payload.` |
| `manual/without-probe.md` | `AND OR NOT retains ν payload.` |

Настоящие `write_project`, `isolated_service`, `index_project` создают finite member store и подтверждённый native transaction. Assert требует точный indexed roster без failed/excluded/unexpected paths. Warm positive ``Explain `FtsLiteralProbe`.`` обязан вернуть полный исходный target body через настоящий public handler с false answer/edit flags; пустой или сломанный handler не является здоровой baseline.

Warm positive использует прежний explicit quoted-literal route. Он не зависит от закрытой bare-identifier формы и поэтому не перехватывает intended guard старой mutation `closed-literal-context-disabled`.

Далее наблюдаются два настоящих public вызова, без подмены ответа или параметров:

1. `AbsentAnchor FtsLiteralProbe AND OR NOT` не имеет полного conjunctive match. Все три реальные rows должны вернуться из `or_fallback`.
2. `FtsLiteralProbe AND OR NOT` имеет ровно один полный conjunctive source. Он обязан иметь mode `and`, а два неполных источника — `or_union`.

Expected rows задаются независимыми fixture facts: один body содержит все четыре literal words, два других — неполные подмножества. Oracle не сравнивает строку SQL с реализацией quoting и не выдаёт original-question answer proof. Observer перехватывает `SQLiteStore._search_rows`, вызывает исходный метод ровно один раз на обращение, сохраняет только фактически вернувшиеся row path/source/stable ID/generation/mode/hash и возвращает тот же rows object. Он не подставляет missing results и не ловит backend exceptions вместо настоящего MCP boundary.

Каждый вызов проверяет before/after generation и SHA-256 fingerprints всех project/store файлов. Для всех возвращённых rows проверяются точная текущая source identity, generation, stable ID и SHA-256 полного source body. Публичный error или отсутствие matching backend receipt дают intended guard failure. Обычный negative projection допустим в двух backend probes только вместе с успешным native execution и конкретными наблюдёнными rows; warm context обязан быть содержательным.

## Mutations and diagnostics

К прежним 31 reviewed mutations filename slice добавлены две:

| Mutation | Exact intended guard |
|---|---|
| `fts-primary-bare-operator-token`: убрать quoting только primary operands | `recovery_fts_literal_primary` |
| `fts-fallback-bare-operator-token`: убрать quoting только OR operands | `recovery_fts_literal_fallback` |

Fallback probe идёт первым. При primary-only mutation он всё ещё должен пройти, после чего distinct primary-mode expectation ловит неверную AND semantics. При fallback mutation настоящий public boundary возвращает error на первом probe; oracle проверяет реальный результат, не преобразует произвольные Python/import errors в kills. Остальные 31 blocks, source/oracle mutation isolation, baseline gate и exact guard verifier сохранены.

Оба новых executed modules — core part03 и helper — входят в runner manifest; поэтому чужой или stale импорт не может дать green. Recovery printer дополнительно печатает только уже существующие вложенные `error.reason_code`, `exception_type`, `retryable`, `where`. Новых вызовов, raw traceback/body или диагностического exception bypass нет. Два лишних пустых ряда удалены; main gate остаётся 999 строк.

## Review manifest

FTS slice следует после отдельного filename slice. Mode existing runners сохранён.

| Path | Mode | Base blob | Proposed blob |
|---|---|---|---|
| `docmancer/core/_sqlite_store_part03.py` | 100644 | `4fd12519b431e1a1ffe1e2190ffc323a14b022d7` | `96f35c1f02a97f58f05b15f154c2fc45487487dc` |
| `eval/agent_developer_v1/fts_literal_controls.py` | 100644 | NEW | `b02fe5c98ca8484d4e2c8cca8531b8a366319953` |
| `scripts/run_recovery_contract_gate.py` | 100755 | `a3f9269526848a0f32d652ec7a88c9a54bdbe991` | `a3e4d05172bb2e124632ad535056a3a02b90df8b` |
| `scripts/run_recovery_mutation_gate.py` | 100755 | `08a9b8da959a86637415f8c66fa13fe2bffb4357` | `4644eb82522eadeea7807fd067759cfce76a7e11` |
| `v2plan/PR211_FTS_LITERAL_OPERANDS_RU.md` | 100644 | NEW | this note |

GitHub create/fetch roundtrips, unique mutation anchors и inverse source transforms проверяются без запуска repository Python. Все source bodies/questions/case IDs прежнего recovery кода, включая падавший whitespace positive, сохраняются побайтно.

## Acceptance remains open

Новый actual baseline/mutations ещё не запускался в этой подготовке. Цель после filename+FTS — **12 cases / 33 intended kills**, а не уже достигнутый результат. Статический review не заменяет этот gate, текущие P14/P15/P16, required CI, final same-checkout closure или installed/client acceptance. Frozen historical reports и P15 corpus/gold/scorer не изменяются; дополнительного разрешения на сеть, модели, ingestion вне объявленной fixture или mutation authority код не выдаёт.

# Project query intent: precheck перед сокращением classifier tests

## Результат

Добавлены один current contract control и одна адресная production mutation в существующий critical gate. `tests/docs/test_project_query_intent.py` целиком остаётся collected и byte-identical. Production intent/ranking/query code не меняется.

Исходный модуль — 6 функций / 32 cases. Пять classifier-only функций составляют 31 case. Шестая функция содержит содержательные ranking assertions и не входит в предполагаемое сокращение.

Фактический прежний результат `589a6366e33278fe542a0e3c971d2502e5e9f99f`: 27 FAIL / 5 PASS по compact JUnit reader https://github.com/Vanilla1999/DocAtlas/actions/runs/37975999319/job/113978187064. Сопоставление с source: 26 failures относятся к пяти classifier-only функциям; ещё один — к первой legacy предпосылке mixed ranking function. Это не результат нового precheck.

После доказанного precheck и отдельного review возможна замена 31 classifier cases одним control, то есть 32 → 2 cases для этой семьи с обязательным сохранением mixed ranking test. В текущем slice сокращения нет; добавляется один collected node.

## Действующий контракт

Непосредственно прочитаны:

- `project_query_intent.py`, blob `45de711d37bdce2574b9704eaa42e6ecc8278923`: `classify_project_query_intent` возвращает compatibility DTO `general`, все `broad/wants_*` flags false; free-form topic routing отсутствует.
- Тот же модуль: `mentions_docs_mcp_surface` распознаёт только буквальные case-sensitive публичные protocol names с границами слов. Этот положительный lexical signal нельзя обнулить вместе с legacy classifier.
- `documentation_query_plan.py`, blob `0cd20b1138f1a3a2740729677d9588414f2dcf32`: original question сохраняется как точный исполнимый запрос.
- `query_terms.py`, blob `5eecc570a8c3317fc762b9730a5c1643978f07ae`: typed literal identity и нормализованное представление различаются и сохраняются.
- `project_doc_ranking.py`, blob `b2cfa8385c2381cd93fc507a35e61b1cc1e33ca9`: finite membership, eligibility, qualified-query coverage и исходный retrieval score; тема вопроса не даёт source promotion.

Это не полный контракт answer/edit authorization. Соответствующие downstream guards остаются независимыми.

## Independent control

`tests/docs/test_project_query_intent_contract.py::test_current_project_intent_preserves_literals_and_never_infers_roles`:

1. Проверяет независимый frozen SHA-256 архива, фактический AST roster всех 6 функций / 32 cases и точное соответствие crosswalk. Исходные вопросы и assertions хранятся полностью; архив не импортируется и старые tests этим control не исполняются.
2. Из пяти classifier-only функций читает как data все 34 буквальных question arguments, включая вопросы внутри concept/incident проверок. Старые topic labels не используются как current oracle.
3. Сверяет current DTO с независимо написанным словарём из девяти полей, а не с ещё одним вызовом production constructor. Добавлены неизвестные EN/RU/Unicode/CRLF inputs.
4. Сохраняет raw question с whitespace, Unicode и CRLF; отдельно проверяет `Client.Open`, `get_docs_context`, `--dry-run`, `docs/Manual.md` с исходной идентичностью и правильными typed representations.
5. Проверяет positive literal detection всех трёх публичных protocol names и отрицательные prefix/suffix/uppercase/Unicode-word neighbors.
6. Выполняет реальный reranker над явно заданной finite fixture: допустимые source bodies сохраняются, результат не пустой, порядок разных base scores не зависит от перестановки входа, unlisted candidate со score 999 не попадает в результат. Source authority остаётся неопределённой; сам ranking не создаёт permission или factual proof.

Этот последний unit control не подменяет retrieval qualification, не доказывает original-query recall и не исправляет прежний semantic ranking.

## Сохранённый содержательный ranking guard

`test_documentation_files_do_not_imply_code_symbol_evidence` сохраняется целиком. В нём остаются исходные implementation/inventory questions, источники `docs/mcp-docs-server.md` и `docs/PROJECT_MAP.md`, полные source facts, исходные scores 0.92/0.55 и оба прежних ranking assertions.

Новый control дополнительно сверяет AST всей содержательной части этой рабочей функции, начиная с `implementation_question`, с frozen archive. Поэтому будущая classifier retirement не может тихо удалить или переписать её meaningful guard.

В имеющемся CI mixed test падает раньше ranking assertions. По source review нынешний reranker не должен угадывать semantic role из этих unqualified fake chunks. Исправление входной qualification/quality boundary требует отдельного evidence и review; данный precheck не объявляет этот guard успешно пройденным.

## Адресная production mutation

`project_query_intent_no_inferred_roles` заменяет единственный:

```python
return ProjectQueryIntent(name="general")
```

внутри `classify_project_query_intent` на настоящий DTO с `name="docs_mcp"`, `wants_docs_mcp=True` и `wants_code_symbols=True`.

Killer — новый current contract node; ожидается ровно один failure с первой строкой `AssertionError: critical_project_intent_no_inferred_roles`. Существующие проверки exact roster, failure count, absence of errors/skips и named assertion сохраняются. Import failure, collection crash или иной assertion не засчитываются.

Normal critical baseline расширяется с 29 до 30 cases; обычных mutants становится 8. Добавлены import-origin checks для intent API, query terms и ranking. Тело literal comparison не меняется; 702/82 и 51 mutations не приписываются этому intent API. Ранее доказанный alias guard тоже не считается доказательством classifier API.

## Identity, manifest и review

База чтения: `841e770e644dba369ab441ba2ec9f2a8807cac7f`.

- Исходный/архивный git blob: `73505df55c4533e2426c460f9b26ad8517179a5c`.
- Archive SHA-256: `28d1cd71c5c6981fa23228b14e93bb7b34a42834c9ffce4ac90d8b929752c727`.
- Frozen roster SHA-256: `fc5f914afdd9fb2458620b3a2486bfa3517fd14d74712f08cd068f28db7b8975`.
- Новый diagnostic node SHA-256: `e760e0aac46b4e2b54a8d168c1fe923e8b1d1f77e178920add41898908f9cb46`.

| Путь | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| `scripts/run_critical_mutation_gate.py` | `375018e23de41d8912d43a6ddc87b6fb8392a241` | `9dc4669bc37bcc06b68e182abe08cbad6778e67f` | 100755 |
| `tests/docs/test_project_query_intent_contract.py` | новый | `6a113106902ff0ce24ab7ef58f332f2c91401bad` | 100644 |
| `eval/task_level/contract_history/project_query_intent.json` | новый | `af69b43d49771697bbc266872105058e41ba77d7` | 100644 |
| `tests/diagnostic_labels.project_query_intent_contract.json` | новый | `e59db20d87993e9475132e8bb04e857338222eb9` | 100644 |
| `eval/task_level/contract_history/project_query_intent.py.txt` | новый | `73505df55c4533e2426c460f9b26ad8517179a5c` | 100644 |

Проведены source review текущего API и callers, статическая сверка шести function boundaries и parameter counts, проверка четырёх единственных gate anchors, единственного production mutation anchor и byte-identical literal comparison body. Никаких selector/threshold/skip/xfail changes нет. Старая diagnostic registration остаётся.

Локальные imports, AST/compile, pytest, server/provider calls не запускались. Новый Python control, его AST archive check и адресная mutation ещё должны пройти обычный CI на опубликованном SHA. Только после фактического baseline и named kill допустим отдельный reviewed retirement пяти classifier-only функций. Full acceptance остаётся отдельным gate.

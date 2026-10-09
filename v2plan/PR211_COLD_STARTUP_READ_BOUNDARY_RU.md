# PR #211: первый холодный member read без записи startup-служб

Статус: production slice для independent review; новый runtime результат ещё не получен.
Exact bases повторно сверены на `38da10d347ae2227eee6d1624db58dbf30938674`.

## Подтверждённый failure и причина

В обычном [CI run 37998331818 / advanced job 114049950632](https://github.com/Vanilla1999/DocAtlas/actions/runs/37998331818/job/114049950632)
recovery baseline дал 11 PASS / 1 FAIL / 0 ERROR.
У `closed_literal_context` первый public read `What does OrdersDraftStore do?` изменил только `store_sha256`:
`e3a6dd2903477da5fe182e8ec6f43969c8d411499b68cb3dfbec28fef3eee047` →
`d2f4ede7bcb63f399f1a2bc1e0b6fbea184be8663ac7793b0d8b3097d17a0059`.
Generation, исходный документ и catalog не изменились. Mutation gate обоснованно не засчитал baseline/kills.

Source trace подтверждает, что cold `LocalMemberService.materialize` создаёт обычный `LibraryDocsService`.
Его constructor пишет ancillary SQLite schema через `LibraryRegistry._ensure_schema` и `SQLiteDocsJobStore._migrate`;
tracker выполняет interrupt/prune, facade запускает resume.
Отдельно обнаружен startup cleanup: constructor library application eagerly создаёт `LibraryRefreshOps`,
который удаляет orphaned staging directories. Это не чтение документов.
Прежний `MemberReadStore` уже устранил writer initialization внутри lexical agent, но не эти facade constructors.

## Контракт construction и lifecycle

| Вход | Materialization | Разрешённое поведение |
| --- | --- | --- |
| Первый cold `get_docs_context`, `docs_status`, source continuation | `read_only_startup=True` | Current owned member SQL read, без registry/job migrations, interrupt/prune/resume или refresh cleanup |
| Explicit `prepare_docs` lifecycle | Обычный writable facade | Прежняя initialization, startup recovery и дальнейшие разрешённые write операции |
| Explicit confirmed member sync | Прежний cold member executor | Finite selected documents, catalog/hash/generation preconditions и atomic commit |
| Read после создания отдельного reader, затем writer | Сохранённый reader | Сохранены continuation references; SQL reader проверяет актуальное поколение на новом подключении |
| Read, когда writable facade был материализован раньше | Тот же существующий объект | Construction не повторяется; сохраняются current same-call observers/prepared lifecycle |

`read_only_startup` — opt-in для cold construction. Обычные constructors по умолчанию остаются writable.
Новые readonly registry/job dependencies используют именно `MemberReadStore._connect`, а не отдельный непроверенный путь:
owner, текущая schema/generation и snapshot проверяются прежде ancillary SQL.
SQLite остаётся `mode=ro`/`query_only`; значения store path или callback не берутся из model-visible evidence.
Случай custom injected registry/job tracker в таком construction отвергается.

Ancillary lookup возвращает пустой ledger только при точном отсутствии соответствующих имён в `sqlite_master`:
для registry — нет `doc_libraries`; для jobs — нет обеих `docs_jobs` и `docs_job_schema`.
Существующая таблица с missing columns, view под ожидаемым именем, половина job schema или неподдерживаемая version
не считаются пустыми. Нет `except OperationalError: return []` и нет repair при чтении.
Readonly write entry points отклоняются, включая job create/update/cancel до изменения in-memory state.

Fixture wrapper только передаёт startup selector и направляет observer attribute access в тот же facade,
который выберет настоящий public dispatcher. Он не materialize-ит writer для warming и не меняет source data.
Explicit `materialize()` остаётся доступным для подготовки.

## Компактные реальные controls

Все 35 существующих test functions / 116 expanded cases сохранены; усилены три существующих real-service Git варианта.
Первый настоящий public call проходит при обеих пустых facade caches, после снятого before fingerprint.
В этот момент forbidden hooks ловят SQL schema initialization, job interrupt/prune, orphan cleanup и resume.
Прежние actual source bytes, Unicode char/byte lineage, SQL child identity, Git read guards и database equality сохранены.

В том же control проверены empty unprovisioned ledgers и отказ readonly writes.
В варианте без Git обычный writable facade создаёт registry/job state;
последующий public confirmed member preparation меняет поколение, а исходный reader видит новые точные bytes и актуальные ledgers.
Четыре real SQLite forgeries проверяют missing registry column, missing job column, future job version и partial job schema:
они обязаны быть отклонены, а fingerprint после каждой попытки чтения остаётся неизменным.
Новых обычных test functions, parallel framework или runtime mocks вместо production return нет.

## Граница этого slice

Это исправление cold startup writer и текущего project member read.
`AgentIndexGateway.query_library/probe_library_requirements` по-прежнему используют отдельный library agent;
полную readonly гарантию для нового открытия library index этот slice не заявляет и не меняет acquisition/ranker.
Подготовленный P1.5 cached library fixture ранее имел state equality; это не доказательство отдельного cold library открытия.
Ни frozen questions/facts, ни qualification, ни recovery before-hash/equality/guards здесь не изменены.
Recovery scripts сейчас редактирует root отдельным согласованным slice.

## Exact manifest

| Файл | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| docmancer/docs/registry.py | 136a9eed2dd77ebc6af5c8da09b2268453505a47 | c3bf2e9a0b4e0f78ef8f90fa76c34db404182199 | 100644 |
| docmancer/docs/application/docs_job_service.py | 0afdc26e72a4a040ab59be16b638f5f65a5b41a1 | b64c68f60be592cdb51436f3f26620913bd509a6 | 100644 |
| docmancer/docs/service.py | 0c3815d7ae3de7f0e6e17d37b3446880bdb26701 | 728a7c62e46eebd19f65c90e86059db1bad788fa | 100644 |
| docmancer/docs/application/_library_docs_service_part01.py | a8fcafa6ee1cf262795f14e3fb6b2bea9eed3ba4 | aeb93b342af93012afa09d05e1e5aa5244e2f5c0 | 100644 |
| docmancer/mcp/_docs_server_part01.py | 4156c6faf99365f270377196498329f64c296ef8 | 9e6e57dfd786ad1665497524785db5fad093a439 | 100644 |
| eval/evidence_quality_v2/runtime.py | 153107026c725d9ee4ad10d1e4849a6956264300 | 73e5e30fe41394d2be33271a03d9e550bf6f4ae1 | 100644 |
| tests/test_mcp_delivery_member_transaction.py | 08eae1631ab465db9cec22933908e42f0a2ce95e | 45b3f7488361e2e66948ca812dcc7b139b6790cd | 100644 |

Нужны independent static review, обычный recovery baseline/mutation gate и current core controls на опубликованном SHA.
Локальные imports, pytest, AST и subprocesses не выполнялись. До фактического CI результата merge-readiness не заявляется.

## Actual CI на `1c6c2c8`: холодный read прошёл, fixture требует read accessor

В [run 38003248365 / advanced job 114066061733](https://github.com/Vanilla1999/DocAtlas/actions/runs/38003248365/job/114066061733)
на PR HEAD `1c6c2c8454cdd6fe797fe80e85f3b651aef01a0a` case `closed_literal_context` прошёл вместе с прежним cold first-read fingerprint guard.
GitHub исполнял merge checkout `64caa3caf213a6a67d44c92546660ef1ced23d87`; его parent — этот PR HEAD,
а tree в обоих случаях `8a544267409f0dbf3ab498dfa864c07b13cdfb73`.

Recovery baseline: **11 PASS / 0 FAIL / 1 ERROR**. `exact_document_recovery` остановился в setup:
`service.project_docs._agent_instance()` отклонён новым read facade с `PermissionError` до public call.
Mutation gate правильно отказался засчитывать evidence при негрин baseline; 12/18 пока не доказаны.

Узкая fixture migration заменяет только этот writer accessor на `service._read_agent_instance().store`.
Это именно store production fallback: `_FixtureService.__getattr__` выбирает сохранённый read facade;
`ProjectDocsService.facade` хранит этот же объект; `_project_docs_service_part03._exact_document_index_chunks` вызывается
с `self.facade._read_agent_instance()`, а `AgentIndexGateway.read_agent_instance` возвращает кешированный `_read_default_agent`.
Следовательно прежний forbidden `list_sections_for_embedding` hook установлен на тот же store,
который fallback использует для bounded `list_sections_for_source`. Это не переход к writer или обход запрета.

Сохранены query denial, full-scan denial, restoration, source/fact/generation assertions, все 12 case names,
код cold first-read before/after и все 18 production mutation definitions. Новые assertions или вызовы retrieval не добавлены.
Миграция ещё требует обычного CI; новые member transaction controls и весь acceptance отдельно не объявляются зелёными.

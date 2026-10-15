# PR #211: независимый review fixture member transaction

Дата: 2026-10-08. Reviewer: отдельный агент `membership_fixtures`, не автор
mutation slice. Сравнение с `df9b682fdd13d8f4d1c5bff6cc4bfc0286e5f8ce`.

**Вердикт: APPROVE для узкого test-fixture slice и обычного совместного CI.**
Blocking findings не обнаружены. Это статический code review, не runtime PASS,
не acceptance retrieval/admission и не разрешение merge/release.

## Проверенная версия

| Файл | Проверенный SHA256 |
|---|---|
| `tests/_fixture_member_transaction.py` | `87260abcf397eb4493d62e50a9d043942e185a905a4156287a705a5c36fd46fe` |
| `tests/test_named_document_context_integration.py` | `0ecdcbdf0ed96cb76c80af3fc8c7f357ee64f9aed2fa86977b1bc6341a082f5a` |
| `v2plan/PR211_MUTATION_FIXTURE_REVIEW_RU.md` | `b997e973c1b643923ee84e03970fcdf473ef00c5980f702adcecced20bdba051` |

Прочитаны полный новый helper, diff и исходные тела named-document tests,
использующие общий fixture внешние modules, а также реальные contracts:

- [`LocalMemberService`](../docmancer/mcp/_docs_server_part01.py);
- [`ProjectDocsService.sync_project_docs`](../docmancer/docs/application/_project_docs_service_part02.py);
- [`MemberTransaction`, `PinnedProject`, `execute_member_transaction`](../docmancer/docs/application/project_docs_member_transaction.py);
- [`MemberStoragePolicy`](../docmancer/core/member_storage_policy.py);
- [`SQLiteStore.upsert_project_members`](../docmancer/core/_sqlite_store_part01.py);
- [`LibraryDocsService`](../docmancer/docs/service.py).

Production и чужие tests этим review не редактировались. Единственный finding
по точности docstring передан автору и исправлен им до фиксации hashes выше.

## Consent, finite selection и storage

Helper получает список paths от автора fixture, а не извлекает разрешение
из catalog или prose. Call sites передают конечные создаваемые fixtures:
`paths` в общем helper, `(plan_path, "ARCHITECTURE.md")` и `(plan_path,)`
в самостоятельных tests. Directory/glob traversal и автоматическое
расширение списка members не добавлены.

`fixture_member_mutation` вычисляет hashes текущих test-owned catalog/document
bytes и catalog entries, формирует полное `sync_project_docs` request с
literal `confirm=True`. Он не патчит `MemberTransaction.parse`, hash checks,
`PinnedProject`, source bounds, owner checks или SQLite CAS. Создание fixture
является явным test-owned подготовительным действием; обычный read handler
не получает auto-consent и не вызывает этот helper.

Storage выбирается config объекта host fixture до обращения к project:
`tmp_path/home/mcp/members.db`, отдельно от `tmp_path/project`. Project config
не используется для перенаправления database. `LocalMemberService` сначала
остаётся cold; отказ от неподтверждённого legacy sync происходит до появления
home/database. В настоящем producer storage validation и descriptor/hash
preflight происходят до `initialize()`.

Материализация обычного `LibraryDocsService` выполняется после успешной
confirmed transaction и сохраняет тот же `MemberStoragePolicy`. Constructor
read facade может создавать свои обычные служебные данные в подготовленном
fixture store; assertion про отсутствие extraction directory относится
конкретно к mutation, до `materialize()`. Author report правильно ограничивает
это утверждение данным моментом lifecycle.

## Hash, identity и CAS

Проверены два независимых preconditions: source bytes и ожидаемое generation.
Helper не получает generation внутри `fixture_member_mutation`: caller обязан
передать `expected_generation_id`. Cold preparation использует `None` один раз;
обновление в integrity test использует явно сохранённый первый generation.
Нет автоматического refresh, retry, подавления отказа или подмены expected
generation фактическим новым значением.

Положительный helper проверяет статус настоящего commit, `member_upsert`,
отсутствие vector synchronization, точные counts, active generation, совпадение
набора generation sources с явным списком. Для каждого source проверяются
content bytes, content hash, catalog-entry hash, root identity и `project_file`.
SQL используется только для чтения результата; ручных INSERT/UPDATE seed,
подмены source metadata или внешнего database здесь нет.

В первом новом integrity test отказ вызывается отдельно для отсутствующего
mutation, false confirmation, неверных content/catalog/entry hashes,
отсутствующего generation, другой operation, другого storage и nonmember path.
После каждого loop-case проверяются cold state и сохранность обоих fixture
files. Затем тот же корректный исходный grant должен реально сохранить ровно
README, а не unselected file. Это исключает положительный результат от
постоянного отказа или пустой подготовки.

Во втором test stale content hash отклоняется при ещё правильном generation.
После явного свежего hash один выбранный source обновляется, generation
меняется, полный `sources` row другого source сохраняется. Повтор успешно
выполненного request отклоняется по generation CAS; helper не переиздаёт grant.
Снимки перечисленных source/generation tables до и после отказа совпадают.

Snapshot helper читает семь явно перечисленных tables. Это не полный снимок
всей SQLite database и не побайтовое сравнение файлов database/journal.
Такого более широкого доказательства для этого review не заявлено.

## Сохранение смысла прежних tests

Независимое stdlib AST сравнение подтвердило:

- Все **18** прежних top-level test functions присутствуют; их arguments и
  parameter decorators сохранены точно. Исходные **21 concrete JUnit cases**
  сохраняют identity.
- Добавлены ровно два test names:
  `test_named_document_fixture_requires_confirmed_hash_bound_members` и
  `test_named_document_fixture_cas_preserves_unselected_source`.
- В старом module было **112 Assert nodes**. Ровно два прежних setup assertions
  меняют AST: sync call без grant заменён проверкой `sync.status == "success"`
  результата настоящей confirmed transaction. Один находится в общем helper,
  другой — в single-fact test. Все прочие assertions сохранены.
- Все **110 read/content/assertion ASTs** внутри прежних test functions
  сохранены; fixture document texts, roles/authority и questions не подменены.
  Assertions про source selection, fidelity, missing facets, ambiguity,
  answer support и отсутствие edit authority остаются активными.
- Итог: **130 assertions** в named-document module и **20** в новом helper;
  module sizes — **753 и 105 строк**, оба ниже 1000.

Фактический эффект на retrieval expectations пока неизвестен. Старые
semantic/alias/output claims могут продолжить падать после устранения
PermissionError. Особенно отмечен отдельный legacy sync foreign project
в `test_foreign_project_same_path_never_enters_owned_context`: этот второй
вызов не мигрирован и не объявлен исправленным.

## Baseline и выполненные проверки

Самостоятельно прочитан сохранённый ledger финального исходного
[CI 37811010878, core Python 3.12](https://github.com/Vanilla1999/DocAtlas/actions/runs/37811010878/job/113427539519)
на HEAD `df9b682f`, merge checkout `4fe1bec2e96a211969676b7086e0d2e769f64981`.

В исходном ledger подтверждены:

| Набор | Исходный выполненный результат |
|---|---:|
| `test_named_document_context_integration` | 21 FAIL |
| Все шесть затронутых fixture families, exact mutation PermissionError | 51 FAIL |
| `test_mcp_delivery_member_transaction` | 109 PASS |
| `test_mcp_trusted_storage_lifecycle` | 30 PASS |
| `test_evidence_quality_v2_fixture_runtime` | 9 PASS |

51 affected failure не равен 51 обещанному исправлению. Baseline PASS других
member suites подтверждает существующий исполняемый путь, но не заменяет CI
нового helper и двух новых integrity tests.

Reviewer выполнил AST parse/compile без imports, сравнение assertions/names/
decorators, чтение source и JUnit, проверку SHA256 и `git diff --check`: PASS.
Repository imports, pytest, установки пакетов, subprocess fixtures, providers
и clients локально не запускались. Результат новой runtime версии: **NOT RUN**.

## Finding, исправленный до approval

Первоначальный docstring `fixture_member_state` обещал все mutation-bearing
rows, хотя перечислял семь tables и не включал, например, `parent_sections`
и `retrieval_parents`. Автор сузил описание до:
`Snapshot selected source and generation rows for rejection controls.`

Независимо проверено, что это единственное изменение helper между исходным
review hash `9d5d0169292f420fd09469ab38552ac6dc703226218a0509d7c6637476758e2f`
и финальным hash `87260abcf397eb4493d62e50a9d043942e185a905a4156287a705a5c36fd46fe`.
Дополнительных test/production изменений ради замечания не потребовалось.

После approval следующий gate — обычный совместный CI с двумя новыми cases,
сравнением старого roster и проверкой конкретных новых исходов. Gates,
retrieval/admission ограничения и merge readiness остаются отдельными.

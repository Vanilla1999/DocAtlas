# PR211: descriptor-bound mtime для текущего member route

Base: `04ff1dda57efb5236d7b3577d4e2736b2820df5b`. Узкий operational metadata fix
и два fixture successors. Runtime на этих bytes **NOT RUN**; выводы ниже основаны
на source/AST review, не на новом PASS.

## Дефект и текущий контракт

`member_document` записывает content/catalog hashes, project identity и scope,
но не `project_doc_mtime_ns`. `project_docs_state.py` читает это поле в indexed
mtime; `project_state.py::partition_project_doc_state` сравнивает его с настоящим
candidate mtime. Поэтому у свежего документа возникает ложный metadata drift,
а `ProjectDocsChunk.mtime_ns` отсутствует.

Сама по себе эта потеря **не делает документ stale**. Текущий stale contract
проверяет content hash, catalog hash и chunking configuration. Mtime служит
отдельной диагностической metadata; эти условия и их порядок не меняются.
В actual04ff два выбранных tests ещё останавливаются раньше, на legacy ingestion
PermissionError. Runtime reproduction исправленного metadata route ожидается в CI.

## Изменение production

Только `_execute_pinned`: после построения Document присваивается
`project_doc_mtime_ns = pinned.versions[pinned.members[member.path]][1]`.
`PinnedProject._version` хранит `(size, mtime_ns, ctime_ns)` уже открытого
file descriptor; selected path ранее bound, bounded-read и recheck выполнены.
Последующие descriptor rechecks перед storage initialization/upsert сохраняются.
Новое присваивание не выполняет pathname I/O и не принимает caller mtime.

Pure `member_document`, mutation wire fields, parser validation, root identity,
source/catalog SHA, source boundaries, read limits/deadlines, no-follow/hardlink
checks, storage policy, consent и generation CAS остаются прежними. Retrieval,
qualification/admission, source selection, authority, output schemas и gates
этот slice не меняет. Metadata не становится доказательством source freshness.

## Два существующих tests

| Concrete node | Сохраняемый контракт и дополнительные controls |
|---|---|
| `tests/test_docs_service.py::test_inspect_project_docs_does_not_mark_mtime_only_change_stale` | Прежние README bytes, os.utime и три финальные assertions сохраняются. До touch: реальный готовый member, точный сохранённый mtime и отсутствие drift. После touch: hash прежний, stored mtime прежний, current mtime изменился; state семи source/generation таблиц не изменился от чтения. |
| `tests/test_docs_service_part03.py::test_get_project_docs_returns_scoped_docs_result` | Прежние вопрос `ProjectAnswer ADR`, README text и все 13 scoped-result assertions, включая non-null mtime, сохраняются. Дополнительно проверяется точное равенство mtime исходному подготовленному файлу. |

Оба fixtures явно объявляют только существующий README: overview/project,
**supporting**, active/track, без roots/code_files. Supporting — текущий default
catalog attribution (`project_docs_catalog.py`); это не новая instruction authority.
Затем существующий `indexed_fixture_member_service` выполняет настоящий cold
confirmed transaction с exact hashes, CAS None, private host store и проверкой
nonempty persisted source bindings. Legacy ingestion удаляется только из этих
двух nodes. После os.utime повторного sync нет.

## Idempotence и границы

SQLite member upsert сравнивает полные metadata dictionaries. Первая явно
подтверждённая синхронизация старой записи без mtime или синхронизация после
mtime-only touch может обновить metadata, создать новую generation и derived
writes. Это действительный metadata update внутри явного mutation/CAS, не
автоматический repair при чтении. Последующий repeat без изменений должен снова
дать zero writes. Source identity/content hash не зависят от mtime.

Риск подтверждается последующим обычным full CI, включая существующие
member/descriptor/CAS/security tests и настоящие installed SDK unchanged-repeat
checks. Их assertions и guards не ослабляются. Предыдущие SDK PASS на04ff не
переносятся на новый production source. Старые записи при одном чтении не
переписываются; данный slice не вводит фоновую migration.

## Статическая проверка

- AST parse и compile без исполнения/import repository code выполнены.
- Во всех трёх модулях изменён только указанный function body. Остальные
  functions/classes AST-exact относительно04ff; signatures/decorators прежние.
- Все исходные test assert AST сохранены, имена/collection nodes не меняются.
- `git diff --check` PASS. Модули 750/794/364 строки, действующий1000-line gate
  не меняется. Новый helper или diagnostic label inventory не требуется.
- Подробный source inventory: `pr211-acceptance-artifacts/04ff1dd-mtime-source-checks.json`.

| File | SHA256 |
|---|---|
| `docmancer/docs/application/project_docs_member_transaction.py` | `e255652379cefb73ce393f2f7e7a1996672e54cda66f608c359ff288c053a2b6` |
| `tests/test_docs_service.py` | `15de8ad7d6ced8dd8c44b90ba9d12c7aebc56a00b2fddc71279becf764842268` |
| `tests/test_docs_service_part03.py` | `3f763853a94c831db2a7d83f0e115d1f9cca7c7ec26031ce58044b3e10b0af01` |

`test_docs_service.py` также имеет отдельные fixture edits в другом worktree.
Перед publication требуется интеграционная AST сверка двух непересекающихся
slices и отдельный итоговый source hash. Этот report описывает только свои bytes.

## Исправление review до publication

Дополнительный независимый source review выявил обязательное непустое catalog
`description` в `_validated_entry`. В обоих новых README entries добавлено
одинаковое `Authored project overview fixture.`. Это не source text, вопрос или
semantic rewrite; остальные entry values прежние. Верхняя hash table обновлена
на corrected bytes. Прежний review требует повторной сверки этой поправки.

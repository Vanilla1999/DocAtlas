# Независимый review descriptor-bound member mtime

Вердикт: **APPROVE corrected bytes** на базе `04ff1dda57efb5236d7b3577d4e2736b2820df5b`. Прежний APPROVE без обязательного catalog description был отозван; повторный review ниже закрывает конкретный finding. Runtime нового production source **NOT RUN**.

| Файл | SHA256 |
|---|---|
| `docmancer/docs/application/project_docs_member_transaction.py` | `e255652379cefb73ce393f2f7e7a1996672e54cda66f608c359ff288c053a2b6` |
| `tests/test_docs_service.py` | `15de8ad7d6ced8dd8c44b90ba9d12c7aebc56a00b2fddc71279becf764842268` |
| `tests/test_docs_service_part03.py` | `3f763853a94c831db2a7d83f0e115d1f9cca7c7ec26031ce58044b3e10b0af01` |
| `v2plan/PR211_MEMBER_MTIME_REVIEW_RU.md` | `e0f8d57a5ca20dca2d6bdcb9832e5ec34e07ec32803cfa6b573ac6222cf41acc` |

Полный diff, текущие producer/consumer contracts и существующие descriptor/member security controls прочитаны независимо. Source inventory `04ff1dd-mtime-source-checks.json` имеет SHA256 `a7c302493bf07dcf52942f573d67cb17f7cd73f705fa36762af584ecb42c72ce`; заявленные hashes и AST boundaries независимо подтверждены.

Production меняет только одно прежнее `documents.append(member_document(...))` на создание того же Document, присваивание descriptor-bound metadata и append. Обратная замена этих трёх statements исходным append даёт AST-exact `_execute_pinned`; всё остальное в module AST неизменно. `member_document`, parser и три wire fields не меняются.

`pinned.versions[pinned.members[member.path]][1]` — mtime из `(size, mtime_ns, ctime_ns)` уже открытого selected descriptor. Он связан с теми же bounded-read bytes, hash/catalog preconditions и rechecks. После присваивания остаются оба recheck перед initialization/upsert. Нового pathname I/O, caller mtime, discovery, authority, source grants или обхода storage/CAS нет. Timestamp — reporting metadata, не замена content/catalog hashes и не доказательство permission или freshness.

Consumer defect подтверждён source: indexed state и `ProjectDocsChunk` читают отсутствовавший `project_doc_mtime_ns`; partition сравнивает candidate mtime с indexed mtime. Изменение исправляет отсутствующую metadata. Mtime drift по-прежнему отделён от stale: stale определяется content/catalog hashes и chunking configuration. Deferred retrieval/qualification/admission slice не меняет.

Correction review: независимо прочитаны весь `read_project_docs_catalog`, `_validated_entry`, literal-path predicate и constants. В обоих entries теперь exact `description: Authored project overview fixture.` (34 символа, одна строка, предел 512). Schema 1, единственный существующий regular `.md` path README, overview/project без module_path, supporting/active/track допустимы; отсутствующие roots/code_files имеют разрешённые пустые defaults. Неизвестных/duplicate fields нет. README создаётся прежним write в новом fixture root до catalog/helper. Отмена ровно одной добавленной description-строки в каждом author-файле восстанавливает прежние reviewed hashes: остальные statements/inputs/assertions не менялись. Helper вычисляет entry hash из исправленного catalog, поэтому correction не оставляет прежний hash и не обходит binding. Первоначальная omission была ошибкой предыдущего review и corrected до publication; исходные source bytes/questions не менялись.

Оба existing tests используют literal README-only catalog с текущим default `supporting`, существующий cold confirmed helper, exact source/catalog hashes, host-selected store и generation CAS. Исходные README bytes и вопрос `ProjectAnswer ADR` прежние; fake result/metadata не вводятся.

- `test_inspect_project_docs_does_not_mark_mtime_only_change_stale`: все **3** старых assert AST сохранены, теперь **11**. До touch доказаны готовность, отсутствие stale, exact stored mtime и отсутствие drift. `.get("metadata_drift_reasons", []) == []` корректен: producer добавляет optional key только при наличии drift. После исходного `os.utime` сохранены ready/not-stale/drift assertions и проверены прежние content hash и stored mtime, новое current mtime и точное равенство state семи source/generation таблиц. **После touch sync нет**; этот тест не исправляет собственный indexed timestamp записью.
- `test_get_project_docs_returns_scoped_docs_result`: все **13** старых assert AST сохранены, теперь **14**. Non-null mtime и все scoped/content/heading/next-actions проверки прежние; дополнительно проверяется точное равенство настоящему filesystem mtime подготовленного README.

Независимая AST проверка: изменены только эти две test functions, signatures/decorators прежние, module AST вне них exact. Сохранены **28 + 24** base test names. Модули имеют **364 / 750 / 794** строки; `git diff --check` PASS. Исполнение repository code не выполнялось.

Author report честно описывает generation consequence: SQLite member writer сравнивает полные metadata dictionaries. Первая явно подтверждённая sync старой записи без mtime либо sync после mtime-only touch может создать новую generation/derived writes; дальнейший неизменённый repeat должен снова быть zero-write. Ownership/source identity/content hash не расширяются, автоматического read repair нет. Существующий pure in-memory repeat test сам по себе не доказывает descriptor route; последующий обычный CI должен сохранить member/descriptor/CAS/security assertions и actual installed SDK repeat checks.

В actual04ff оба выбранных nodes ещё падали на legacy ingestion PermissionError. Поэтому этот review подтверждает контракт и implementation scope, но не заявляет runtime PASS. Другие fixture edits `test_docs_service.py` требуют отдельной интеграционной AST сверки и нового итогового hash; APPROVE относится только к bytes таблицы выше. Изменён только этот независимый report.

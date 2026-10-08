# PR211: authored member setup для шести существующих read tests

База: `04ff1dda57efb5236d7b3577d4e2736b2820df5b`. Отдельная ветка
`implementation/pr211-member-read-fixtures`; изменены только шесть тел тестов
в четырёх файлах. Это author review, не результат runtime acceptance.

В сохранённом core 3.12 JUnit для 04ff все шесть nodes падают при подготовке:
два на `sync_project_docs`, четыре на `ingest_project_docs`, до своих read guards.
Причина — отсутствие explicit mutation grant и validated member transaction.
Членство в catalog само не разрешает запись. Эти tests проверяют module routing,
изоляцию проектов и stale reads, а не прежнюю автоматическую ingestion lifecycle.

## Область и сохранённые guards

| Существующий node | Setup / положительный контроль | Assertions: до → после |
| --- | --- | --- |
| `tests/docs/test_module_docs_manifest_e2e.py::test_two_module_docs_manifest_sync_filter_and_public_mcp` | Cold confirmed transaction ровно для прежних README и двух module docs. Существующие непустые module reads, path/module filters и public MCP проверки сохранены. | 11 → 11 |
| `tests/evidence_quality_v2/test_readme_neutral_context.py::test_foreign_project_same_path_never_enters_owned_context` | Один captured active generation для foreign README; после real upsert обе owned/foreign generation rows обязаны существовать, иметь исходные bytes/hash и разные владельцы. | 3 → 20 |
| `tests/test_docs_service.py::test_inspect_project_docs_reports_indexed_and_stale_sources` | Explicit authored README catalog и cold member transaction. Существующий ready/indexed positive до редактирования и весь stale/preflight tail сохранены. | 16 → 16 |
| `tests/test_docs_service.py::test_get_project_docs_never_returns_hash_mismatched_stale_content` | Перед прежним изменением файла — непустой read `OriginalNeedle` с исходными tokens/limit и bindings. После изменения прежние empty-results/hash-mismatch guards. | 4 → 9 |
| `tests/test_docs_service_part04.py::test_get_project_docs_reports_stale_project_docs` | До изменения — непустой read `ProjectStaleAnswer`, tokens=1200/limit=3. Прежние stale status, confirmation, next action и path guards сохранены. | 11 → 16 |
| `tests/test_docs_service_part04.py::test_get_project_context_requires_preflight_for_stale_project_docs` | До изменения — raw project-doc read того же `ProjectStaleContextAnswer`, tokens=1200/limit=3. Затем прежний context call и полный stale/answer-unavailable/confirmation tail. | 6 → 11 |

Три новых positive reads проверяют непустые chunks, только `README.md`, точный
абсолютный source, content hash исходных bytes и наличие исходного marker.
Они не требуют новой answer authority или qualification. В context case positive
доказывает наличие читаемого исходного документа; прежний context failure остаётся
проверкой preflight после изменения bytes.

В foreign case единственный старый assert, изменившийся по AST, — inline
`sync_project_docs(...).status == 'success'`: теперь это `result.status == 'success'`
после вызова с полным mutation. Два исходных отрицательных read/integrity guards
сохранены дословно по AST. Дополнительно проверяются `member_upsert`, отсутствие
vector request, ровно один new member, zero changed/deleted, новая committed
generation, trusted policy validation и точные source rows. Для обеих rows
сверяются content bytes/hash, catalog-entry hash, project identity/path,
`README.md` и source class. Catalog у foreign по-прежнему копируется из owned
fixture: одинаковый entry hash при разных root-bound project identities ожидаем.

## Текущий контракт и происхождение inputs

Переиспользован неизменённый `tests/_fixture_member_transaction.py`:

- `cold_fixture_member_service` выбирает disposable host storage вне проекта и
  создаёт cold `LocalMemberService` без eager read service.
- `fixture_member_mutation` получает конечный tuple путей от вызывающего test,
  а не glob/discovery. Он передаёт explicit operation/confirm/storage path,
  SHA256 catalog bytes, content SHA256, catalog-entry hashes и предоставленный CAS.
- `indexed_fixture_member_service` исполняет реальный cold transaction с CAS=None,
  проверяет generation, exact member source set, bytes/hashes/catalog binding,
  project ownership, no source deletion, no vectors/extraction; только затем
  materialize обычный read service.

Production grounding:

1. `project_docs_member_transaction.py:41–82,99–121,275–342` проверяет полный
   mutation, matching operation/consent, literal members, hashes, trusted storage,
   active generation, source boundary и finite explicit catalog. Никакого bypass
   этих проверок в тестах нет.
2. `core/_sqlite_store_part01.py:297–331,385–450` повторно проверяет CAS внутри
   `BEGIN IMMEDIATE`, immutable ownership и compatible lexical generation.
   `recreate=False` сохраняет foreign/owned rows; `sources_deleted=0` проверяется.
   Warm foreign mutation получает generation один раз до записи; refresh/retry нет.
3. `project_docs_catalog.py:319–321,347–350` задаёт defaults
   supporting/active/track и разрешает overview только в project scope.
   Четыре B fixtures теперь явно авторствуют один такой README entry;
   `roots: []`, `code_files: []`. `supporting` не повышает прежнюю default
   attribution до source_of_truth. `overview` — authored роль fixtures,
   а не вывод роли из имени файла или текста.
4. `domain/project_state.py:200–249` отделяет hash/catalog staleness от mtime drift
   и требует catalog-bound overview. `project_docs_service_part03.py:753–757,808–841`
   связывает raw read с текущим content hash и переносит exact source/path/hash
   в возвращаемые chunks. Прежние changed-byte/stale guards поэтому остаются
   проверкой актуального контракта.

В A сохранены все исходные document/catalog write calls и bytes. В B исходные
README texts/изменения, вопросы и лимиты не меняются; добавляется только конечный
catalog для authored fixture membership. После изменения README нет reindex/sync,
поэтому stale guards не скрываются повторной подготовкой.

## Статическая проверка и frozen hashes

Проверено только stdlib AST/JSON/hash и `git diff --check`; repository imports,
pytest, providers, installs и новые runtime subprocesses не запускались.
Нужен обычный CI на итоговом опубликованном SHA; шесть будущих PASS не заявляются.

AST comparison с exact base подтверждает:

- Изменены только перечисленные шесть function bodies; module-level AST,
  остальные functions, signatures/decorators и parameter rosters идентичны.
- Сохранены 50 из 51 исходных asserts по точному AST; один success assert имеет
  описанный successor. Всего теперь 83 asserts, без удаления отрицательных guards.
- Все original non-setup statements сохраняются в исходном порядке; исходные
  document write calls и read calls также сохранены по AST.
- 73 base node IDs четырёх модулей не изменились. Hashes roster совпадают со всеми
  соответствующими `tests/diagnostic_labels*.json`, включая extension
  `diagnostic_labels.readme_neutral.json`. Manifest edits не требуются.

| Файл | Строк | SHA256 |
| --- | ---: | --- |
| `tests/docs/test_module_docs_manifest_e2e.py` | 130 | `03ab60949fbb467487e82257ad0614eb641b892e77f564bd16dfc1e54721ad4c` |
| `tests/evidence_quality_v2/test_readme_neutral_context.py` | 159 | `7334d6493b1273fd4724cca8b27ac6674b4927b29e3d52df95c9b7dae8c9f95c` |
| `tests/test_docs_service.py` | 768 | `46864d74480a24869130d6d3083991de01a1aa949b93f1d88f5ae3e835a9f00b` |
| `tests/test_docs_service_part04.py` | 775 | `d8df782d1e2356c3ad64d3ee1800f5cce36eb7206e52fad4651657dae0220e95` |

Неизменённый helper SHA256:
`87260abcf397eb4493d62e50a9d043942e185a905a4156287a705a5c36fd46fe`.
Все четыре test modules остаются ниже 1000 строк.

Подробный scratch audit: `pr211-acceptance-artifacts/04ff1dd-member-read-fixture-ast-audit.json`,
SHA256 `788438a811115a669ae4d6c95fe9df276911cd01791c80cb1d22f810f4a6c7c3`.
В нём individual function AST hashes, base/source hashes, manifests и counts.

Production, shared helpers, retrieval/admission, semantic gold, authority flags,
workflow/gates, vector/idempotence/auto-prune/orphan/mtime tests не изменены.

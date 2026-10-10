# PR #211: provisional перенос committed lineage в project context DTO

Статус: подготовлено для independent review; публикация и runtime acceptance pending.
Это отдельный copy-only production slice. P1.5 oracle/source-class migration сюда не входит.

## Основание из source

На `c1e058cb51072f02620329000e2d68706a96bd67`:

1. `core/_sqlite_store_part02.py` строит child_metadata из actual structured child:
   source_identity, source_content_hash, char_span, byte_span и line_span.
   Source hash происходит из исходных document bytes; display hash относится к child window.
2. `_project_docs_service_part03.py` сохраняет эту metadata в ProjectDocsChunk при проверке current catalog/hash.
3. `project_context_pack` в `_project_context_service_shared.py` создаёт context DTO с source_class=project_doc,
   но прежде пропускал source_identity/source_content_hash и byte_span при переносе в top-level поля.

Actual diagnostics на `0855fb491ec388100cce92e57fe64b889c4cd3e0` уже прочитаны:
[run 37996655934 / job 114044350172](https://github.com/Vanilla1999/DocAtlas/actions/runs/37996655934/job/114044350172).
И canonical-policy, и implementation-fact source доставляют полный frozen факт.
У каждой найден ровно один committed child того же пути, stable id и generation; совпадают все сравниваемые поля, кроме ровно четырёх отсутствующих в snapshot:
source_identity, source_content_hash, byte_start и byte_end.
Actual snapshot.source_class=project_doc, stored.source_class=project_file; project identity, scope и authority совпадают.

Общий P1.5 результат ещё 2/7, verified facts 0/6, errors 0, oracle controls 6/6; source_integrity не позволяет зачесть эти два факта.
В пяти failed cases preparation_errors/authority_errors/state_differences пусты.
Artifact `11647437442`, 30762 bytes; ZIP SHA-256 `55de2ce5073898cc40d39ac6c5f98a262d571b3360b7bd246804acc89fe0a703`.
Таким образом, потеря четырёх полей подтверждена actual observation, а не только чтением кода.
P1.5 oracle всё ещё требует отдельно обоснованного контракта представления source class.

## Production изменение

`project_context_pack` дополнительно переносит source_identity и source_content_hash из уже существующего child metadata.
Byte span переносится как byte_start/byte_end только для пары настоящих int с неотрицательным упорядоченным диапазоном.
Отсутствующие/неправильные поля не синтезируются из отображаемой цитаты или предположений о source.

Source_class context DTO остаётся project_doc. Stored source type остаётся отдельным project_file.
Existing ownership, scope, catalog/hash/generation, trust, coverage, authority и projection решения не изменены.
Новых SQL reads, schema writes, retrieval calls, source opens, общей agent/session настройки нет.

Это перенос provenance через существующую границу DTO; он сам по себе не даёт query/answer/edit credit
и не устраняет отдельную проверку source_class в P1.5 oracle.

## Контроль в существующих трёх real-service cases

Изменена только `test_real_service_retrieves_committed_fixture_member_bytes`.
Все 35 test function names и их decorators сохранены; прежние 116 expanded cases остаются.
Новых обычных test functions или параметров нет.

- В README heading добавлены Ω и combining accent; исходный полезный факт
  `The command that starts the Docs MCP server is doc-atlas mcp docs-serve` сохранён с прежними backticks.
- В каждом из существующих вариантов none/repository/worktree_marker выполняется настоящий публичный context read.
- Observational wrapper вызывает настоящий model-visible validator и сохраняет его authoritative snapshot.
- Read-only SQL существующего MemberReadStore сопоставляет source с одним committed child и parent по active generation, stable id и canonical path.
- Независимо проверяются source identity, parent, raw source SHA-256, display hash/text, char/byte/line coordinates и публичная цитата.
- Unicode требует фактически разных byte_end и char_end и обнаруживает ошибочную подстановку character offsets.
- Прежние file/storage fingerprint, no schema initialization, Git-boundary, read-only SQL и explicit writable-ingest проверки остаются.

Raw SHA вычисляется от созданного README/protocol file; ожидаемая lineage читается из actual committed SQLite rows.
Product DTO не используется для построения собственного expected result.

## Exact manifest

| Файл | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| docmancer/docs/application/_project_context_service_shared.py | 870d502ba0fe7ae3cb02a8c7a62a9ac2f72c5e01 | f08b6327719fb14e6d93b143beb1150cf2cd4770 | 100644 |
| tests/test_mcp_delivery_member_transaction.py | 0a654d04f23e4ecd55eb69ab9b48546ee5e117b5 | 08eae1631ab465db9cec22933908e42f0a2ce95e | 100644 |

## Что ещё неизвестно

Новые public reads во всех трёх Git fixtures и snapshot equality assertions пока не исполнялись.
Общий контракт расширенных/перепроецированных source windows этим коротким fixture не доказывается.
Actual P1.5 field log подтвердил четыре missing fields до handoff; следующий job должен показать, какие несовпадения исчезнут после изменения.
Source-class oracle и lineage rules для transformed windows требуют отдельного обоснования;
их нельзя исправлять простой подстановкой фактического значения.

Independent review обязателен до публикации; после него нужны exact three real-service node PASS и сохранённые member-module gates на конечном SHA.
Локальные imports, pytest и runtime/subprocesses не запускались.

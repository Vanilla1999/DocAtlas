# PR #211: два домена хешей в native read-presentation контроле

## Фактический сигнал и граница вывода

На опубликованном HEAD `d76f6ab85e12f482ad6bec1d43040899f4b0a532`
(slice 126) acceptance reader job `114129755653` в
[проверках этого коммита](https://github.com/Vanilla1999/DocAtlas/commit/d76f6ab85e12f482ad6bec1d43040899f4b0a532/checks)
показал падение
`test_real_service_retrieves_committed_fixture_member_bytes[none]`
на `critical_project_read_acquired_qualified`.
Общий critical baseline: 59 случаев, 58 PASS, 1 FAIL. Новый mutation proof
после неуспешного baseline не заявляется.

Этот guard используется и для общего набора acquired windows, и для проверки
каждого окна. Полученный краткий traceback сам по себе не выделяет отдельный
ложный operand. Два несовместимых ожидания формата хеша ниже подтверждены
текущими производителями по исходникам; это не подмена фактического runtime
значения и не утверждение, что остальных причин падения нет.

## Текущий контракт производителя

| Поле | Источник | Ожидаемый формат |
|---|---|---|
| `ProjectDocsChunk.content_hash` | `member_document` записывает `project_doc_content_hash`; reader копирует его в DTO | `sha256:` + SHA-256 полного исходного файла |
| `context_pack[*]._source_snapshot_sha256` | `project_context_pack` копирует `item.content_hash` | тот же префиксный хеш полного файла |
| SQL parent `source_content_hash` | committed parent source bytes | 64 шестнадцатеричных символа без префикса |
| SQL child / DTO `display_content_hash` | точные байты отображаемого окна | 64 символа без префикса |
| public snapshot `source_content_hash` | сохранённый committed source hash | 64 символа без префикса |

Точные owning blobs:

- `docmancer/docs/application/project_docs_member_transaction.py`,
  `18e979c12769662c3a69376ed1c52a5f06cb6378`: `member_document`
  формирует `"project_doc_content_hash": "sha256:" + member.content_sha256`.
- `docmancer/docs/application/_project_docs_service_part03.py`,
  `94fe9ee6629d14034d337fae879272c5b6d16a64`: успешный
  `ProjectDocsChunk` получает этот metadata field без преобразования.
- `docmancer/docs/application/_project_context_service_shared.py`,
  `f08b6327719fb14e6d93b143beb1150cf2cd4770`:
  `"_source_snapshot_sha256": item.content_hash`.

## Узкая коррекция фикстуры

В `eval/agent_developer_v1/project_read_presentation_controls.py`
изменены только два сравнения:

1. Хеш файла в member DTO сравнивается с
   `"sha256:" + digest(documents[row.path])`.
2. Хеш файла в ProjectContext / Unified pack сравнивается с
   `"sha256:" + child["committed_source_content_hash"]`.

Эталон по-прежнему вычисляется из независимых literal fixture bytes и реального
committed SQL parent. Форматы не нормализуются через удаление префикса;
два варианта записи не принимаются одновременно. Проверки raw SQL хешей,
window SHA, public snapshot, точных Unicode bytes/spans, владельца, поколения,
scope, full fact, immutable state, 24 acquired windows, bounded control view
и operational veto остаются побайтно прежними.

Новых чтений, поисков, preparation calls или обычных pytest функций нет.
Production, runner и ожидаемые mutation guards не меняются.

## Exact manifest и проверка

| Путь | Mode | Base → proposed blob |
|---|---|---|
| `eval/agent_developer_v1/project_read_presentation_controls.py` | `100644` | `6cee024ec37691e919c1ccfa636c58cdd77f8f87` → `cb8bb289c5e7ce5b170011beffc33213c326ad69` |
| `v2plan/pr211-execution/PROJECT_READ_HASH_DOMAINS_RU.md` | `100644` | новый документ |

Обе замены имеют единственный anchor; обратное применение восстанавливает
исходный helper побайтно. Проверка здесь статическая, Python / pytest не
исполнялись. Новый совместный baseline и intended mutation kills остаются
PENDING до обычного PR CI на опубликованном конечном SHA.

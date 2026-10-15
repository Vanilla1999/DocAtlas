# PR #211: raw library provenance в P15 capture

Статус: узкая capture/oracle migration; новое runtime evidence ещё не получено.
Base: `1c6c2c8454cdd6fe797fe80e85f3b651aef01a0a`.

## Два разных расхождения

[Actual P15 job](https://github.com/Vanilla1999/DocAtlas/actions/runs/38003248308/job/114066060666):
**4/7 cases**, **2/6 complete facts**, **6/6 self-controls** на merge checkout
`64caa3caf213a6a67d44c92546660ef1ced23d87`.
Dependency fact найден и полностью доставлен. Source integrity сохраняет FAIL.

1. Реальный producer defect: при втором add SQL generation скопированного child обновлялся, metadata generation оставался старым.
   Это исправляется отдельно в [generation slice](PR211_COPIED_CHILD_GENERATION_RU.md).
2. P15 observer сохранял только top-level lineage. Канонический library candidate уже содержит остальные поля во вложенной metadata.
   Их отсутствие в отчёте нельзя объявлять production snapshot loss.

Новый observer не исправляет старую generation и не подставляет данные из подготовленного child.
Даже после capture migration старое противоречивое поколение обязано провалить child binding.

## Текущий контракт и источники

`docmancer/docs/application/_library_docs_service_part03.py`,
blob `07db6295be98e234c872f7370a9bcee37b0056f5`:
- selected candidate сохраняет исходную metadata;
- stable/parent ID, display hash, resolved version, exactness и authority дополнительно присутствуют сверху;
- metadata несёт generation, source identity/hash, library/canonical IDs, scope/class и packed char/byte/line spans;
- metadata `content_hash` — hash исходного display text; `version` — текущая resolved version.

`model_visible_projection.py`, blob `dfde451b4af3474bcc3225bcc74e2aa0f62c1772`,
использует `candidate.original`.
`_model_visible_docs_support.py`, blob `dd6795d83c8d863b12dd5e7d9ebe0712a19b2549`,
сохраняет original в `source` snapshot entry.
Таким образом nested metadata доступна в том же настоящем snapshot; дополнительного retrieval/store/resolver вызова не требуется.

## Что меняется

Runtime использует один `capture_source_binding` и сохраняет:
- `lineage` — raw top-level whitelisted fields;
- `metadata_lineage` — raw whitelisted поля original metadata, если metadata присутствует;
- прежние candidate hash material и exact projected source.

Словари не сливаются при capture. Явные null/false/list вместо metadata сохраняются и затем отклоняются.
Версии, hashes и coordinates не выводятся из gold, prepared rows или ожидаемого ответа.

Library-only oracle:
- сохраняет каждый present top↔nested конфликт как ошибку;
- проверяет конкретные DTO соответствия `version/resolved_version` и `content_hash/display_content_hash`;
- проверяет все present packed/scalar координаты: обе границы, ровно два integer значения, допустимый порядок, без bool/float/string;
- отвергает недостающий span и любой packed↔scalar конфликт;
- принимает documented boolean / SQLite integer metadata exactness; top-level candidate flag остаётся строго boolean;
- после чтения DTO выполняет прежние точные library/version/scope/class и committed child проверки, включая path, stable ID, generation, parent, source/display hashes, body и все spans.

Противоречие не превращается в отсутствие поля и не может быть перекрыто более удобным значением.
Project top-level interpretation, same-call projected source, frozen body/hash checks, registry/job/HTTP grants и no-write/authority checks сохранены.

В crosswalk добавлено только описание `library_source_representation`.
Удаление этого поля побайтно восстанавливает исходный JSON; все семь case entries и 13 source mappings прежние.
Frozen **7 questions / 13 candidates / 6 full facts / 2 negatives**, historical report и quality thresholds не меняются.

Runner печатает raw metadata через прежний body-free formatter.
Существующее сравнение top-level rows явно подписано как `raw_top_level_lineage_only`; оно не объявляется effective verdict oracle.

## Шесть сохранённых self-control names

Обычные test functions не добавлены и не удалены.
Все прежние controls сохранены; дополнительные ветви используют независимый library DTO и настоящий capture helper:
- full-fact positives для library и mixed observation;
- exact bool / SQLite 1 в metadata;
- identity/version/hash/authority/class/scope conflicts;
- неверная или отсутствующая metadata, missing identity/hash/version/spans;
- согласованная, но чужая generation/hash против прежнего committed child;
- совпадающие scalar/packed coordinates и их отдельные conflicts, malformed/partial values;
- nested library fields не исправляют неверный project top-level DTO.

Каждый negative сохраняет public payload и полный факт, требует healthy preparation, конкретную source-integrity ошибку и итоговый FAIL.
Healthy baseline должен пройти до fault checks. Synthetic oracle controls не считаются настоящим public-runtime/installed/stdio доказательством.

## Manifest

Все mode `100644`.

| Path | Base blob | Proposed blob |
| --- | --- | --- |
| eval/agent_developer_v1/mixed_retrieval_runtime.py | 748a0bff549cae94075ec2414cc4ffd75157cd7b | 2beaba07f393f52e99c21152d720983bc2aa64b0 |
| eval/agent_developer_v1/mixed_provenance.py | 3cff3b7555ecbcf3f4546ffe82d6131ccd0bdb6e | f9b08e92c08afda079f26aa735f8d8642a3022c8 |
| scripts/mixed_evidence_provenance_self_test.py | caefb69a18be940d99593e9cad598837c2a065de | 99575d56a3e27ab0d8429b853259ffbd2f5e05d2 |
| eval/agent_developer_v1/mixed_provenance_contract_migration.json | ebbf874792c09ad2a386792b23c7cd3ea4687c20 | 2f63f82bce958219ea75d529e0be9d335e1e57f9 |
| scripts/run_mixed_evidence_provenance_gate.py | f610afb987e7f4461c27ae1c97c4f83c64c7a52b | 41e18ddeee8032529b4c250837c564d94485ef96 |

Обратные точечные edits восстанавливают base runtime/oracle/controls/runner побайтно.
Read-time production код, resolver, qualifier, source selection и catalog не меняются.
Document-statement и mixed project qualification остаются отдельными задачами.

## Acceptance

Независимые source reviews всех шести файлов выполнены readonly reviewer и root: APPROVE.
Нужны actual шесть self-controls, syntax, current P15 runtime и обязательные downstream/closure gates на опубликованном SHA.
Прежние **4/7** и **2/6** не переименованы в PASS; новый результат не заявлен.
Локальные imports, pytest и subprocesses не выполнялись; commits/refs не создавались.

# PR #211: P1.5 storage source type → context DTO type

Статус: отдельная contract migration для independent review; runtime pending.
Base files перепроверены на `0855fb491ec388100cce92e57fe64b889c4cd3e0`.
Этот slice меняет evaluator mapping и его controls; production handoff четырёх lineage fields находится в отдельном slice.

## Почему меняется контракт

Actual P1.5 [run 37996655934 / job 114044350172](https://github.com/Vanilla1999/DocAtlas/actions/runs/37996655934/job/114044350172)
показал два полных факта — canonical policy и OrdersDraftPersistence — с source_integrity failures.
В обоих случаях snapshot.source_class=project_doc, committed child.source_class=project_file,
а project identity, scope, source_of_truth authority, stable id, generation, parent, display bytes/hash и char/line spans совпадают.
Отдельно отсутствуют четыре top-level lineage fields; их восстанавливает production copy-only slice.

Типы не взаимозаменяемы. Существующий SQL producer индексирует project_file.
`project_context_pack` явно преобразует ProjectDocsChunk в project_doc context DTO,
а project docs projector принимает именно project_doc.
Следовательно, прежнее требование snapshot.class=project_file проверяло представление другой стадии.
Исправление обосновано этим существующим producer/projector контрактом и отрицательными controls,
а не выбором любого фактического значения, которое делает отчёт зелёным.

## Точное правило

Для local frozen source одновременно обязательны:

- явный host project request;
- snapshot context source_class=project_doc, правильные project identity, project doc_scope и source_of_truth authority;
- ровно один реально наблюдавшийся committed child по canonical path + stable_chunk_id + generation_id;
- у этого child source_class=project_file, тот же expected project identity, project doc_scope и source_of_truth authority;
- прежние точные comparisons parent/source identity, source/display hashes, display text и всех char/byte/line coordinates;
- прежняя связь публичной source с authoritative same-call snapshot, полный frozen source fact и отсутствие answer/edit grants.

При любом другом типе на любой из двух стадий source_integrity остаётся false.
Нельзя принять набор {project_file, project_doc} в обоих местах.
Отсутствие lineage, другой owner/scope/authority, неправильная generation, hash или координаты не обходятся.
Library source handling, finite member manifests, robots infrastructure, runtime identity и read-only checks не меняются.

Crosswalk получает один explicit `project_source_representation` mapping.
Все прежние crosswalk fields, frozen question/fact/role bytes, historical report hash,
host bindings, required source paths и protocol-control members остаются прежними.

## Controls

Оставлены те же шесть self-test functions и все прежние positive/negative assertions.
Независимый fixture constructor теперь раздельно создаёт:
committed local child как project_file, snapshot local DTO как project_doc.
Он не импортирует production DTO defaults и не является actual runtime evidence.

В существующий `test_assignment_source_ledgers_fail_closed` добавлены:

| Изменение | Что остаётся прежним | Обязательный результат |
| --- | --- | --- |
| Wrong stored class; wrong snapshot class; обе стадии swapped; одинаковый advisory class; отсутствующий тип на каждой стадии | Public payload, полный frozen fact, bytes/hash и finite preparation | source_integrity FAIL |
| Чужой committed project owner | Полный frozen fact и finite preparation | committed scope/authority error, source_integrity FAIL |
| Committed library scope | Полный frozen fact и finite preparation | committed scope/authority error, source_integrity FAIL |
| Committed supporting authority | Полный frozen fact и finite preparation | committed scope/authority error, source_integrity FAIL |

Это шесть class variants и три дополнительных committed ownership/metadata variants внутри прежнего test.
Существующие controls неправильного документа, orphan/duplicate binding, обрезанного факта, неверной library identity/version,
network/member grants и report corruption сохранены.
Полный правильный fixture должен продолжать проходить; валидная цитата из неправильного документа остаётся различимой от отсутствующего обязательного факта.

## Exact manifest

| Файл | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| eval/agent_developer_v1/mixed_provenance.py | 180c6cd1c0e29c4028ec656d6d9d4d85984d0ca0 | 7cb2769ae2f1a71695c846ffd9d8c9d740170036 | 100644 |
| eval/agent_developer_v1/mixed_provenance_contract_migration.json | a82ad2c2b999fa273deddbd18e4412a37e176919 | ebbf874792c09ad2a386792b23c7cd3ea4687c20 | 100644 |
| scripts/mixed_evidence_provenance_self_test.py | 54c3e5cdf0511156b8779cdee27223963b9f789f | 65d4840ae2a8c3104cc6f28926aa26de4b2a6d69 | 100644 |

После independent review нужны обычные P1.5 self-controls 6/6 и actual public-source assessment на одном опубликованном SHA с production handoff.
Три оставшиеся positive cases (dependency docs, exact document statement, mixed roles) пока не объявляются исправленными.
Новые controls локально не исполнялись; imports/pytest/subprocesses не запускались.

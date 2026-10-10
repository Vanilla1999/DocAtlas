# PR #211: P1.5 диагностика binding к committed child

Статус: diagnostic-only slice; source oracle и production не изменены.
База: `c1e058cb51072f02620329000e2d68706a96bd67`.

## Что действительно произошло

Прочитан обычный CI [run 37995500399 / job 114040357202](https://github.com/Vanilla1999/DocAtlas/actions/runs/37995500399/job/114040357202):
2/7 cases, 0/6 verified full facts, runtime errors 0, oracle self-controls 6/6.
В пяти failed cases preparation_errors, authority_errors и state_differences пусты.

В `project_rule_prefers_canonical_policy` исходный вопрос `What is RetryPolicyLimit?` получает одну source и полный frozen факт из ARCHITECTURE.md.
`missing_full_fact_sources=[]`, но source_integrity отвергает источник с двумя причинами:
`different_project_scope_or_authority` и `source_not_bound_to_committed_child`.
Поэтому отчёт честно не считает этот видимый факт verified.
Остальные четыре положительных case не доставили требуемые полные факты.
Этот slice начинает с первого integrity failure и не объявляет остальные причины решёнными.

Artifact `11646598312`, `p1.5-current-provenance-37995500399-1`, 30095 bytes.
ZIP SHA-256: `68d0e6a4dd3d1e2781c5b547b5255c4d898c35bd85ba6db7c64765f383908bdc`.
Факты взяты из сохранённых logs; бинарный artifact не исполнялся.

## Найденная граница контракта

Текущий independent oracle в `mixed_provenance.source_errors` требует для local source:
snapshot lineage.source_class=project_file, project scope, source_of_truth authority, правильный project identity.
Затем он ищет ровно один committed child по path + stable_chunk_id + generation_id
и сравнивает parent/source identities, body hashes, display bytes и char/byte/line coordinates.

В текущем `project_context_pack` (`_project_context_service_shared.py`, blob `870d502ba0fe7ae3cb02a8c7a62a9ac2f72c5e01`)
явно создаётся retrieval DTO с source_class=project_doc.
`_docs_context_projection_core.py` принимает project candidates именно этого класса.
Storage source class и context DTO class относятся к разным стадиям; совпадение их строк само по себе не доказывает provenance.

Та же функция явно переносит stable_chunk_id, parent_logical_id, generation, display hash, char/line spans и reference evidence,
но не переносит top-level source_identity, source_content_hash, byte_start и byte_end.
Из исходников следует гипотеза потери части lineage при построении context DTO.
Существующий краткий лог не показывает, какие значения реально дошли до snapshot, поэтому oracle пока не меняется.

Корректный дальнейший контракт должен сохранять проверяемую связь с реальным immutable member/child,
не заменять отсутствующую provenance metadata фактом, что quote выглядит верно,
и отдельно описывать разрешённое преобразование storage source type в retrieval context type.
Конкретное исправление выбирается после actual field diagnostics; source_of_truth и owner/scope/version/hash guards остаются обязательными.

## Что добавляет этот slice

Только `scripts/run_mixed_evidence_provenance_gate.py`: после сохранения и верификации исходного report печатает дополнительные DIAGNOSTICS из уже сохранённого observation.

- Actual request/service requests/observer counts и project identity.
- Public source fields, authoritative same-call projected source, snapshot lineage и наличие каждого поля.
- Candidate hash material с hash/length вместо source text.
- Все уже наблюдавшиеся committed children того же пути с storage lane, совпадением stable id/generation и точными различиями child fields.
- Уже сохранённые pipeline stages, qualification outcomes и delivery decision.

Body/text/snippet/raw_document/section/title/preview/excerpt/answer значения выводятся только как UTF-8 SHA-256, число bytes и characters.
Подготовленные children не перечитываются. Нет повторного retrieval, SQL, qualification, scorer или source selection.
Формат исходного saved report, frozen questions/facts, source_errors, assessment, summary, exit verdict и assessment стоимости public DTO не меняются. Служебный log расширяется.
Неправильные типы optional binding/row structures не должны превращать diagnostic printing в runtime crash.

## Manifest и acceptance

| Файл | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| scripts/run_mixed_evidence_provenance_gate.py | c3124d822361e978db36d9d21a4f193ca62f532d | 7daab9ebeb8cdb7ff6839a13912641403d4a889b | 100644 |

Нужны independent source review и обычный P1.5 job на опубликованном SHA.
Проверка: прежний verdict не меняется от печати; actual diagnostics раскрывают два source errors без source body.
Локальное выполнение/imports/pytest/subprocesses не выполнялись.

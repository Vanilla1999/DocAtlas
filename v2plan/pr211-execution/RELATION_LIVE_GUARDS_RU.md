# PR #211: восстановление живых relation guards

Статус: узкая test migration, **без retirement и production edits**.
Base: `931be4a3f0296695d78cae9cb87da419a7124456`.

Изменены только три существующие test functions: source policy (15 cases), crop anti-replay (5), no-I/O (1).
Во всём семействе сохраняются **16 test names / 98 expanded cases**, исходные decorators/parameter values и shared `CASES`, `probe()`, `qualify()`.
Пять native original-only quality cases и отдельный public DTO guard не изменены.

## Почему нужна migration

[Последний прочитанный полноценный JUnit reader, 0855](https://github.com/Vanilla1999/DocAtlas/actions/runs/37996655986/job/114047940486):
witnesses **64 FAIL / 8 PASS**, safety **24 FAIL / 2 PASS**; первые failures — `StopIteration`.
Общий helper пытался извлечь `retrieval_need`, хотя current planner создаёт original и явно переданные host lookups.
Падение helper не проверяет source policy, crop revalidation или отсутствие I/O.

Current source policy: `docmancer/docs/domain/evidence_qualification.py`, blob `498a3941ce965443ee2508d4f88525966d3d581c`.
Current annotation: `docmancer/docs/domain/content_trust.py`, blob `ddfadc92850f9a08c627708515344513753992a6`.
Оба exact source blobs заново сверены на указанном base.

Raw risk veto удалён намеренно:
[completed contract](../stage3/pr211-context-admission-checkpoint-2026-10-06/NL_DICTIONARY_REMOVAL_COMPLETED_RU.md),
[final integrated review](../stage3/pr211-context-admission-checkpoint-2026-10-06/NL_DICTIONARY_REMOVAL_FINAL_REVIEW_RU.md).
Identity/freshness/index/lifecycle, explicit caller forbidden terms/roles и текущие source bindings остаются guards.
Retrieved text сохраняется как `untrusted_data`; метаданные не дают workflow/edit permission.

## Три сохранённых обязательства

| Existing function | Cases | Current independent oracle |
| --- | ---: | --- |
| test_relation_does_not_override_source_policy | 15 | Healthy candidate получает `None` от owning policy API; foreign и stale получают ровно `wrong_project_identity`/`stale_evidence`. Для каждого из пяти исходных bodies unsafe metadata остаётся inert: реальная annotation сохраняет content/document_data bytes, принудительно ставит untrusted_data/non-executable boundary и не меняет inputs. |
| test_replaying_old_approval_recomputes_relation_after_crop | 5 | Явный literal host lookup имеет healthy lexical positive и только собственный query-lookup-1 credit. Тот же anonymous positive не имеет public credit. Старый qualified trace с девятью fabricated inherited fields после замены body получает `insufficient_visible_match`, нулевой coverage и полную очистку этих fields. |
| test_compiled_queries_and_relations_are_pure_without_source_io | 1 | Первый original query из прежнего CASES[0] получает healthy context-only qualification. После прежних traps на builtins.open, Path.read_text/read_bytes, socket.socket заново выполняются настоящий planner и qualifier; result равен healthy result. |

Policy проверяется через собственный `evidence_policy_rejection_reason`: positive не зависит от lexical overlap заголовков конкретной таблицы.
Это проверка eligibility policy, не утверждение, что каждый body отвечает исходному вопросу.

Literal body lookup в crop control добавлен намеренно для изоляции boundary.
Original question bytes и original lane сохранены; seeded lookup не передаёт original credit и не заменяет пять original-only native quality cases.
Все исходные body strings и glossary crop сохранены.

Удаляемые при crop поля перечислены независимо в тесте:
`need_local_witness`, `admission_route`, `matched_need_ids`, `need_witness_spans`,
`need_witness_source_key`, `_admission_demands`, `context_eligible`, `context_need_ids`, `_need_context`.
Input trace/DTO dictionaries также проверяются на отсутствие mutations.

## Test migration manifest

Все mode `100644`.

| Файл | Base blob | Proposed blob |
| --- | --- | --- |
| tests/docs/test_admission_relation_witnesses.py | cf32e3ca365b7255a418a900074f18677b20c299 | f230beaa41ebb0b999f97493007fe253c629ef78 |
| tests/docs/test_admission_relation_safety.py | 9efbee0bb757bc0c92ccbf41187d3ca2589076ed | f3374394afce41c21659a9fc582f73e78b5ecc35 |

Обратная замена только этих трёх function bodies восстанавливает оба base files побайтно.
Поэтому все прочие test bodies, helpers, imports, decorators и parameter rosters сохранены.
Diagnostic registrations/node hashes не меняются; ordinary test functions не добавлены и не удалены.
Independent static review исходной трёхфункциональной migration завершён APPROVE. Финальная safety revision дополнительно ограничивает lifetime I/O traps контекстом; её отдельный independent review также завершён APPROVE. Runtime пока не выполнен.

## Отдельный proposed critical-gate slice

`scripts/run_critical_mutation_gate.py`, mode `100755`:
base `c0a3b41ef9f52a8104d5c2fe24e44642ce33134b` →
proposed `7331b5a85b99887ec64334388a7b23c8eed687e5`.

Harness добавляет ровно три существующих migrated targets: **32 → 53** normal baseline cases.
Все 13 прежних mutants остаются; добавлены шесть адресных faults, итого **19**.
Весь код от `def _ignore` до конца файла побайтно совпадает с base, включая baseline refusal, exact JUnit roster/guard validation, diagnostics и отдельный literal comparison.
Оба production modules добавлены в существующий import-origin inventory.

| Mutation | Killer | Tests / expected FAIL | Первый guard |
| --- | --- | ---: | --- |
| relation_source_identity_guard | source policy | 15 / 5 | critical_relation_policy_identity |
| relation_source_freshness_guard | source policy | 15 / 5 | critical_relation_policy_freshness |
| relation_raw_metadata_cannot_authenticate_quote | source policy | 15 / 5 | critical_relation_risk_metadata_inert |
| relation_anonymous_trace_has_no_public_credit | crop | 5 / 5 | critical_relation_lookup_no_borrowed_credit |
| relation_crop_clears_inherited_proof | crop | 5 / 5 | critical_relation_crop_no_inherited_credit |
| relation_qualification_performs_no_source_io | no-I/O | 1 / 1 | critical_relation_qualification_no_io |

Все mutations требуют **0 ERROR / 0 SKIP**, полного прежнего killer roster и только ожидаемых assertion guards.
Normal baseline должен полностью пройти до выдачи какого-либо mutation credit.
Other legacy failures, malformed query lane и collection/setup errors не засчитываются.

Каждый exact source anchor имеет ровно одно совпадение.
Пять qualification mutations имеют before SHA-256
`34d299026e7f826c72c5f40f79b48980eda3671690da7282e84b9e7d5d38c554`;
annotation mutation — `a8f7d738a66b55a30e0c4ab6a0694a647f1500f1cbfb15e74896daea8fbba3b5`.

| Mutation | Proposed production-copy after SHA-256 |
| --- | --- |
| relation_source_identity_guard | 5cf3c77d433595b775936ca0e63c0a4d2b0632d7806c38b73d33f30903862403 |
| relation_source_freshness_guard | 9119187e40a00d8498db5af8144d45ea9b5970b23abc820b2cffef02d5bf66d0 |
| relation_raw_metadata_cannot_authenticate_quote | fef3fbe43bdb6ac66bd7241327083c0db9c9a8c7434a1fbe9896f654211ae381 |
| relation_anonymous_trace_has_no_public_credit | 2cfe7d9938e01646ae85dc969b270eed11d136fb15c61986ec2887c6999ea79b |
| relation_crop_clears_inherited_proof | 673c68c06c17a6af3a50c3e7108ecba078cadc853488e74947bebe49ab94223b |
| relation_qualification_performs_no_source_io | 2a99268c408d01f562a5ce3c683b9f8b67d35059ffd277de65db2c7fdf9a9e82 |

No-I/O fault добавляет в функцию чтение её собственного source file через `Path(__file__).read_text`.
Оно существует только в disposable mutation checkout: первая healthy call проходит, повторная call после traps должна дать именованный AssertionError.
Traps ограничены `monkeypatch.context()`: даже при injected exception исходные I/O APIs восстанавливаются до pytest traceback/JUnit reporting; сами calls и сравнение результата сохранены.
Никакое новое чтение не добавлено в production branch, рабочие тесты, CLI или пользовательский runtime.

## Проверка сохранения consumers и acceptance

На exact 38da предшествующий read-only анализ прочитал все 1272 tracked Python files без ошибок:
safety импортирует `CASES/qualify/probe`; mapping_assignments импортирует `qualify` и использует внутренний import `probe`.
Кроме того, `experiments/language_aware_context/packing_regressions.py` запускает safety module как pytest selector.
Эти names/paths и consumers остаются неизменными. Это не утверждение о любых динамически собранных imports/non-Python selectors.

Нужны review harness proposal, actual green **53-case normal baseline / 19 intended kills**, общий core и прежние downstream/installed/client gates на опубликованном SHA.
Ни 21 migrated cases, ни оставшиеся 77 cases пока не объявлены PASS.
Никакого retirement на основании этого slice нет; дальнейшее сокращение требует отдельного доказательства и review.
Локальные imports/pytest/subprocesses не выполнялись. Commits/refs не создавались.

# PR211: контекст двух исходных идентификаторов

Статус: исходники и направленные faults подготовлены; собственный runtime 12 baseline / 46 mutation controls ещё PENDING. Успех AgentDeveloper/V2 этим документом не заявляется.

## Контракт и основание

Исходный вопрос: How does OrdersDraftStore differ from PaymentOutbox?

В frozen ARCHITECTURE.md оба имени и полный факт находятся в одном обычном абзаце. В literal_context_admission.py на 2a25313955f125e79666eb386f108e8e94eac7cf прежние single-name / Explain / count / filename формы этот вопрос не принимают; ordinary_body_context.py на 46e43fba32a4a30784b5b658b0e5717297d78516 исключает technical mentions. Это доказанная граница исходного кода, а не наблюдённый first-veto конкретного downstream запуска.

Добавлены только полностью потреблённая generic форма How does A differ from B? и private body witness. A/B — два разных, реально извлечённых bare unresolved identifier. Оба целиком и с исходным регистром должны находиться в одном substantive plain paragraph уже проверенного raw window. Qualified, path, prefix segments, headings, links, code, labels и объединение разных paragraphs не дают пару. Повторы имени допустимы; для проверки содержательности удаляются все вхождения обоих имён.

Это развитие cite-only context по ADR0003: никакого доказательства различия, синтеза lookup, изменения role, original credit, answer/edit authority. Canonical qualification veto, current owner/scope/generation/catalog/file hash и mandatory raw bounds остаются до нового пути. Старые ветки и ordinary module не меняются.

## Точные входы

| Материал | Идентичность |
| --- | --- |
| Source Git blob | 7cec4c32a3760b27482b14f6d7d5f3e3d53f96aa |
| Source path | eval/agent_developer_v1/projects/explicit_manifest_monorepo/ARCHITECTURE.md |
| Native fixture path / scope | ARCHITECTURE.md / all |
| Source UTF-8 bytes / SHA-256 | 485 / ccad600f6c90895fa820d0516c37382a7ed7b2cbed5f99137bdefa2e40d05ba7 |
| Original question SHA-256 | 14d4ada968e58c9f909185036a1d111e3b5d38b498796e9456657769496405e4 |
| Full fact span / SHA-256 | [361, 484) / d0a22abf8a42273fca0ff93e0f1fb01a0bc6edfb9b4d6c5a0544b86eb78b8e48 |
| Frozen V1 expected trajectories / V2 cases blobs | 3e7ce4abb294b69b4dfb560d1878f9f769571686 / e0f873ffa5df3abbd4bf55b13a58e11dd49d58d8 |

Полный неизменённый факт: OrdersDraftStore writes order drafts before upload, whereas PaymentOutbox writes pending payment events until confirmation.

## Native контроль и цена исполнения

В существующем closed_literal_context вызывается дополнительная private группа из literal_window_controls.py. Сохраняются прежние четыре исходных closed-context тела и прежние raw controls (2 native reads, 2 preparations, 3 projection replays). Новых pytest functions, jobs, dependencies или удалений нет.

| Дополнительная работа на здоровый вызов группы | Количество |
| --- | ---: |
| Finite member preparation через существующий prepare_docs fixture | 1 |
| Настоящий public get_docs_context, exact original question, scope all | 1 |
| Наблюдаемый core вызов внутри того же public read; без повторного исполнения | 1 |
| Detached core projections: healthy + 9 query/source counterfactuals | 10 |
| Direct frame probes: 2 positive / 3 negative | 5 |
| Direct body probes: 2 positive / 12 negative | 14 |

Это честно 19 прямых predicate calls; они не объявляются native retrieval либо выполнением других frozen tasks. Projection counterfactuals отдельно проверяют incomplete suffix, case, prefix, одинаковые имена, чужой original plan, owner/hash/raw span/member scope. Direct body probes проверяют одну отсутствующую сторону, разные paragraphs, metadata/code/path boundaries; healthy повтор и нейтральные CopperLedger/QuartzMailbox исключают запрет повторов и привязку к business names.

Native observer возвращает тот же result tuple. Он отдельно сохраняет core payload/snapshot, пока public observer сохраняет итоговый facade результат. Source body, host-derived owner, generation, file/catalog hashes и char/UTF-8-byte/line bounds проверяются независимо. Core witnesses связываются с исходным core window; final citation может быть текущим same-source superset, но обязана целиком сохранять его с теми же scope/version/authority. Optional URI проверяется при его наличии. Actual original query plan содержит только query-original/original/direct без parent. Original-query credit и answer/edit authority остаются false; query_coverage остаётся partial.

Facade c7aef87448fbd4508634c16d86ec589dc22ab159 законно выполняет joint/query-block finalization после core. Поэтому равенство core/final ranges не требуется. Обнаруженная при review устаревшая byte-coordinate metadata исправляется owning slice148: joint_context_candidates.py d59e90626cc951c980d948953327a4932ef5aa3f (root commit 07d44423); final byte guards здесь сохранены.

## Направленные faults и собственный proof

| Fault | Первый независимый counterexample | Обязательный guard |
| --- | --- | --- |
| pair-context-admits-one-body-name | direct body single_body_name | recovery_pair_requires_both_body_literals |
| pair-context-accepts-unconsumed-tail | captured projection unknown_suffix | recovery_pair_frame_requires_full_query |
| pair-context-joins-separate-paragraphs | direct body separate_paragraphs | recovery_pair_keeps_paragraph_boundary |

Все три faults изменяют настоящий literal_context_admission.py, anchor count = 1. Native healthy positive и healthy detached projection идут до отрицательных probes. Ошибочный paragraph fallback включается только после отсутствия локальной пары; это сохраняет здоровый ARCH и достигает именно split-paragraph guard. Error/import failure, чужой guard или неуспешный baseline не считаются mutation kill.

Нужен совместный green baseline 12/0F/0E и все 46 intended kills в существующем recovery runner. Для каждой новой mutation: case closed_literal_context, exit 1, counts {passed:0,failure:1,error:0} и указанный guard. Сохранены 43 старых blocks, import roster, execution/report verifier; runner вырос с 394 до 406 physical lines. Gate1000 и critical998 не изменяются этим slice. Никакой новый downstream PASS до собственного CI не приписывается.

## Manifest и инверсии

| Path | Mode | Base Git blob | Proposed Git blob |
| --- | --- | --- | --- |
| docmancer/docs/domain/literal_context_admission.py | 100644 | 2a25313955f125e79666eb386f108e8e94eac7cf | 42a7f7ff3daa530585721c1f98bc39a978f2e2d4 |
| eval/agent_developer_v1/literal_window_controls.py | 100644 | f281d68d81ca6a52d9c8dd093861046f51017f2f | 44a1f7b4bbc62b700b6cc7a2fc2ed426bef3d4d7 |
| scripts/run_recovery_mutation_gate.py | 100755 | 3360dce2970cab4f45b180c0fe23c8f13f23db4d | b1673f6eb2b6623fc9358a90fa307634b380568c |

Production: +57 lines, 380 total; удаление двух private helpers и additive wiring побайтно восстанавливает base. Control: 495 lines; удаление двух private control helpers и обратная замена последнего return/wiring восстанавливают f281 целиком. Runner: удаление ровно трёх новых blocks восстанавливает 3360 целиком. Все три blobs прошли exact Git roundtrip; локального runtime/AST/import исполнения не было.

| Proposed source | SHA-256 |
| --- | --- |
| docmancer/docs/domain/literal_context_admission.py | 96bfa45783ce7dc86927f01af385e214b05790cc8cf380b52ef16bdb3eca45b0 |
| eval/agent_developer_v1/literal_window_controls.py | ad263065581cf4beb65b8bc39b45b2a1d49e43d41a1e546beae35854592d5cae |
| scripts/run_recovery_mutation_gate.py | 10bd2e1dffd74344ca603938b573110dacdc290ea9b8f56413deb7451e6ddef5 |

Все mutation before hashes равны production SHA-256 из таблицы.

| Mutation | After SHA-256 |
| --- | --- |
| pair-context-admits-one-body-name | f1569a8565c014171cf89a68b3e6f9b3632c04b347e7db9f1f8ba5ec6f965e06 |
| pair-context-accepts-unconsumed-tail | 3cdbeb659539ae7c6f9ed71153b402a965f8de417f8443e4baf5f797152bd663 |
| pair-context-joins-separate-paragraphs | 9fcc73e57ff7a129c3b4773e5fa9e15bbd202da5c83bb8b562166c6a399e3d80 |

Сохранённый old43 tuple slice: от MUTANTS = ( до следующего \ndef _digest, без последнего delimiter; 15734 UTF-8 bytes, SHA-256 d83d6a59c8a44dcd07a765dc5d461e0e0af300a5bda5278601a2642fd21282a6. Этот hash описывает старый текст, не новый runtime receipt.

Исходные task/corpus/protocol/gold bytes не изменены. Review кода не заменяет own runtime и не разрешает retirement других tests.

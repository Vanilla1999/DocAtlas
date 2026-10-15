# PR211: независимый factual review acceptance 991638f

Решение: **APPROVE** для указанных байтов документации. Это проверка точности завершённого CI и границ следующего изменения; она не означает успешную acceptance или разрешение merge. Runtime после `991638f` **NOT RUN**.

База review: HEAD `991638f28ecff659c320b45738edfaa8b9fd375e`, merge checkout `e499c39704d4923164dc50c1460a2e1c50b81d7f`, tree `955bac94d5ca6b847f558b0e7dbd0dcb8265e9df`. Прочитаны только текущие документы, закрытые evidence snapshots и узкий successor; исторический CI повторно не запускался.

## Проверенные документы

| Файл | Bytes | SHA-256 |
| --- | ---: | --- |
| `PR211_991638F_ACCEPTANCE.json` | 74382 | `e29c749a61cb989e98bc32a123cc3675ac146af5fb3346e4b51fb416d4a96d1f` |
| `PR211_991638F_CORE_ACCEPTANCE.json` | 12960 | `487a53de8ddaf11b2bcc6b638fd9e9660df355d24fb904dc2142b0e26f81f701` |
| `PR211_CHECKPOINT_RU.md` | 50693 | `416821927e7f15a319b268962b5000a694e70840379a8ea8066ba2aeb3d0c638` |

Все десять записей `source_evidence` проверены по реальным сохранённым файлам: bytes и SHA-256 совпадают. Core JSON byte-exact равен `991638f-core-validated-delta.json`. Общие core-поля основного acceptance точно равны core delta. Секции `advanced`, `self_host`, `self_host_unit_cross_check`, `retrieval_evidence` точно равны актуальному advanced audit; `runtime` точно равен frozen runtime-final-delta.

| Evidence | Bytes | SHA-256 |
| --- | ---: | --- |
| `991638f-core-validated-delta.json` | 12960 | `487a53de8ddaf11b2bcc6b638fd9e9660df355d24fb904dc2142b0e26f81f701` |
| `991638f-core-critical-reasons.json` | 18134 | `a35c6003e9325b9c086900a262403e60b2ead6e2f196bb3259e1d8fb241acbf0` |
| `991638f-core-failure-phase-audit.json` | 42764 | `1d53539682cfa012942fdf381cf587278a75426205038583e7addfc839e04911` |
| `991638f-core-message-variation-audit.json` | 10545 | `b840605c907a4242d21c2053ecd5f59479f5af7d1e01007bdd6d882af2998be4` |
| `991638f-core-provenance.json` | 5735 | `ecfa6df66698b93a92bdcab0b2cae1d7b57c3e334cf7c2519fe46da4a0fcfe08` |
| `991638f-runtime-final-delta.json` | 18985 | `fd8e4994ef6c30e339919d7838a307724a883754c0ecbe9e95c2e1758c4b6293` |
| `991638f-runtime-release-audit.json` | 709588 | `f6d53afca23cd2b159c5932b7c765d5317d7f3675f2e1aecb17840a122d6aca2` |
| `991638f-advanced-related-audit.json` | 42355 | `3245bca5f62ce8c92edf660659a60ac41d25cecf8e2c7ae93eb3b01a6f1f2e3f` |
| `991638f-final-workflows-jobs.json` | 56222 | `6bf5d69a294d8ff91b4940dc21cb22bde51dad2310a7a59fcf1fbbb0793da71f` |
| `991638f-publication-verification.json` | 6678 | `af43ea830428b88eb2f5d686077bb0c5d69251efbae7ace2f9e25fd346d3e3e0` |

## Фактические утверждения

- Core на трёх Python: **8513 = 6496 PASS / 1946 FAIL / 61 ERROR / 10 SKIP**. Против 04ff — ровно семь FAIL→PASS, шесть новых nodes (5 PASS / 1 FAIL), без удалений и прежних PASS regressions. Семь из восьми старых targets PASS; оставшийся module target дошёл до публичного отказа. 141 security control на каждой Python, 47 прежних diagnostic errors и десять продвинувшихся первых barriers описаны без объявления скрытых причин или PASS.
- Advanced **622 = 524 PASS / 98 FAIL**, roster/states прежние; все девять независимых downstream steps действительно FAIL, dependent mutation SKIP. Critical baseline **19/28 PASS**, mutants не запускались.
- Legacy uploaded JSON действительно подтверждает **2807 tracked files / 119478143 bytes**, exact tree, успешный cold guard и real committed preparation **10 members / 98 sections**, zero deletions и сохранность origin. Реальные результаты **10/16 PASS**; original coverage **0 < 12** и contamination **1** остаются блокерами. Это проверка in-process fixture, не installed app или Git-impact.
- V2 действительно остановился на frozen witness `wiki/Commands.md`, отсутствующем в active catalog. Документ physically tracked/copied; это не даёт membership. **Собственный V2 prepare не сертифицирован**: JSON/provenance отсутствует, порядок вызовов не заменяет evidence. Ни catalog, ни gold автоматически не исправляются.
- Retrieval: все 80 фактических BPE/size values прежние, canonical UTF-8 bytes сверены 80/80; **24 из 48** within-budget cases превышают 800, максимум **1451**. Снятие fixed catalog ceilings не отменяет этот критерий. Catalog **6918** и output schema **860** корректно обозначены как прежние измерения при неизменном source; app/model стоимость не заявлена.
- Runtime-секция совпадает с закрытым audit: шесть platform SDK jobs PASS, три package/CLI runs по 77/77, 19 logs / 15 invocations / 30 lanes / 420 observations и scripted harness 1/1. Actual Claude Code/Codex/OpenCode sessions остаются **NOT RUN**.
- Все 17 workflow rows совпадают с final snapshot: **8 SUCCESS / 8 FAILURE / 1 SKIPPED**, все completed. Проверены все 15 main и 13 P1 job rows. Required CI `113532153123` и P1 aggregate `113532324954` действительно FAILURE; release validation SUCCESS, публикация release не происходила.
- Frozen embedded runtime metadata ещё содержит прежние aggregate `in_progress`. Это явно и корректно superseded полем `runtime_final_run_statuses`, сверенным с final runs; snapshot не переписан задним числом. `readiness=false` и `complete_ci_acceptance=false` сохранены.

## Последующий synthetic lookup: граница утверждения

Проверены существующие ссылки на author и independent source reviews; текущие source/report hashes:

- `tests/test_project_docs_self_host_fixture.py`: `098c51af40c4ad37e7ddc07a4fd64abf6f2f4caaa7a8eced02cb41754e9a0569`.
- `PR211_SELF_HOST_LITERAL_LOOKUP_REVIEW_RU.md`: `e9fe6d2d21bce91ced5accae87b0582ebbab07f96c6ce78589eefba1f85d2834`.
- `PR211_SELF_HOST_LITERAL_LOOKUP_INDEPENDENT_REVIEW_RU.md`: `7265c68bd7cbf0800d16ab29a11914de75012137bc4d1cbbf761118b488ab9a9`.

Stdlib AST cross-check подтверждает все **24** исходных assertion expressions и **5** добавленных (итого29); AST вне одного node неизменен, включая RULES и остальные пять tests. Исходный question сохранён. Author и independent reviews явно описывают добавленный host lookup и guards: lookup credit отдельно, `query-original` не covered и остаётся missing; answer/edit authority не возникает. Checkpoint не приписывает старому JUnit скрытый qualification reason и не объявляет новый runtime PASS.

Все шесть ссылок текущего checkpoint раздела разрешаются; локальные связанные файлы существуют. `subsequent_work.runtime=NOT RUN` и граница «не сертифицирует commits после991638f» явные. Frozen downstream questions/corpus/scoring, gold, floors, production retrieval и prohibition deferred retrieval сохранены; critical proposal остаётся PENDING scope decision.

Blocking factual findings не обнаружены. Изменён только этот review-документ; runtime/imports/pytest/installs/providers/client calls, reruns, publication и implementation edits не выполнялись.

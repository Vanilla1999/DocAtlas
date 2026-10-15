# Admission selection V2 — состояние

**Итоговый статус: этап завершён, включая независимый review.** См. RESULT_V2_RU.md, review/FINAL_REVIEW_V2_RU.md, REVIEW_RESULTS.json, X_FINAL_REVIEW_RU.md, X_REVIEW_RESULTS.json. Подтверждена узкая польза Mini на HOLD01; complete positive semantic answers B1/Mini3/6, Budget1/5finished+1UNKNOWN. X-prune увеличил суммарный submitted proxy6.8%, не рекомендован к внедрению. Upstream completeness, exact citations и empty-source contract не закрыты. Итог7prepares/58context/56forwards/40hostattempts39finished1UNKNOWN. DefaultOFF; commit/push/unit tests не было. Дальнейшие runtime/модели автоматически не запускать. Ранние pending записи ниже — история этапа.

Дата: 2026-10-12. Запрос владельца разрешает bounded public/model/host experiment по CONTINUE_ADMISSION_RESEARCH_V2_RU.md.
Git: fix/main-flow-compact-evidence, HEAD 4849b8f796d9e3e25e2c49e58562ec6859978411; четыре прежних изменения сохранены.
Старые artifacts не изменяются; default OFF.
Preflight: runtime-product/model-runtime и pinned Mini assets доступны; inference ещё не запускался.
Docs MCP: insufficient_evidence, рекомендован code search, без prepare/retry; служебный docs lookup не evaluation context request.
Review-role: ses_ecfeee2dbffeq5JcGfOvA1CCU4 — независимый synthetic corpus/oracle, далее raw review.
Новые продуктовые файлы планируются: application/experimental_candidate_selection.py и минимальный hook в application/_project_docs_service_part03.py. Никакой подмены retrieval или validation.
Запуски и результаты добавлять сюда по мере выполнения; таблицы не считать PASS до raw review.

## Primary выполнен
- Independent corpus/labels frozen before inference; holdout oracle executor не читал до freezek и не использовал при выборе параметров.
- Preflight blockers сняты REVIEW_PATCH_DELTA_RU.md; явная transport adaptation TRANSPORT_BINDING_RU.md: четыре семейства в отдельных project/catalog, actual public versionunversioned, domainversion2026.1 не подделывается. Version denial NOT_TESTED/literal transport expectation UNSATISFIED.
- Calibration provisional +final realpublic confirmation: k=2, all delivered B1 witnesses preserved Mini; Budget использует тот жеk. Fulloracle completeness оценивается отдельно.
- Primary: 7prepares,54realcontext requests,40Mini FP32 forwards,36hostrequests,35completed answers. Один consumed HOLD07_Budget STARTED был прерван shell120s с UNKNOWN backendcompletion; никаких retries/repair.
- Recovery: существующие projectfiles/member SQLite stores/generations сохранились; resume_remaining.py reattached именно их, no prepare/re-score, только10missing public+16unconsumed host requests. Полный commoncandidate sequence и poolhash match across calls проверены. Результаты первичного процесса не переписаны.
- COSTS_V2.json: фактическая Budget/Mini orchestration требует initial B1capture +newpublicselected read; оба acquisition costs включены. Hypothetical inline onecall speedup не заявляется. Coldload отдельно; proxies неbilling.
- Independent raw review в той же review роли запущен; это не автоматическая production acceptance. Default OFF, commit/push/CI/unit tests не было.

## Conditional X подготовлен
Остаточная diagnostic Q16 Mini выдача911snippet proxytokens/1653submitted обосновала узкую conditional проверку. X_PROTOCOL_RU.md и run_x_pair.py зафиксировали пару X-rank/client-exact-prune двух известныхdiagnostics на томжеpoolk2, threshold.3 до X inference. Это не nativeprunedDTO, а source-bound clientadaptation с protectedheadinglines и сохранением public expansions вне evaluated native windows.

X реально выполнен:16forwards/2public/4host,0prepares. X top2 membership совпал с Mini в обоих diagnostic случаях. Submitted proxy Q16:1653→1479 (−10.53%);Q46:1141→1506 (+31.99%), из-за excerptframing/metadata. Q16 newlinecitation дефект сохраняется в Xprune raw; окончательный verdict — independentreview. Финальный ledger:7prepares/56context/56modelforwards/40hostattempts,39completed+1unknown. Corpus/frozenoracle не менялись. Artifacts≈45MiB,models/downloads/install/CI/commit/push/unit tests не добавлялись.
Подготовлены COSTS_V2.json, X/COSTS.json, SELECTION_V2.patch (только новые2productfiles delta), SOURCE_IDENTITY.json, UPSTREAM_BLOCKER_RU.md. До независимогоreview выводы preliminary. Та же reviewроль получила Xraw как дополнение к primaryreview, новых исследовательских агентов нет.

## Default-off smoke после нового hook
Из-за нового producthook появилась новая причина проверки default:2оригинальных publicQ16/Q46 без experimentalflag, прежний mainstore/project,0prepares/0models/0host. Оба сноваinsufficient_evidence/empty/falseauthority, observedreadstateunchanged. Это DEFAULT_OFF_SMOKE.json, НЕ full40/50parity или installedstdiosmoke. Итоговыйсчёт теперь**58context** (54primary+2X+2default),7prepares/56modelforwards/40hostattempts39completed1unknown.

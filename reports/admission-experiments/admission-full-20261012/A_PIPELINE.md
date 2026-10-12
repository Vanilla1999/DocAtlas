# A — baseline pipeline и изолированный public B1 (initial, read-only)

**Актуальный статус после разрешённого исполнения координатором:** G independently reviewed experimental B1 direct40 **39/40**, Q46/Q16 доставлены, все прежние direct28 сохранены, old10 **10/10**; единственный пробел Q31. Default-off normalized40 unchanged и 10 control PASS по G. Это не default deployment acceptance: четыре прежних relevance-negative CURRENT_CONTRACT FAIL и существенный cost tradeoff сохраняются. Подробности в разделе 10 и `A_Q31_REMAINING.md`. Первоначальный read-only анализ и pre-runtime implementation receipt ниже сохранены как история.

## Решение / статус

**Следующим испытывать B1: дополнительную source-policy-valid read-only admission lane на существующей публичной границе `get_docs_context`, с прежним retrieval/ranking и неизменным operational delivery veto. Не включать в production default.** Это экспериментальное изменение relevance-контракта, не исправление threshold и не доказательство качества хоста. Точный минимальный product scope предложен ниже: три domain-файла. Реализация не назначена и не выполнялась.

- B0: **архивный факт delivery FAIL Q46/Q16 повторно подтверждён** по raw JSON и независимому corpus/hash; нового B0 исполнения нет.
- B1: **ADAPTED proposal / NOT RUN**. Feasible по статическому extension-point анализу; публичная доставка после patch, source-policy controls и ответы хоста **UNVERIFIED / NOT RUN**.
- Ни inference, ни provider/download/model/CI, ни product runtime/import/pytest/AST/install, ни nested agents. Единственный записанный файл — этот отчёт. Статический анализ не называется runtime PASS.

## 1. Идентичность и материалы

Рабочая копия `/tmp/opencode/docatlas-compact-review`: branch `fix/main-flow-compact-evidence`, HEAD `4849b8f796d9e3e25e2c49e58562ec6859978411`; исходный `git status --short` пуст. `git diff --stat d8af387de507007f2b8c83f04aac78feb9b6760c HEAD` содержит только четыре review-документа, без product/test изменений. Поэтому кодовую реконструкцию можно сопоставлять с архивным продуктом, но его CI не является новым run на review SHA.

Полностью прочитаны FULL_PROTOCOL, AGENTS.md, `q46-admission/STATE.md`, исследования и A/B/C/RESULT предыдущего этапа; также checkpoint `v2plan/PR211_CHECKPOINT_RU.md:12–29`, ADR0003, frozen old10/extra40 вопросы, corpus и manifest. Старые отчёты использованы для навигации; выводы ниже проверены по текущему коду и первичным сохранённым данным.

Самостоятельно пересчитанные offline SHA-256:

| Материал | SHA-256 |
|---|---|
| `docatlas-compact-d8af387.zip` | `aa539f453e108bc0a2b25e5fd8011af528f294f337e39e94ee1092fe966c1485` |
| `corpus.md` | `31da2449b89b3edc72f6f463a84144d256105a77f99bfe5c7bdeab9cdd3c1d00` |
| `questions.json` | `2b88e653b4726747d4ee55682d159744bc1b7dcfc8ac525ee830a688ec401f67` |
| `questions_extra40.json` | `5d0618db2bc1ddb18f65ac246b79ecb1adaadeef3a1618ed68d9f5a5784a12dc` |

Все совпадают с `eval/main_flow_comparison/compact_review/EVIDENCE_MANIFEST.json:13–17,64–70`. `final_compaction/head.txt` содержит `d8af387de507007f2b8c83f04aac78feb9b6760c`; manifest связывает архив с run `38227928058`, artifact `11735844893`. Остальные пять ZIP заново не хешировались: для данной проверки они не нужны. Извлечённые JSON проверены непосредственно, byte-for-byte соответствие каждого извлечённого файла ZIP отдельно не заявляется.

Все raw paths ниже относительно `/tmp/opencode/docatlas-review-evidence/final_compaction/`, все code paths — относительно repo; ссылки относятся к зафиксированному HEAD.

## 2. Q46 и Q16: наблюдение, не пересказ runner verdict

Raw: `extra40-results.json/results[id=46]` начинается на строке **225059**, `[id=16]` — **37704**. Оба `lookup_variant=no_lookup`, `lookup_queries=[]`, вопросы неизменные. Публичные payload не содержат `sources`, имеют `context_available=false`, `answer_supported=false`, `answer_available=false`, `edit_ready=false`, `status=insufficient_evidence`, `reason_code=required_evidence_missing`. Это независимое подтверждение **недоставки фактов**, не оценка ещё не полученного model answer.

| Свойство | Q46 | Q16 |
|---|---|---|
| Исходный вопрос | Можно ли признать PASS, если оба режима логирования дали одинаковый неправильный ответ? | Какая диагностическая информация у события завершения, которой нет в начале запроса? |
| Независимый corpus факт | `Одинаковые неправильные ответы не дают PASS.`; строка 82, `[6952,6996)` | `завершение содержит ` + `` `duration_ms` `` + `\n  и ` + `` `trace_incomplete`. ``; строки 30–31, `[1152,1209)` |
| Stable child ID | `child-aefd3978207191f7af083c7353118c9d422a136d` | `child-f4934d98be2629717870adaf0d8ff223470c5204` |
| Member-read окно | `[6919,7107)`, 188 chars, `items[4]` из 10 | `[1024,2100)`, 1076 chars, `items[0]` из 11 |
| Window SHA-256 | `a4999c80a4ff1bd34eb63c5855cca1b7575afe24224a22fd99628cb30c27c9d9` | `fca78e50498ae130919876243d2bc8738e13f0f2a6ff6010f2ec5905b2d1ae33` |
| Qualification rows | `[4]`, `[14]` | `[0]`, `[11]` |
| Canonical literal terms matched | `pass`, 1/12, ratio .0833 | `события`, `завершения`, `в`, `запроса`, 4/11, ratio .3636 |
| Outcome | `insufficient_visible_match`; `literal_context_admission=null` | то же |

Полные raw selectors внутри каждой строки:

- `payload.diagnostics.delivery_observations.returns[0].result.result_windows.items[...]` — найденный member-read window.
- `payload.diagnostics.qualification_outcomes[...]` — `observed_candidate.source_reference`, `observed_qualification`, null admission.
- `payload.diagnostics.delivery_observations.returns[1].result.context_windows`: **`count=0`, `items=[]`, `omitted=0`**; delivery `{deliverable:false,reason_code:no_reliable_context}`.
- `...returns[2].result.context_windows`: те же нулевые counts; delivery false с `required_evidence_missing`.
- `payload.diagnostics.projection_observation.delivery_blocked=true`, `stage_status.delivery=blocked_before_projection`, `pre_projection_qualified_ids=[]`.

Самостоятельный Unicode slice frozen corpus по обоим полным window spans с последующим UTF-8 SHA-256 совпадает с `display_content_hash` member read и `observed_candidate.window_sha256`. Полный обязательный fact лежит строго внутри каждого окна. Q16 canonical trimmed `reference_visible_span=[1024,2098)`, а исходное окно `[1024,2100)` заканчивается двумя newline: это не потеря fact и не hash mismatch.

Восстановленное Q46 окно, **не публично доставленный текст**:

> результат и изменения состояния. Одинаковые неправильные ответы не дают PASS. Переключатель логов не должен менять права, выбор источников, побочные действия или число продуктовых вызовов.

Q16 полное окно начинается с связи `docatlas_request_start`/`docatlas_request_end` через `request_id`, далее прямо содержит оба completion поля и несколько следующих пунктов. Raw diagnostics сохраняют spans/hash, а не весь body text; восстановление из независимого corpus с совпавшим hash явно отделено от наблюдения публичной выдачи.

Обе source identities: `README.md`, content SHA выше, project `local:59d0d052033c551d84916eefea248b188ed36d7a937e26b73c41716355ba928d`, snapshot `gen-98f972e217b24d5b9fe7428cde4f24f7`, version `""`, doc_scope project, member module_path `""`, active/current/stale=false. Это валидная архивная lineage этих окон, **не общее доказательство access/consent/wrong-version isolation**.

## 3. Где теряется контекст

1. **Acquisition состоялся.** `_project_docs_service_part03.py:223–242,258–269` делает реальные native reads, fresh reference preparation, discovery recording, tagging. Оба answer-bearing окна ещё присутствуют в member result. Нельзя называть это отсутствием retrieval recall для указанных окон.
2. **Canonical qualifier слишком буквальный для данных вопросов.** `domain/evidence_qualification.py:342–364,418–448` считает unchanged literal body matches, threshold .5 при отсутствии hard-exact. Q46 singular `одинаковый неправильный ответ` не совпадает с plural source wording. Q16 4/11 также ниже .5. Это relevance admission, не security denial. Metadata/heading совпадения не могут сами дать body proof.
3. **Partial lane не возникла.** `application/reference_query_tagging.py:107–113` вызывает `admit_original_literal_context`; raw null наблюдаем. `domain/literal_context_admission.py:296–304,308–374` требует либо explicit/closed-frame witness, либо ordinary-body witness. Q46 `PASS` unresolved, не explicit identity; Russian conditional не закрытый frame. `domain/ordinary_body_context.py:113–182,208–249` требует два независимых literal terms/phrase или technical term плюс второй term, native receipt, корректного owner и numbers. Q46 даёт только один term; Q16 не даёт подходящую contiguous phrase или technical anchor. **Private receipt ledger и точная внутренняя ветка None не записаны:** witness-объяснение реконструировано по коду; дополнительная более ранняя receipt rejection не исключена.
4. **Непосредственный admission-dependent read filter.** `domain/project_doc_ranking.py:205–225` отвергает без qualification/повторно вычисленной partial admission. Rank один не помогает. Публичная presentation использует этот filter в `application/_project_context_service_part01.py:156–175`; альтернативные compatibility hints не разрешают rescue (`domain/context_hint_policy.py:7–20`). Member read ещё полон, project/unified context уже пуст: это наблюдаемая граница потери. Два qualification наблюдения в одной call — не два независимых запуска.
5. **Operational veto приходит раньше projection.** `_project_context_service_shared.py:489–492` при пустом packet даёт no_reliable_context. `_project_context_service_part01.py:879–909` позволяет read packet без answer proof, но packet отсутствует. `interfaces/mcp/context_tools.py:358–384` проверяет canonical false delivery до projector; `application/model_visible_projection.py:466–494` возвращает blocked response. Поэтому `_docs_context_projection_core.py:271–305,677–695` и compaction не могут восстановить fact на этой call. Архивное `ranking:not_reached` относится к downstream projection наблюдению, **не доказывает отсутствие upstream project-doc reranking**.

## 4. Реально активный ranking / semantic scope

**На этой публичной локальной member границе активен SQLite lexical, не dense/reranker.** Это более сильное основание, чем наличие классов:

- `eval/main_flow_comparison/run_extra40.py:109–150` создаёт isolated LocalMemberService, делает настоящий `prepare_docs`, затем public dispatcher requests. `eval/evidence_quality_v2/runtime.py:74–93` очищает DOCATLAS env, ставит OFFLINE=1/AUTO_VECTORS=0, вызывает production factory. Оракулы не индексируются.
- `mcp/_docs_server_part01.py:61–63` → `core/config_resolution.py:72–98`: конфиг local member **отвергает non-SQLite или non-lexical** (`:93–94`). `application/project_docs_member_transaction.py:312` также ограничивает local member sync. Следовательно попытка «просто включить existing dense» здесь не изолированный B1 и не доступная zero-patch замена ranking.
- Native read берёт `retrieval.default_mode` в `_project_docs_service_part03.py:174–202`; dispatcher lexical branch — `retrieval/_dispatch_part01.py:153–169`. Store использует active generation, metadata filters, FTS5 BM25 weights `(6,2,.5)`, literal AND и OR fallback/union (`core/_sqlite_store_part03.py:480–562`). Raw Q46/Q16 непосредственно записывают `candidate_lexical_match.mode=or_fallback`, BM25 costs `-3.629974513082237` / `-12.62564163158336`; это observed acquisition evidence, не neural scores.
- Далее lane round-robin (`application/context_selection.py:170–178`), qualified-first stable ordering (`_project_docs_service_part03.py:40–50,314–335`), packing/dedup и retained-admitted exemptions (`:340–416`). Project ranking (`domain/project_doc_ranking.py:160–170,226–247`) сортирует base score, затем отдаёт предпочтение ещё не покрытым public query IDs и применяет source diversity. `source_weight_for_intent`/`source_requirement_boost` равны 1 (`:108–113`), topic guesses не дают authority. Qualifier `lexical_score=.8/1.0` в сохранённой trace не следует выдавать за raw BM25 cost или semantic probability.
- Dense/sparse/hybrid компоненты существуют для других настроек: dispatcher capabilities gate `retrieval/_dispatch_part01.py:145–151`, fan-out/fusion/hydration `:200–264`; `retrieval/dense.py:19–23` делает embedding query. **Их наличие не доказывает activation в этом архиве; activation здесь исключается local-member config boundary.** Расширение этой boundary означало бы отдельный scope/permissions/config/storage проект, не минимальный B1.
- `domain/question_semantic_frames.py:71–88` comparison/location/condition/premise/decision hooks возвращают None; `context_hint_policy.py:7–20` inert. Никакого обнаруженного live semantic admission witness, исправляющего Q46/Q16 при прежнем контракте, нет. Это не repository-wide impossibility proof.

## 5. Защитные условия отдельно от relevance

| Условие | Источник проверки | Что B1 НЕ меняет |
|---|---|---|
| Host project / scope / finite current catalog | `_project_docs_service_part03.py:128–143,455–501,532–541`; `literal_context_admission.py:258–281` | Только настоящий разрешённый original project read; без all/module/dependency расширения |
| Current generation, document/file hash, exact raw occurrence | `application/source_reference_evidence.py:130–205`; `domain/query_reference_binding.py:339–378`; `original_body_discovery.py:67–121` | Никакого доверия wire metadata, copied score или stale content; exact char/byte/line binding |
| Version/reference/explicit locator | `query_reference_binding.py:344–362,419–432` | Version mismatch/ambiguous or missing locator остаются rejection |
| Freshness/lifecycle/forbidden policy | `evidence_qualification.py:143–178,228–235` | Это не insufficient lexical-match fallback |
| Native original same-call receipt | `reference_query_tagging.py:36–68`; `original_body_discovery.py:124–149` | Lookup-only discovery, replay, derived probes не дают grant; finally deactivates state (`:31–64`) |
| Source owner integrity | `query_reference_binding.py:463–466`; `ordinary_body_context.py:225–238` | Проверка owner bytes и unresolved-name placement сохраняется |
| Explicit identity и numeric condition | `literal_context_admission.py:368`; `ordinary_body_context.py:239–244` | Не ослаблять missing-hard-exact и same-body numeric constraints |
| Consent/confirmation/operational veto | `context_tools.py:330–335,358–384`; `model_visible_projection.py:466–494`; `_project_context_service_part01.py:879–909` | Read не запускает bootstrap/network/sync; confirmation, stale, work/budget veto не обходятся |
| Final schema/hash/span/authority | `model_visible_projection.py:717–755,809–820`; `context_selection.py:324–378` | Snapshot equality/digest, source IDs, cite_only, no supported answer/edit guidance |

**Owner placement, hard-exact и numeric checks — не сами access grants.** Это identity/query constraints и консервативные admission boundaries. Сохранять их в B1 полезно, но не называть их semantic entailment. `evidence_policy_rejection_reason` один недостаточен: он не проверяет полный catalog/window/receipt. Correct hash тоже не relevance, sufficiency или correct answer.

Access/consent для LocalMemberService опираются на прежнюю host storage/prepare policy и operational decisions, а не на новое название «policy-valid». Существующие выбранные source/scope/hash controls не доказывают произвольный consent-denial или requested wrong-version сценарий. Такие claims не делать без raw public controls.

## 6. Минимальный изолированный B1: конкретный future patch

### Contract delta (нуждается в назначении/одобрении)

B0 остаётся точным default. Только в специально включённом отдельном host experiment B1 разрешает **source-policy-valid, native-original-acquired substantive body windows без прежнего two-term/phrase/whole-question topical witness**. Это candidates для той же host model, **не certified relevant/answer-supported sources**. Original question и lookups не меняются; qualification остаётся false, original coverage missing, read-only authority false. Сохранить hard-exact, numeric, structural owner и весь source-policy слой выше.

Предлагаемая activation: один host-controlled `DOCATLAS_EXPERIMENT_ADMISSION=policy_candidates_v1`, захватываемый **на входе eligible synchronous handler** в existing call-local `_BodyRead`; не новый public argument, registry/config system и не wire candidate flag. Scope ещё уже существующего receipt eligibility: original local project, без module/library/maintenance/patch_context, на первом срезе **без explicit lookups**. Невключённый/неизвестный flag — B0. Захваченный режим не меняется посреди handler; nested scopes fresh, finally clears/closes; direct/private helper invocation вне scope не получает B1. Это предложенное имя, не существующая опция.

### Product file ownership для назначения A — ровно три файла

1. **`docmancer/docs/domain/original_body_discovery.py`** (`:19–64,143–149`): добавить captured experimental mode в private read scope и маленький active-scope getter. Использовать существующие eligible/local identity/finally ограничения; активация — отдельно от receipt, receipt всё равно обязателен.
2. **`docmancer/docs/domain/ordinary_body_context.py`** (`:208–249`, existing `_body_blocks :74–110`): отделить общие receipt/owner/unresolved/numeric/substantive-body eligibility checks от phrase/technical topical witness. Переиспользовать их в обычном B0 без изменения результата и в новом экспериментальном candidate witness. Для B1 нужен настоящий nonheading/nonlink/nonheader body block с substantive content; **не требовать второго match/phrase/anchor**. Это provenance/structural eligibility, явно `relevance_unassessed`, а не semantic witness. Возвращать binding + exact original block/span; retain whole acquired window как сейчас. No token/word dictionaries.
3. **`docmancer/docs/domain/literal_context_admission.py`** (`:285–297,365–384`): после тех же canonical checks/raw body window/missing-exact rejection сначала существующий ordinary lane; если он отсутствует и captured B1 active — новый candidate lane. Reuse existing admission carrier с отдельным честным reason `policy_valid_original_candidate_v1`, `coverage_credit=False` и source/window bindings. Не записывать qualified=True и не маскировать reason под literal topical proof.

Почему это минимально: existing tagger (`reference_query_tagging.py:107–113`) заносит carrier; read packing/retention (`_project_docs_service_part03.py:370–416`) его учитывает; project ranking (`project_doc_ranking.py:210–225`) и final projector (`_docs_context_projection_core.py:271–305,681–695`) **независимо пересчитывают тот же function** в одной active scope. Значит новый lane может пройти все три стадии без обхода delivery veto/alternate projector/private replay. Existing final validation допускает честный partial missing coverage, не требует квалифицировать каждый source (`context_selection.py:324–378`).

Не назначать A изменения `context_tools.py`, qualifier thresholds, retrieval/dense/storage, model_visible validator, joint compaction, frozen inputs или tests. При выявленном runtime несовместимом consumer остановиться и уточнить scope, а не расширять patch молча. Из статического анализа **не следует**, что три файла гарантированно дадут фактическую доставку или минимальные токены: есть downstream closure/recovery/selection и operational bounds.

### Public harness ownership — отдельный назначенный владелец, не A сейчас

- **`eval/main_flow_comparison/run_extra40.py`**: минимальный first-slice режим с exact unchanged IDs 16/46 без lookups; activate host B1 только **внутри** `isolated_service` around public calls, поскольку `runtime.py:85–89` удаляет inherited DOCATLAS env. Затем existing direct40 и archived28 retention audit без retries, как назначит координатор. Сохранять отдельный output dir/variant/activation receipt; не переписать исторические JSON. Не менять общий `runtime.py` ради flag и не мокать retrieval/validation. Новый mode не должен подменять default direct40 workload или frozen inputs.
- **`tests/test_project_context_quality_v2_protocol.py`**, только если это выбранная existing integration assembly boundary: reuse existing public negatives/positive data (`:466–629`) для записи B1 raw results по тем же исходным requests. **Не переписывать empty-source assertions ради зелёного B1.** B0 прежний gate сохраняется; B1 текущий контракт оценивается отдельно и может получить FAIL, при этом host correct refusal — отдельный EXPERIMENT_OUTCOME. G/координатор выбирают как выполнить measurement без дублирования workload и без новых unit names.
- CI workflow selectors остаются отдельным coordinator решением; нынешний `.github/workflows/main-flow-context-review.yml:37–57` уже выбирает public negatives/scope/hash и direct40. Сам A CI не запускает. Реальный host generation требует отдельно назначенного adapter/разрешения; текущий `run_extra40.py` измеряет delivery, а **не генерирует ответ**.

## 7. Negative oracle и неизбежный tradeoff

Прямо повторно проверенный raw `pytest/test_public_partial_context_pr0/qualification-review-proof.json`: `ordinary.payload.status=ok`, один source, answer/edit=false; `owner/numeric/compound/numeric_range/setext` — insufficient, без sources, authority false. Это архивный B0 positive-control плюс реальные refusals, не новый B1 result.

Existing OtherAPI request (`tests/test_project_context_quality_v2_protocol.py:498–501`) спрашивает packet delivery/recovery, но correct-owner source (`:478–481`) говорит только credentials/startup. Такое окно проходит owner/source eligibility, **не содержит нужного отношения**. При B1 оно может стать публичным candidate; прежние assertions `:615–621` тогда **CURRENT_CONTRACT FAIL**, даже если хост честно откажется. Это предсказанный контрактный риск, не свежий executed FAIL.

Отдельные unrelated-topic/compound expectations также могут быть нарушены source-valid candidate contract; нельзя обещать сохранить их empty sources после снятия topical veto. Numeric/hard-exact/body-format constraints сохраняем, но их runtime результат тоже UNVERIFIED. Нельзя «починить» relevance договором о правильном owner или принятием sources как поддержки ответа. В public payload `authority=source_of_truth` описывает catalog source, а не поддержку вопроса; host prompt обязан различать это.

ADR0003 `:39–66,68–98` требует literal witnesses и unrelated-empty controls. B1 — **явно отдельный experimental delta к этому accepted default**, не silent migration ADR. Решение о внедрении требует согласия владельца на extra irrelevant context либо более сильного relevance selector. Никакое source-policy нарушение (scope/version/hash/access/consent/generation) не является допустимым tradeoff.

## 8. Feasibility, blockers и один следующий шаг

**Feasible static:** existing active call-local admission hook может дать source-valid candidate lane и Q46/Q16 не нуждаются в extra retrieval/download/provider. На архиве их полные факты уже acquired; прежний native workload/ranking можно оставить. Но отсутствие архивного private ledger не позволяет заранее сертифицировать, что все B1 receipts действительно будут minted, а downstream output fidelity и реальная host adequacy требуют public run.

**Blockers:**

1. Нет назначения трёх product files/experimental activation и явного contract delta; сейчас только report-only.
2. Local runtime запрещён; coordinator должен назначить разрешённый exact-SHA public integration запуск, без запуска A и без stale CI credit.
3. Реальная фиксированная host model/prompt/generation settings и разрешение corpus transmission/inference пока не предоставлены A. «Good prompt достаточен» — NOT RUN.
4. Нужно заранее выбрать допустимый operational candidate bound/selection; не подкрутить threshold/k на Q46. Предложение сохраняет existing acquired pool/work bounds, не создаёт 3-source/800-token потолок. Candidate pool may grow at representation delivery, это измеряется; одинаковый pool для B1/R1–R5 надо снять **до topical filter** и сохранять exact source spans, а не извлекать из B0 пустых public sources.
5. Диагностика ограничена (`_project_docs_diagnostics.py:10,63–107`); получить все acquired/policy-valid IDs и omission counts в разрешённом run, если >32. Сохранённые 20/22 qualification rows Q46/Q16 не являются полной непоказанной initial pool. Новое instrumentation — только после доказанного пробела; не требуется сейчас менять product diagnostic файлы.

Минимальный следующий шаг: координатор назначает A перечисленные **три** domain files и **экспериментальный-only** contract delta; G до patch фиксирует negatives и dual verdict; отдельный владелец harness подготавливает existing public first slice (Q46/Q16 + existing negative/source controls). Затем один разрешённый exact-SHA public smoke. При запрещённом runtime дальше только NOT RUN, не offline helper benchmark вместо public integration.

После smoke сравнивать unchanged old10/direct40, отдельно прежние 28 successes, delivered facts/source fidelity/irrelevant context, реальные host ответы/citations и суммарную стоимость. B1 не имеет заранее объявленного PASS и не рекомендует release/default migration до этих результатов.

## Проверки и граница отчёта

Выполнены только git identity/status/stat diff, text reads/grep, Python standard-library JSON/Unicode/hash inspection без product imports. Первое data-only inspection завершилось TypeError при попытке трактовать preview dict/null как list; исправленный selector проверил `context_windows.count/items/omitted`. Это tooling data-inspection error, не product runtime error; никакие данные не изменены. Запрещённые действия не выполнялись. Итоговый артефакт: `/tmp/opencode/docatlas-review-evidence/admission-full-20261012/A_PIPELINE.md`.

## 9. Implementation receipt после явного назначения (2026-10-12)

### Разрешение и текущий verdict

Координатор передал обновление владельца: лимит 0.6B отменён, isolated local runtime/install/download разрешены для эксперимента; frozen inputs, unit additions, default deployment не разрешены. **A получил ровно три repo-файла из предложения**; до готовности shared environment продукт не запускать. G должен просмотреть diff до runtime. Поэтому эта стадия — implementation + static review preparation, **не runtime PASS**. No commits/CI/install/download/product imports/AST/pytest/inference. Прочитаны `G_ORACLE.md` и `G_FROZEN_ORACLE.json`; frozen criteria не изменены, evaluation-only probes не использовались для настройки реализации.

### Реализованный diff

Base HEAD остаётся `4849b8f796d9e3e25e2c49e58562ec6859978411`; working tree до patch был clean. Изменены только:

1. `docmancer/docs/domain/original_body_discovery.py`: `:19–27` новое private `_BodyRead.experiment_admission`; `:55–64` host-флаг `DOCATLAS_EXPERIMENT_ADMISSION=policy_candidates_v1` захватывается один раз при входе eligible handler и только без explicit lookups. `:75–79` getter требует active public read scope. Существующие root/project/module/library/maintenance/context_format ограничения, receipt material и finally deactivation/clear не изменены. Неизвестное/отсутствующее значение flag ничего не включает; copied context после выхода inactive, nested handler создаёт fresh state.
2. `docmancer/docs/domain/ordinary_body_context.py`: `:208–239` исходные native receipt, owner/unresolved-name и same-block numeric checks вынесены в общий generator **без ослабления условий**. `:242–260` обычный lane вычисляет те же phrase/technical witnesses в прежнем порядке, возвращая тот же dict. `:263–288` experimental candidate lane требует active host flag, затем те же общие eligibility checks и реальное structural body content после прежнего masking. Он не требует topical phrase/second term; возвращает точный raw source block text/span, private native binding и честное `relevance_unassessed=True`, kind `policy_valid_original_candidate_v1`.
3. `docmancer/docs/domain/literal_context_admission.py`: `:373–381` новый fallback **только после неудачи обычного ordinary witness**, после существующих canonical source/reference checks, raw-window checks и `missing_exact_terms` rejection (`:371`). Carrier/whole acquired-window provenance сохраняются; `coverage_credit=False`, failed qualification и original missing coverage не меняются. Новая reason — не прежняя literal topical proof. Tagger/ranking/projector consumers используют этот same-call function без изменений и без bypass delivery veto.

Diff size: **3 files, 78 insertions(+), 18 deletions(-)**. `git diff --check` завершился без замечаний; это только whitespace/text diff check, не syntax/runtime verification. Default byte behavior **предусмотрен кодовым сохранением old branch**, но пока не проверен public B0 byte-for-byte runtime сравнением. Честный verdict до G/run: **implemented ADAPTED experiment, NOT RUN**.

### Exact text identity перед G review

| Repo file | SHA-256 текущих bytes |
|---|---|
| `docmancer/docs/domain/original_body_discovery.py` | `b80209618be43b78bd501abde5e77a04f09e5a26cb4b0e52840ebec8f14ffc14` |
| `docmancer/docs/domain/ordinary_body_context.py` | `b069de048f7ae4d3e64b87710a0c709671f0e3e47f4d5e3da12d10dd37c5eedb` |
| `docmancer/docs/domain/literal_context_admission.py` | `324d4e9994d539f5938ac614543f5ebdfbdd0ce6a5b95649a3fdc94bc75e3cc9` |

SHA-256 exact stdout `git diff --` по этим трём файлам (в порядке discovery, ordinary, literal): `bc30cc6a0216988b91be205d979642fb88f5182d90d7081ef5c615a3182f2317` (Git фактически печатает tracked paths в своём сортированном порядке). Diff воспроизводим от указанного HEAD без отдельного созданного patch-файла; review через `git diff -- docmancer/docs/domain/original_body_discovery.py docmancer/docs/domain/ordinary_body_context.py docmancer/docs/domain/literal_context_admission.py`.

### Граница experiment и следующие проверки

Эксперимент **может выдать unrelated source-valid candidates** и получить CURRENT_CONTRACT FAIL по прежним empty-source negatives. Это явно одобренная экспериментальная contract delta, не production acceptance. Source-policy/owner/numeric/hard-exact и false answer/edit authority остаются обязательными независимо от этого tradeoff. Новая private witness text не превращает candidate в semantic support; public source schema/validators и operational veto не менялись.

Harness принадлежит другим workers и находится вне repo: A не менял `run_extra40.py`, tests, workflows, frozen corpus/questions, oracle, storage/retrieval/projector или authority flags. Для activation harness должен установить host env **после входа в isolated_service**, поскольку тот очищает inherited DOCATLAS env. B0 flag absent/unknown и lookup requests сохраняют default lane. Предлагаемый next handoff: G проверяет exact diff; координатор готовит shared environment/назначает public runtime и сравнение default B0 bytes, Q46/Q16 фактов, negative dual verdict, source-policy и read-only state. Сам A до такого назначения не запускает продукт.

## 10. Actual runtime checkpoint и Q31 final trace (после review G)

Источники независимого verdict: `G_B1_STATIC_REVIEW.md`, `G_RUNTIME_REVIEW.md:27–67`, `G_RUNTIME_DATA_AUDIT.json`, `G_DEFAULT_OFF_AUDIT.json`, `G_B1_CONTROLS_AUDIT.json`. **A не выставляет своему patch runtime PASS и не исполнял продукт.** Разрешённые executions выполнены координатором/shared harness; текущая задача A — только bounded saved-data/code trace.

- G подтвердил default-off normalized public parity всех40, без differing IDs, и 10 control PASS. Это равенство content/path/line/scope/version/status/authority при независимой проверке каждой lineage, **не буквальная byte equality runtime-local IDs/digests между isolated projects**.
- G independently audited combined B1 **39/40**, Q46/Q16 факты полные, все archived28 сохранены; old10 **10/10**. Combined40 — assembly первых24 persisted rows и16 recovery rows на двух preparations/generations, не одна uninterrupted attempt. Lost/interrupted работы учитываются отдельно (`G_RUNTIME_REVIEW.md:35–46`), не скрытый best-of.
- Четыре отдельных старых negatives CURRENT_CONTRACT FAIL: OtherAPI, compound, Setext-heading/generic-body, quantum unrelated. Numeric7/range7-9 остаются empty, scope controls не наблюдают widen, captured read source/catalog/generation states unchanged. Это ограниченная public evidence, **не universal access/consent/version PASS** и не default recommendation.
- В reviewed host checkpoint G подтвердил source-supported Q46 answer, но Q16 семантически верен при **FAIL exact-quote citation**; sufficiency и fact delivery не равны strict generator acceptance. Этот отчёт не пересматривает subsequent model outcomes, не запускает model calls и не делает финальный методический ranking.
- Три product-файла сохранили hashes раздела 9. `run_extra40.py` теперь изменён отдельным владельцем для bounded recovery; A не изменял его и не отменяет чужую работу. Product default flag по-прежнему off; default deployment не выполнялся.

**Оставшийся Q31:** отдельный `/tmp/opencode/docatlas-review-evidence/admission-full-20261012/A_Q31_REMAINING.md` независимо проверяет raw `.results[id=31]` в `B1_COMBINED40.json`, source windows/hashes и точные code lines. Факт `[3980,4070)` acquired совместно окнами `[3770,4000)` и `[4000,4198)`; admission null, downstream context пуст, delivery veto до projection наблюдаемы. Статически достаточный blocker — сохранённый unresolved-name guard: bare query `HumanEval` не равен цельному source term `HumanEval/LeetCode`; slash-prefix не разрешён, underscore-prefix exception неприменим. Canonical hard-exact=[]/missing_exact=[], numeric query terms отсутствуют; это не numeric/hard-exact denial и не полный retrieval-missing.

Private receipt/internal None branch в Q31 raw не записаны: конкретный unresolved guard — source reconstruction, не якобы наблюдённый return trace. Никакого guard relaxation/question rewrite/retry ради40/40. Новая implementation/runtime/model работа не авторизована и не выполнялась. Итог: **39/40 доставленных фактов с явным оставшимся lexical owner/identity limitation**, не «всё исправлено».

# Step10: checkpoint исполнения

## Итог 2026-11-07: поисковые пояснения не дали прироста

Два Astra Low выполнили bounded experiment: opt-in source-bound descriptions
в ingestion и отдельная source-only подготовка21описания для6документов.
Parent провёл единое итоговое review:440code hashes,7-file diff из BEFORE,
источники/вопросы/facts и все8raw A/B packets независимо сверены.
Integration2PASS после сохранённых setupERROR и wiringFAIL; один A/B run.
Покрытие10/19→10/19; candidates37→38; source bytes7204→7376;
полные сохранённые JSON bytes292250→336928. Полнота/экономия не достигнуты.
Это lexical acquisition, не final delivery/Qwen/hybrid/Terra: API не применяет
переданные limit/budget. Пояснения участвуют в существующем routing field,
metadata видна Python-клиенту. Генерация — harness artifact, не production service.
Принимается только opt-in implementation/отрицательный development result.
Review: `eval/blind_project_context/step10-index-descriptions/PARENT_REVIEW_RU.md`.
Новый rollout/следующий runtime не разрешён этим результатом; прежние FAIL/BLOCKED
не меняются. Далее возможен отдельный design целостного локального контекста.

## Выполняется 2026-11-07: Astra Low, поисковые пояснения

Владелец поручил реализацию первого эксперимента через Astra Low, анализ и одно
итоговое review — родителю. Parent разрешил opt-in source-bound descriptions и
изолированный development A/B на шести доступных документах Meridian через
публичный ingestion + lexical retrieval. Четыре исходных вопроса и19facts
зафиксированы до результатов, проверены по оригиналам; это seen development.
Отдельный Astra Low готовит descriptions только по исходникам, не читая вопросы.
Направление и ограниченный runtime budget:
`eval/blind_project_context/step10-index-descriptions/PARENT_DIRECTION_RU.md`.
Проверка относится к lexical retrieval, не к hybrid/Qwen/Terra. Прежние
FAIL/BLOCKED сохраняются; окончательное качество нового варианта ещё не оценено.

## Актуальный фокус 2026-11-07: анализ подготовки при индексации

После обсуждения владельцу не понравилось направление relation classifier,
описанное ниже; продолжать его по прежнему design review не следует.
По новому запросу выполнен анализ существующего ingestion/chunking и публичного
подхода Context7: `v2plan/STEP10_INDEX_PREPARATION_ANALYSIS_RU.md`.
Предпочтительный небольшой предмет нового design — индивидуальные поисковые
пояснения к существующим source-exact фрагментам с отдельной проверкой candidate
retrieval и final selection. Это не исправление frozen Qwen FAIL: погодный раздел
уже участвовал в complete scan с document/incoming-reference контекстом.
Новый алгоритм не выбран владельцем; implementation, переиндексация, model calls
и Terra не разрешены. Ниже сохранена история предыдущих решений и результатов.

## Следующий design: task-and-delivered-claim dependencies

По запросу владельца Astra Low подготовил отдельный design:
`eval/blind_project_context/step10-dependency-roles-design/DESIGN_RU.md`.
Родитель принял направление с уточнениями в `PARENT_REVIEW_RU.md` той же папки.
Предлагается новый, ещё не проверенный relation component: REQUIRED/NONBINDING/
UNKNOWN на occurrence. Пропуск только при отсутствии зависимости и задачи,
и смысла уже выданного утверждения; UNKNOWN сохраняет полный доступный target
или даёт incomplete. Roles/TOC/keywords/relevance не разрешают автоматический skip.
Это явное изменение reference-completeness контракта, не восстановленный PASSv3.

До implementation нужен capability package: model/runtime proposal без загрузки,
exact resolved/source-only inputs, independent oracle, parser feasibility,
holdout specification и bounded call budget. Code labels/occurrence extraction
остаются отдельным parser blocker. Ошибочный NONBINDING на REQUIRED/UNKNOWN —
FAIL даже при случайно спасённом другом seed тексте; alwaysUNKNOWN не доказывает
способность различать ссылки. Production/inference пока не разрешены.
Старые24tasks nowseen, historicalFAIL/v3blocked сохранены. Terra/L2 заблокированы.

## Итог parent review v3: PRE-INFERENCE BLOCKED подтверждён

Итоговый manifest `b5b955b82a930dda810cdbffdf27fb3350f33065c6f0eb4f7a2f916d5e76d817`
проверен родителем:54entries совпали,39новыхfacts source-exact, прежние16tasks
не изменены,6-file implementation.diff точно совпал с BEFORE/current bytes.
Прочитан diff; выявлен также обход delivery size guard в новом early refusal path.
Главный blocker уже доказан исходниками: required OTel sections требуют TOCs,
которые транзитивно включают unavailable dependencies. Ни один threshold не
может дать одновременно required coverage и complete-dependency result в
текущем scope. Это ограничение design, не новый scored FAIL.
Freeze/calibration/validation не разрешены, бюджет0public/model calls.
Для продолжения требуется отдельный product-contract design по различению
обязательных зависимостей и навигационных/справочных ссылок; он ещё не принят.
Полный review: `v2plan/STEP10_REFERENCE_CLOSURE_SOURCE_REVIEW_RU.md`.

## Parent source review v3: найден feasibility blocker до inference

Подготовлены draft8 questions и independent graph на OTel/Rust Embedded Book.
Родитель сверил12local provenance entries и25literal fact-spans: расхождений нет.
Но оглавления в OTel ancestor bodies по принятому правилу раскрывают документы,
включая ссылки за пределы checked collection. До freeze требуется явный verdict
по navigation amplification и delivered dependency gaps; это ещё не runtime FAIL.
Также возвращены замечания к полноте semantic obligations нового holdout.
Подробности и hashes проверенного draft:
`v2plan/STEP10_REFERENCE_CLOSURE_SOURCE_REVIEW_RU.md`.
Astra Low завершает checkpoint с учётом review; model/runtime calls не разрешены.
Production diff review ещё не завершён; T01/Terra остаются заблокированы.

## Следующая версия: полный extent явных dependencies, preparation разрешена

После review revision1 родитель отверг role-based игнорирование ancestor links
и ownbody-only для ссылок на раздел с детьми. Принята revision2:
`eval/blind_project_context/step10-reference-closure-design/REVISION_2_RU.md`.
Semantic seeds включают ownbody+ancestors; все фактически delivered bodies
раскрывают явные ссылки на полный author-defined section/document extent.
Target score не удаляет dependency; children/definition-owner links сохраняются.
Scope/qualification, cycles/dedup и explicit gaps обязательны. Возможен рост до
всего reachable corpus; тогда reduction FAIL, без cropping/top-k.

Astra Low разрешены отдельная versioned implementation/evaluator и подготовка
нового8question real-source holdout с pinned official raw docs. Приоритет
authored Markdown без нового parser/конверсии; source downloads разрешены,
model inference/downloads/runtime tests пока нет. Existing scorer inputs/math,
capability lifecycle и historical618files semantics/results сохраняются через
отдельную revision+BEFORE snapshots. Parent review кода/источников/labels перед
freeze. Current synthetic validation FAIL неизменен; T01/Terra не разрешены.

## Последний gate: Qwen structural v2 validation FAIL подтверждён родителем

Первая и единственная validation8 завершена:22/24required units,38/41facts.
V-M1 потерял `weather.md#Suspension` и его intro: три обязательных факта о
wind interlock, сохранении identifiers и restart approval отсутствуют в packet.
Transfer содержит ссылку, но target score0.4378235042 ниже tau0.8670357466;
structural v2 не делает anchor closure. Это semantic coverage failure на complete
scan, не capability bug/overflow. Parent independently проверил raw packets,
source spans/hash/scope, facts, counts и readonly; runtime не повторялся.

2/2noanswer и hardnegative0 прошли.1069/4056source tokens,73.64% reduction
пересчитаны родителем, но не компенсируют required FAIL.176forwards/75136Qwen
input tokens,2prepares/8queries/8reads;618bound hashes неизменны.
Отчёт `eval/blind_project_context/step10-qwen-validation/RESULTS_RU.md`.

Frozen experiment остаётся FAIL/default off. T01/installed/Terra/L2 заблокированы;
provider-token экономия не доказана. Ранее принятые fit-window/client/capability
corrections сохраняют свои узкие доказанные границы и не превращают quality вPASS.
Все текущие Qwen runs вместе со smoke:714forwards/310091input tokens; это стоимость
локального scorer, не Terra/provider tokens.

Astra Low поручен следующий **design-only** checkpoint зависимости/closure:
own-body anchor obligations против повторного unary relevance gate, без subtree
раздувания/словарей/top-k. Current16cases теперь seen regression; для нового
эксперимента понадобится отдельный pre-frozen holdout. Ни новой implementation,
ни inference, ни retuning/переписывания текущей validation не разрешено.

## Текущий результат: recovery PASS принят; validation разрешена

Родитель независимо проверил8actual final packets по исходникам:24/24required
units,40/40facts,2/2complete empty noanswer,0hardnegatives. Source metric пересчитан
из raw delivered intervals:961/4272tokens,77.50% reduction.176forwards/76022Qwen
tokens,2prepares/8queries/8reads; readonly audits и618bound hashes неизменны.
Это fresh-prepared synthetic public recovery PASS, не exact historical replay
и не provider-token экономия. Исторический calibration ERROR сохраняется.

Recovery summary SHA256:
`93f8f93787c0c4a50a424d22295c2ed85a94df6cc73d7e349ef1ccde6da08604`.
Родитель создал `step10-qwen-recovery-entry/parent-validation-authorization.json`
относительно eval/blind_project_context и разрешил первый однократный validation
run8Meridian/Cairn questions с теми же manifest2bcebef…/policy16fb92…/threshold.
Никаких refit/retry/правок критериев. T01/installed/Terra/L2 ещё не разрешены.

## Текущий run: fresh-prepared recovery разрешён

Родитель принял runner-only extension по diff и618hashes. Новый manifest frozen:
`eval/blind_project_context/step10-qwen-recovery-entry/recovery-freeze-ready-manifest.json`,
SHA256 `2bcebef52ab6268e091f5e28de12acc8837988bff36c2068432e2a4b73ebe066`.
Отдельное разрешение `parent-recovery-authorization.json` в том же каталоге.
Предыдущий draft369534… сохранён. Astra Low выполняет один recovery run:
2prepares/8final-policy queries, прежняя policy16fb92…/threshold, без fitter.
Resource checks и все фактические критерии неизменны. FAIL/ERROR — остановка;
validation/T01/installed/Terra/L2 пока не разрешены.

## Актуальный шаг: capability correction принята, готовится recovery gate

Родитель независимо проверил exact3-file diff/BEFORE hashes и raw public
regression: fresh C-T3 после consumption получает V!=U, active alias reuse
даёт literal same packet, U/V повторно unavailable; C-T3 обязательные факты,
источники/span/hash/scope/version сохранены.2continuation reads дают исходный
Capacity section. Read-only receipts совпадают.1prepare/3queries/5reads,
63forwards/28536tokens; existing legacy integration test1passed, две setup failures
сохранены. Expiry/atomic-fault branches — только code review.

Correction принята в этой границе; исторический calibration ERROR не исправлен
задним числом. Astra Low готовит минимальный evaluator command recovery и новый
manifest:8final-policy questions на fresh-prepared calibration projects, прежние
policy bytes/tau, без diagnostic8/fitter. Источники/вопросы/expectedfacts/критерии
не меняются. Новый run и validation пока ждут короткого parent entry/manifest review.

## Текущая correction: spent capability renewal

Targeted public reproduction подтвердил причину C-T3: после consumption
Retention URI `issue` получает spent URI и возвращает None, `_bind_atomic`
бросает `source_reference_rejected`, конечный packet body-free refusal.
Родитель сверил raw call/return/exception trace с frozen control flow.
Driver завершился ERROR из-за неправильного assert номера return line (CPython
сообщил95 при выходе из with вместо99); этот artifact не переписан в PASS.
Дополнительная работа:1prepare/2queries/2reads,42forwards/19076tokens.

Astra Low разрешена минимальная capability lifecycle correction: fresh qualified
query может получить новый URI, consumed/expired старый URI остаётся unavailable;
rebind/replay не получает renewal. Atomic staging/remap/post-remap pricing и
authorization сохраняются. Scorer/threshold/data не меняются. Разрешён scoped
public regression и один существующий legacy replay integration test.
Исторический frozen manifest/policy/results сохраняются; после correction нужен
новый reviewed manifest. Новый calibration/validation пока не разрешён.

Provenance limitation установлена родителем: historical calibration SQLite temp
stores уже удалены; incoming source identity включает random generation UUID.
Новый prepare даже при том же root не гарантирует exact model-input hashes.
Дальнейший gate следует обозначать fresh-prepared acceptance с прежним threshold,
а не точный replay; вручную восстанавливать/подменять generation недопустимо.

## Последний результат: calibration ERROR_NOT_PASS

Один разрешённый Qwen calibration run остановился без повторов.8diagnostic
queries дали frozen fit tau `0.8670357465744019`, predicted source reduction
961/4272tokens (77.50%). Реальный final replay: C-T1/C-T2 сохранили все обязательные
факты; C-T3 — body-free `source_reference_batch_rejected`. Остальные5final queries
не выполнялись. **Calibration PASS нет;77.50% — offline prediction, не итоговая
экономия final split или Terra.**

Работа run-01:2prepares,11queries,4resource reads,239forwards/104524input tokens,
0lost traces. Родитель независимо сверил534frozen hashes, сумму11work receipts,
largest required-preserving breakpoint, факты/spans/hash C-T1/C-T2 и3read-only
receipts. Исторический ERROR сохранён. Источники/labels/prompt/policy не менялись.

Offline hypothesis: после consumption одноразового Retention URI новая query
пытается выдать тот же deterministic URI, и atomic binding отвергает batch.
Exact runtime branch пока не доказана. Astra Low разрешён отдельный targeted
reproduction:1prepare,2queries C-T1→resource read/replay→C-T3 и passive trace;
без изменения534bound files и без нового calibration run. Требуется concrete
fix design с сохранением spent старых URI и fresh authorized issuance.
Validation/T01/Terra/L2 не разрешены. Отчёт:
`eval/blind_project_context/step10-qwen-calibration/RESULTS_RU.md`.

## Текущий шаг: frozen Qwen calibration

Родитель принял R3/R4 по коду и raw preflight:2prepares+3queries,
16forwards/6608tokens; exact OFF/ON packet parity, source/catalog/DB/assets
read-only receipts PASS. Overflow35263tokens → явный scan_incomplete,
0forwards; успешный32K forward этим не доказан.

Frozen approved manifest:
`eval/blind_project_context/step10-multidoc-gate/freeze-ready-manifest.json`,
SHA256 `87585ea10a1c0a4e6673020368ad51ee0e64bdd9ca3d6de4ca8ddce86a34046a`.
534 bound hashes проверены, sources/questions/labels/input recipe неизменны;
прежний candidate сохранён. Astra Low разрешён один calibration run:
8diagnostic questions и8real final replay только при fit PASS. При FAIL/ERROR —
сохранение evidence и остановка. Validation/T01/Terra/L2 ещё не разрешены.
Ни качество semantic selection, ни provider-token экономия пока не доказаны.
Ниже сохранена история checkpoint до этого разрешения.

## Актуальное продолжение: correction принят, открытый scorer на design review

2026-11-06. По поручению владельца работает Astra Low под родительским контролем.
Новая opt-in `complete-fit-first-maxp-v4` исправляет лишнее разбиение полностью
помещающихся пар; historical recipes/policies сохранены. Public diagnostic:
26→11 model pairs, точные исходные spans/hash и хвостовое условие сохранены.
Это не semantic acceptance и не доказательство экономии provider tokens.

Родитель вернул R1 (безусловная запись подробных intervals) и R2 (перезапись
старого plan новой provenance), затем принял исправления по diff и raw artifacts:
OFF/ON packets/scores совпадают, по11 pairs; два CLI refusal сохранили sentinels,
session/model subprocesses отсутствуют. Повторного родительского inference нет.
Отчёт: `eval/blind_project_context/step10-review-corrections/RESULTS_RU.md`.

Клиентский transport probe установил: OpenCode2.2.5 positional CLI добавлял
кавычки уже в user message, до Terra. CLI stdin сохраняет точный вопрос;
runner исправлен. 3 scripted-provider requests,0 Terra calls. Исторический
exact-question FAIL сохраняется; обвинение answering model опровергнуто.

EXIT заблокирован gated Gemma weights. Владелец выбрал открытую модель;
родитель принял предложенный Qwen3-Reranker-0.6B для одного opt-in эксперимента
после проверки pinned model card и дизайна. Multilingual/custom instruction/32K
подтверждены карточкой; качество target/full-doc/incoming-context recipe неизвестно.
Новый synthetic gate:4 проекта/28 документов/16 вопросов, ещё draft.
Родитель потребовал исправить semantic labels полезных ограничений, ошибочно
помеченных hard negatives, до freeze/inference. Full-section и anchor dependency
policy приняты как проверяемая гипотеза: каждый body оценивается отдельно,
seed/anchor не расширяют subtree, обязательные дети/условия проверяются конечной
выдачей. Rev2 исправила основные labels; родитель нашёл остаточные полезные
ограничения среди обычных negatives и поручил завершить review до freeze.
Astra Low реализует отдельную recipe/structural policy и project evaluator;
calibration/validation/T01 ждут родительского review diff/final labels/manifest.
Новые semantic/installed/Terra PASS не получены.
Implementation checkpoint Qwen получен: родитель сверил506 hashes и неизменность
28sources/16questions/81facts/requiredunits/hardnegatives; rev3 labels приняты.
Official-card smoke:2forwards/189tokens, только короткие пары. Review вернул
R3 (сохранение model-work receipt при post-scoring failures) и R4 (сохранённые
source/DB/model-assets read-only receipts). Разрешён bounded public preflight
на отдельном existing structural fixture: OFF/ON и oversized-source отказ,
план2prepares+3queries. Gate inference ещё не разрешён.
Default off; полная L2/Terra-серия остаётся заблокированной quality gates.
Подробный статус: `v2plan/STEP10_ASTRA_REVIEW_RU.md`.

## Последняя диагностика: доказательный аудит отбора

По запросу владельца сверены статьи, план, код и реальные same-call scores.
Два installed in-process public вызова воспроизвели V3 original T01 34→72 rows,
0/3 facts и V1 historical renewed request 152→157 rows,3/3 facts. PR-блок имеет
rank82/score−5.191558 в первом и rank126/score−5.307424 во втором.
Независимый HF model-card контроль воспроизвёл score: короткий PR не обрезан,
ошибки encoding на нём нет. Плохое ранжирование и усиление через subtree доказаны.
V1 calibration objective несовместим с пустым no-answer на сохранённых scores;
calibration/validation однодокументные. Также найдено расхождение §5.3 плана:
11 помещающихся units в renewed разбиты на лишние окна из-за ancestor pcap//3.
Его влияние на false positives отдельно не измерено. Production/policy не менялись.
Исправлены прежние недоказанные объяснения про MaxP и обязательность novelty gate.
2 public calls,2298 model pairs +8 direct control pairs,0 Terra calls. Ошибка
диагностического assert про module scope исправлена offline, inference не повторён.
Полный разбор и артефакты:
`eval/blind_project_context/step10-selection-audit/RESULTS_RU.md`.
Default off; проблема качества остаётся открытой.

## Последнее продолжение: closure-aware V3

Реализован schema2 `final-closure-all-useful-breakpoints-v3`: наибольший
observed calibration threshold с полным final-closure retention. Scorer V2 и
структурные правила неизменны; direct retention — метрика. Старые V1/V2 не
переписаны. Tau−3.352724552, policy5683d27c…, wheel9b95d287….
6 prepare +24 public query,16 real scoring executions +8 exact memo replays,
52 closure replays без повторного inference по порогам. Calibration20/20 facts;
новая заранее frozen validation27/27 facts,19/19 useful units,2/2 empty noanswer.
Однако installed L0 originalT01:0/3; original+полный перевод:0/3. Оба выдают
72 блока без CONTRIBUTING.md. Это новый concrete transfer blocker; новый Terra
не запускался, отсутствуют новые provider-token результаты. Default off.
Отчёт: `eval/blind_project_context/step10-calibration-v3/RESULTS.md`.
Ниже остаётся предшествующая история реализации и оценок.

Актуальный статус: публичный opt-in full-acquisition/semantic/structural pipeline,
atomic refs, emergency50k и native client adapter реализованы. Независимая
validation: 14/14 фактов, но no-answer contamination — acceptance FAIL.
Measured wheel663e:16/46 facts против fresh file42/46, все8L2 cases censored.
Последующие dependency-preparation/URI-pricing исправления проверены public257
и installed T01: broad emergency1.18M tokens, focus3/3, trace/read-only parity.
Историческая повторная Terra оценка была блокирована provider429 usage_limit_reached.
Own-body-gated-v2 прошёл отдельный public calibration/validation run:22/22 facts,
но15/16 direct retention и1/2 no-answer contamination — acceptance FAIL.
Installed v2 wire positive control PASS; final wheel b8ecfb99….
После сообщения о восстановлении квоты выполнен один Terra L0/T01-ru на
wheel b8ecfb99 + frozen V1:3/3 фактов и цитат,111.57s,61419 input+cache
против file5247 (11.706×). Usage сверено по всем steps/session. Квота доступна.
152/157 units проходят relevance напрямую,157/157 доставлены после closure.
MCP question получает лишние кавычки — exact-question FAIL. Полный suite
не обоснован; relevance/no-answer остаются blocker, default выключен.
Детали и границы baseline reuse: `step10-agent-evaluation/renewed-results.md`
относительно каталога `eval/blind_project_context/`.
Default выключен. Работы и negative acceptance зафиксированы; статусы P0–P7,
точная команда blocker и hashes — в отчёте и связанных receipts.
Ниже сохранены исторические записи первого checkpoint, они не описывают
текущее состояние реализации. Актуальный фактический отчёт:
`eval/blind_project_context/STEP10_MINIMAL_CONTEXT_RU.md`.

## Зафиксированная база

- Git: `393082976d2e06b946e6ce6d12997d50d869f73d`.
- Ветка: `work/step9-gap-resolution`.
- До начала работы единственный незакоммиченный файл — план step10.
- Побайтно проверены оба wheel и все три frozen inputs из
  `eval/blind_project_context/step9-evidence/provenance.json`; хеши совпадают.
- Measured wheel: `aded302cff52c23a57b99411c725f48bbc7dfa43db1674539eb1a1d60f0132ae`.
- Final wheel: `99fe1ece2899e27b7fa09e92138ea9ccb38987a6d2d29cb36f2b1a0d35e0a9e3`.

## Найденные зависимости

1. `SQLiteStore.acquire_candidates` возвращает list и сохраняет deep copy в
   request memo. Простое удаление SQL LIMIT не создаёт потоковую обработку.
   Новый iterator требуется провести через consumers и отделить от legacy memo.
2. `original_body_read_scope` дополнительно ограничивает контекст переменной
   `DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS` через `min(..., delivery_token_ceiling())`.
   Это отдельная квота от `DOCATLAS_EXPERIMENT_DELIVERY_MAX_TOKENS`.
3. Исходный blind protocol уже содержит holdout. Не читать его подробности ради
   выбора нового threshold и не использовать его как calibration set.
4. Есть независимые предметные calibration labels:
   `reports/admission-experiments/admission-selection-v2/review/calibration_labels.json`.
   Они включают условия/исключения для seed bank и stage rigging. Прежнее
   назначение — выбор k. Для step10 требуется проверить исходный corpus,
   разметить полные structural units и пересчитать scores новой оконной recipe;
   старый threshold/receipt переносить нельзя.
5. Старый calibration command ссылается на
   `/tmp/opencode/docatlas-review-evidence/...`, отсутствующий в текущем списке
   `/tmp/opencode`. В `/home/viadmin/.cache` модель `model.safetensors` поиском
   не найдена. Это не доказательство отсутствия весов на всей машине.

## Следующие действия

- Найти либо явно подготовить pinned multilingual MiniLM assets.
- Проверить corpus/labels и отделённую validation для нового calibration artifact.
- Закончить audit consumers и P0, затем реализовать P1 через настоящий public path.
- Сохранить source/scope/hash/consent checks; 50k внедрять вместе с emergency
  semantics, а не заменой числа в старом budget selector.

## Исполнение 2026-11-06

- Добавлен `SQLiteStore.iter_scope_candidates`: полный filtered-generation
  keyset scan без lexical matching/memo/deepcopy, явный `scan_incomplete` при
  смене generation/прерывании. В public context consumers ещё не подключён.
- Добавлен `complete_context_scoring.py`: pinned MiniLM, raw MaxP, все окна
  original/translation/body/ancestor, batches без общей квоты. Не подключён
  к финальному public selection и не является source authorization.
- Pinned assets явно подготовлены в `/tmp/opencode/step10-mini-assets`;
  все 6 хешей совпали. Поддержанное окружение:
  `/tmp/opencode/step10-mini-py313` (torch 2.10.0+cpu, transformers 4.57.1).
- Один real-preparation storage integration: 257 документов, exact source
  facts, scope, read-only SHA, generation-change failure — **1 PASS, 2.82 s**.
  Diagnostic inventory обновлён для нового сценария.
- Собран/установлен wheel SHA-256
  `76c184d4e085b204aaa750b0430840f7a18f01ab252bc918dc5554980ce81341`.
- Installed scorer probe вне checkout: 18 calibration pairs + 60 long-input
  pairs, wall 5.475 s, CPU 28.505 s, max RSS 1,075,964 KiB.
  Receipt `/tmp/opencode/step10-scoring-probe.json`;
  diagnostic tau -3.053239107131958, **не deployable calibration**.
- Frozen source/question/oracle files не менялись; holdout details не
  использовались для настройки. Старые labels недостаточны для исчерпывающей
  structural-usefulness calibration и независимой validation.
- Реальный client, installed stdio новой policy и Terra-сессии не выполнены.
  Нового минимального public candidate/default нет. Pipeline/closure/emergency/
  refs/client migration остаются незавершёнными; это не завершение задания.

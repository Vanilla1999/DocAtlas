# Step10: контролируемое исполнение Astra Low и review

2026-11-06. Владелец поручил исполнение `openai/gpt-6-astra#low`, предварительный
инструктаж, контроль родительским агентом и последующее review.
Исполнитель: session `ses_e4e23311bffeDU5eDXIClQAk7d`.

## Актуальное поручение: dependency roles design после V3 blocker

Владелец разрешил пересмотреть правило обязательности ссылок. Astra Low создал
отдельный `step10-dependency-roles-design/DESIGN_RU.md`, без code/data/runtime
изменений. Parent review: `PARENT_REVIEW_RU.md` в той же eval папке.
Принят candidate contract task-and-delivered-claim completeness с отдельным
непроверенным relation component REQUIRED/NONBINDING/UNKNOWN. Новый механизм
не валидирован прежней unary Qwen policy и не имеет выбранной модели.
Нельзя убирать условия admitted claims из-за queryirrelevance или ролиancestor.
UNKNOWN консервативно покрывается полным target либо refusal; skips проверяются
независимо от finalfacts, чтобы redundantseeds не маскировали ошибку классификации.

Следующий этап ограничен preparation capability package и parent review; текущий
design не разрешает inference/downloads/training/production changes. Exact input
modes, source-backed oracle и parser feasibility обязательны до approval. Старые
24tasks seen, прежние FAIL/BLOCKED не переписываются. Calls на design этапе0.

## Выданное задание и checkpoints

1. Изучить AGENTS.md, доказательный аудит, исходный план и production-код;
   сначала обосновать подход, без изменений и inference. Выполнено.
2. Отдельная versioned fit-whole-pair correction, targeted public verification;
   feasibility опубликованного EXIT; многодокументные authored fixtures для review
   до inference. Correction принят после исправления R1/R2; semantic acceptance
   этим не доказан. Многодокументный набор остаётся draft.
3. После review: отдельная evidence/structural policy, если доступность модели и
   ресурсы подтверждены; frozen calibration/validation, затем installed gate.
4. Только после quality PASS: сопоставимый targeted Terra experiment.

Родитель проверил клиентскую передачу исходного вопроса; исполнитель применил
проверенный stdin correction. Historical scopes/recipes/artifacts не менять.

## Что родитель будет проверять в diff

- Старые recipes не получают новые model inputs через изменение default constant
  или общего helper. Старые policies не принимаются под новым именем recipe.
- Новая recipe явно участвует в policy binding, continuation fingerprint,
  диагностическом receipt и supported probe interfaces.
- Full-fit означает полную пару с special tokens, для каждой lane отдельно;
  ни вопрос, ни тело, ни ancestor не урезаются. В non-fit пути нет пропавшего хвоста.
- Model batch ограничивает память, а не candidate count. Полнота прохода и
  результат relevance не выводятся только из counters/exit 0.
- Публичный проверяющий получает факты из независимых исходников и сверяет
  delivered text/span/source/scope/hash и read-only state. Никакой подмены
  retrieval/selection/storage/validation.
- Новое subtree-поведение имеет отдельную policy. Узкий seed не разрешает весь
  корень; запрос полного раздела не теряет его дочерние требования.
- EXIT provenance включает base, adapter, tokenizer, prompt, label normalization,
  segmentation, dtype и overflow; английский training domain не называется
  доказанной поддержкой русских запросов. Gated access не обходится.
- Перевод не подменяет original question. Клиентская correction не снимает
  кавычки на сервере и не меняет вопрос ради PASS.
- Validation содержит конкурирующие документы в одном scope, hard negatives,
  условия/исключения, no-answer и обе языковые ситуации. Synthetic происхождение
  и пределы репрезентативности явно указаны.
- Порог не выбирается по T01 или validation; source reduction не равен экономии
  всего диалога. Все проваленные попытки и реально затраченные вызовы учтены.

## Исправление прежней атрибуции клиентской ошибки

Read-only GET `/api/session/ses_e4e64fcf0ffeDGGXiZi9TslFbt/message` показал, что
историческое user message `msg_1b19b03690012AMgFDVRIZBiWk` уже содержит буквальные
внешние двойные кавычки. Утверждение «Terra добавила кавычки» не подтверждается:
изменение возникло до answering model. Проверка настоящего клиента2.2.5 с
scripted local provider воспроизвела CLI positional FAIL, JSON API и CLI stdin PASS
как в persisted user text, так и в provider-bound request. Подробности:
`eval/blind_project_context/STEP10_CLIENT_QUESTION_RU.md`.

## Принятый review correction

- Fit-first V4: 26→11 model pairs в публичном диагностическом сценарии;
  полные исходные spans и хвостовое условие сохранены. Это экономия вычислений
  scorer в данном сценарии, не измерение provider tokens или semantic качества.
- R1: подробные интервалы opt-in. Новый public OFF/ON run: 1 prepare,
  2 queries, по 11 pairs; packets и scores совпадают, source/hash/scope/read-only
  проверки PASS. Родитель независимо сверил raw packets, scores, исходные
  spans/hash и факты offline, без повторного inference.
- R2: immutable plan guard до config writes/session calls. Два реальных CLI
  отказа сохранили sentinel bytes; родитель сверил hashes и execve traces:
  session/model subprocesses отсутствуют.
- Доказательства: `eval/blind_project_context/step10-review-corrections/RESULTS_RU.md`.
  Это принятие конкретных corrections, не итоговый PASS Step10.

## Выбор открытого scorer и review дизайна

Официальный EXIT заблокирован gated Gemma weights (401, локальный доступ не
найден). Владелец выбрал «Выбрать открытую модель». Astra Low поручен design
checkpoint открытого multilingual scorer. После проверки pinned official model
card и предложенного recipe родитель принял **Qwen/Qwen3-Reranker-0.6B**,
revision `e61197ed45024b0ed8a2d74b80b4d909f1255473`, для одного opt-in эксперимента.
Это instruction-aware passage reranker, не воспроизведение EXIT. Карточка
подтверждает multilingual/custom instruction/32K, но не качество нашей target
JSON recipe. Фактическое завершение download/provenance ещё ожидается от исполнителя.

Родительский pre-freeze review обнаружил полезные ограничения среди hard
negatives (C-L1 Display preference, V-M2 Forecast display и аналогичные
shortcut exclusions). Исполнителю поручено обосновать разделение обязательных
фактов, допустимых дополнительных/альтернативных witnesses и истинных negatives,
сохранив исходные вопросы/документы и историю draft. Наличие полезного дубля
не делает его обязательным для минимально достаточной выдачи.

Родитель прочитал все 24 project-documents и сверил rev1/rev2 tasks offline:
вопросы, 81 fact quotes и required units неизменны. Rev2 исправляет основные
ошибочные hard negatives. Найдены дополнительные supporting ограничения среди
обычных negatives: Loom Queue ownership/Raster pipeline и Meridian Planner.
До freeze поручено завершить их review и сохранить историю разметки. Неизученные
остаточные тела нельзя выдавать за доказанные false positives.

Принятый экспериментальный дизайн:
- каждый own-body оценивается отдельно с полным checked containing document и
  фиксированными прямыми incoming-reference contexts;
- seed и anchor не разрешают subtree; ancestors/definitions сохраняются;
- full-section children и linked conditions обязаны пройти конечные gates;
- полный prompt до32768 tokens; overflow/OOM означает incomplete, не truncation
  или успешный пустой ответ; query/source bytes не переписываются;
- largest calibration breakpoint с полным required final-obligation retention,
  затем unchanged noanswer/hard-negative/50% source reduction gates.

Astra Low поручены smallest production diff, project evaluator и freeze-ready
manifest. **Calibration/validation/T01 inference пока не разрешены**: сначала
родительское review кода, evaluator и окончательной разметки. Разрешён один
official-card feasibility smoke на двух опубликованных pairs, с отдельным
учётом вычислений. Его результат не заменяет quality gate.
Дизайн: `eval/blind_project_context/step10-open-scorer/DESIGN_CHECKPOINT_RU.md`.
Финальное review реализации, installed gates и Terra оценка ещё впереди.

## Review implementation checkpoint Qwen

**Актуализация:** R3/R4 приняты; родитель выполнил freeze и разрешил только
calibration (см. итог ниже). Описание замечаний далее сохранено как история review.

Прочитаны новые `context_evidence_scoring.py`, `context_evidence_structure.py`,
dispatch/schema3/config/structural v2, project runner и freeze-ready контракт.
Родитель независимо проверил все506 hashes review manifest. Rev3 сохраняет
28 sources и все16 task records, кроме согласованных optional_support additions;
81 facts, required units и hard negatives не менялись. Rev3 labels приняты:
остаточные непроверенные bodies явно unlabelled, а не доказанные false positives.

Фактический official-card smoke подтверждён raw receipt:2 forwards,189 input
tokens. Это только две короткие положительные опубликованные пары; ни новый
target/context prompt, ни32K, ни public execution этим не проверены.

Review вернул два пункта до freeze:
- **R3:** после успешного scorer исключение в closure могло вернуть stop packet
  без scoring receipt до observer append. Уже выполненные forwards могли исчезнуть
  из evaluator accounting. Требуется сохранение receipt независимо от terminal
  delivery verdict и учёт попыток/исключений без дублирования observations.
- **R4:** source/DB before/after digests runner сравнивал assertions, но не сохранял
  компактные raw receipts для родительской проверки. Поручено сохранить уже
  вычисленные значения, включая failure path и asset verification.

Разрешён ограниченный public preflight на существующем structural fixture:
OFF/ON parity и отдельный oversized-source отказ. План2prepares+3queries,
без gate sources/T01. Реальный overflow обязан быть scan_incomplete, не no-answer;
этот отказ не подтверждает успешный32K forward. Calibration/validation по-прежнему
ждут исправленного diff, raw diagnostic receipts и окончательного freeze.

## R3/R4 приняты; calibration разрешена

Родитель проверил исправленный control flow и raw preflight offline:
534 file hashes, unchanged sources/tasks/labels/recipe; literal OFF/ON packet
parity, exact source spans/hash/scope/facts/definitions; source/catalog/DB/assets
before/after receipts. Два work receipts суммируются в16forwards/6608tokens.
Overflow receipt совпадает в packet/observer: `evidence_prompt_overflow:35263`,
scan_incomplete,0forwards/0model-input tokens. Runtime не повторялся родителем.
Поздние ошибки после scorer проверены code review, не fault-injection runtime.

Родитель сохранил reviewed candidate в `step10-multidoc-gate/reviewed-candidate-r3-r4.json`
(SHA256 `02e4d074106ceaf3eb8514f72bfc14c56d01ad109cb0654243967770e54097bb`)
и отдельным approval изменил статус `freeze-ready-manifest.json` на
`FROZEN_APPROVED_FOR_INFERENCE`. File map и input contract неизменны.
**Approved manifest SHA256:**
`87585ea10a1c0a4e6673020368ad51ee0e64bdd9ca3d6de4ca8ddce86a34046a`.

Разрешён один calibration run:8 diagnostic questions → заранее frozen fit →
8 real final-policy queries только при fit gates PASS. Два public prepares;
все повторные forwards и resource reads учитываются. FAIL/ERROR сохраняется,
повтор/изменение bound inputs не разрешены. Validation, T01, installed/Terra/L2
требуют следующего review. Semantic acceptance пока не получен.

## Calibration run-01: родительское review отрицательного результата

Run завершился **ERROR_NOT_PASS**, не semantic PASS:8diagnostic calls, затем
2successful final calls и C-T3 `source_reference_batch_rejected`;5final calls
не выполнены. Родитель offline независимо сверил:
- 534bound hashes неизменны;
- 11raw work receipts суммируются в239forwards/104524tokens;
- tau0.8670357465744019 действительно largest required-preserving breakpoint по
  исходным score sets и independently assembled ancestor closure; следующий
  больший observed score теряет обязательство;
- predicted no-answer/hard-negative gates; actual C-T1/C-T2 facts/spans/hash/scope;
- 3source/catalog/DB/assets before/after receipts совпадают.

Reported961/4272source tokens (77.50%) относятся только к offline fit prediction;
full final calibration, validation и provider-token improvement не доказаны.
Policy SHA256 `16fb92b9687d68c30cdc8bfa8656b20d512da2b9b8600497ed78a0f5742d0f11`
не получила разрешения на validation. Родитель inference не повторял.

Предположительная причина технического отказа — повторная выдача deterministic
source capability после его consumption на C-T1. `issue()` отвергает spent URI,
а atomic binder прекращает весь packet; это согласуется с кодом/raw, но точная
runtime ветка ещё требует подтверждения. Исполнителю разрешён один отдельный
public reproduction с passive trace и подготовка минимального fix design.
Нельзя обнулить spent registry, убрать resource checks или сменить session между
queries ради PASS. Старые URI должны оставаться unavailable; новые authorized
queries требуют корректного fresh issuance. Frozen implementation пока не меняется.

## Capability reproduction принят; correction разрешена

Raw trace проверен родителем: C-T3 `issue` call для consumed URI имеет spent=true,
actual returnNone, затем `_bind_atomic:312` ValueError и public atomic refusal.
Причина установлена совокупностью public read/replay/refusal и frozen control flow.
Driver ERROR от неверного line-number assertion сохранён; ни assertion, ни итоговый
старый run не переименованы в PASS.1prepare/2queries/2reads,42forwards/19076tokens.

Принят design `step10-qwen-capability-repro/DESIGN_AND_REPRO_RU.md`:
host-only fresh intent только для новой qualified query; default rebind;
canonical locator/fingerprint отдельно от renewed session capability;
strict spent old URI, active alias reuse без TTL refresh, atomically staged maps/
packet/snapshot, consistency checks и pricing после реальных URI bytes.
Разрешён smallest diff трёх production files с предварительным сохранением
before bytes; original534-file manifest, policy и historical artifacts неизменны.
Scorer/prompt/data/threshold не меняются. Scope runtime: public renewal regression
до1prepare/3queries/5reads и один existing legacy portion replay integration test.
Дальнейший semantic acceptance ждёт parent diff/manifest review.

Родитель отдельно проверил historical `prepare.json`: обе временные SQLite DB
отсутствуют после process exit; raw source identities содержат generation UUID.
Поэтому новый authorized prepare меняет provenance-dependent model input даже
при прежнем absolute root. Следующий proposed8-question final-only gate должен
быть явно fresh-prepared, со старым numeric threshold и неизменными фактическими
критериями. Exact-predicted-unit equality допустима только при одинаковых inputs;
подмена generation или повторный fit ради PASS запрещены. Пока run не разрешён.

## Capability correction: итог родительского review

Принята. Родитель самостоятельно сравнил current three-file correction с
сохранёнными BEFORE bytes/old hashes и `production.patch`, проверил current repair
manifest и все остальные531unchanged files. Raw public regression подтверждает:
new V!=spentU, literal active-alias packet reuse, обе source-exact Capacity reads,
oldU remains unavailable и replayV unavailable; C-T3 facts/spans/hash/scope/version
сохранены. Readonly receipts совпали; raw work sum63forwards/28536tokens.
Runtime родителем не повторялся. Atomic fault/expiry не выдаются за injected proof.

Repair candidate SHA256:
`cf794aba227f91df7af099ed4dfb02bb09c733ff1dfd7ef2d64f59611e8f2f1e`.
Approval этой correction не разрешает semantic run автоматически. Исполнителю
поручено минимальное extension существующего runner: command recovery,2prepares,
8final calls и прежняя resource-read sequence; exact oldpolicy/tau, без нового fit.
Новый manifest и recovery authorization должны связать repaired implementation,
evaluator и исторический ERROR/policy. Validation допускается лишь после нового
recovery PASS и отдельного parent authorization. На этом checkpoint inference
по recovery/validation ещё не разрешён.

## Recovery entry принят и однократный run разрешён

Родитель прочитал entry diff, сверил его с BEFORE bytes и подтвердил618current
hashes, exact oldpolicy и prior_failure. Из reviewed repair files изменён только
runner; production/semantic recipe/data не менялись. Recovery branch не вызывает
fit и сохраняет existing phase/packet_check/gates/read-only/resource sequence.
Input hash comparison вынесен в diagnostic, старый ERROR не подменяется PASS.

Approved manifest SHA256:
`2bcebef52ab6268e091f5e28de12acc8837988bff36c2068432e2a4b73ebe066`.
Path: `step10-qwen-recovery-entry/recovery-freeze-ready-manifest.json` относительно
`eval/blind_project_context`; previous draft369534… сохранён рядом.
Родитель создал `parent-recovery-authorization.json`: только2prepares/8final
calibration questions с policy16fb92… и неизменными gates, без refit/retry.
Validation approval пока отсутствует. Исполнителю поручено выполнить run и
сохранить все фактические counters/raw receipts для следующего parent review.

## Recovery PASS принят; первая validation разрешена

Родитель проверил618hashes и независимо собрал expected source spans/факты по
original files и frozen labels, сравнил с8actual packets:24/24units,40/40facts,
оба noanswer complete+empty,0hardnegatives. Source metric пересчитан из original
delivered intervals с pinned codec:961/4272tokens. Raw work sum176forwards/76022
input tokens,16changed/160equal model-input hashes,readonly receipts подтверждены.
Новых product/model calls при review не было. Recovery boundary принят честно:
fresh-prepared public acceptance; old calibration ERROR не превращён в PASS.

Summary93f8f93787c0c4a50a424d22295c2ed85a94df6cc73d7e349ef1ccde6da08604 и
original policy16fb92… связаны новым parent-validation-authorization.json.
Разрешён один первый validation run8questions,2prepares и existing resource reads
на неизменных manifest2bcebef…/policy/prompt/source/labels. При FAIL/ERROR — сохранить
и остановиться. Validation не повторять/не подгонять. Следующие installed/realproject/
Terra gates требуют отдельного review; сейчас не разрешены.

## Итог review frozen Qwen + structural v2: QUALITY FAIL

Родитель независимо проверил все8validation packets по original docs/labels,
source spans/hash/scope/version/authority, complete scan/noanswer,618boundhashes
и readonly receipts. Результат совпал:22/24required units,38/41facts. Все3потери
в V-M1 относятся к `weather.md#Suspension`, отсутствует также required ancestor
Weather decisions. Source reduction пересчитан из исходных delivered intervals:
1069/4056tokens (73.64%);2noanswer complete+empty,0hardnegatives. Это неPASS при
потере обязательных условий. Raw receipts sum176forwards/75136tokens.

Наблюдаемый путь: delivered Transfer содержит явный anchor weather.md#suspension;
target score0.43782350420951843 ниже frozen tau0.8670357465744019; v2 не закрывает
anchor автоматически. Обязательные wind/interlock/identifier/restart facts
теряются. Не приписываем модели недоказанные внутренние причины. Capability repair
этот run не блокировал; он не устраняет semantic dependency loss.

Validation summary SHA256:
`14e5f1f2512b16d7795083c7fb992d346b401aa20201c98b1f770878bc08a1a2`.
Historical recoveryPASS/calibrationERROR/validationFAIL сохранены раздельно.
Текущая policy не принята для installed/T01/Terra/L2. Defaultoff; реального
provider-token proof нет. Все Qwen smoke/preflight/calibration/reproduction/
repair/recovery/validation вместе:714forwards/310091model-input tokens.

Дальнейшее поручение исполнителю — design-only нового dependency admission:
консервативная own-body reference closure либо обоснованный relation mechanism,
без тематических словарей, small caps или настройки по V-M1. Нужны явные границы
navigation amplification/nested conditions/scope и новый independent pre-frozen
holdout; старые16scenarios после просмотра не могут вновь объявляться blind
validation. Текущие bound files, thresholds и источники не меняются; новых model
calls/implementation на этом checkpoint не разрешено.

## Reference closure revision2: следующий design принят

Revision1 возвращена: запрет expansion у mechanically added ancestors вновь мог
терять условия; ownbody target не покрывал явно адресованный раздел с детьми.
Revision2 принята как отдельный experiment contract: все delivered bodies имеют
одинаковое reference treatment, target heading включает полный author section
extent, local document link — полный checked документ, definitions wholeowner.
Semantic seed сам по себе не включает subtree. Обход до fixpoint без caps,
live qualification/source identity/typed gaps; внешние источники не загружаются.
Стоимость navigation amplification принимается и проверяется, не маскируется.

Исполнителю разрешены smallest versioned production/evaluator diff и подготовка
нового pre-inference holdout: pinned upstream raw Markdown, естественные вопросы,
independent verbatim obligations/optional/unlabelled labels. Old16cases остаются
seen regression; текущая policy/validationFAIL не переименовываются.
До review конкретного diff и corpus никаких model calls/симуляций/новых runtime
tests; source downloads и bounded static checks разрешены. Существующие scorer
inputs и capability correction не меняются; BEFORE bytes затронутых files сохранять.
Budgets следующих прогонов ещё не утверждены. Новый experiment пока не имеетPASS.

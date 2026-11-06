# Step10: публичный experimental candidate и фактические проверки

Дата: 2026-11-06. База: `393082976d2e06b946e6ce6d12997d50d869f73d`.
Публичный candidate **реализован и подключён**. Общие performance fixes проверены;
отдельный own-body-gated-v2 также реализован и прошёл независимый запуск проверки.
У обеих relevance recipes acceptance **FAIL**: остаётся no-answer/structural
overinclusion. Default не включён. Предыдущий V2 wheel — b8ecfb99…; новый V3 ниже.
Коммитов и push нет. Frozen вопросы, документы и oracle не изменялись.

**Доказательный аудит по запросу владельца:**
[`step10-selection-audit/RESULTS_RU.md`](step10-selection-audit/RESULTS_RU.md).
Два public replay со scores установили низкий rank PR-блока (82/126), который
независимо воспроизводится официальным HF model-card путём. Ошибка encoding на
нём не найдена. Подтверждены несовместимость V1 direct-positive calibration с
no-answer, нерепрезентативная однодокументная validation и subtree amplification.
Отдельный implementation gap:11 помещающихся units разбиты на лишние окна.
Статьи EXIT/LongRefiner не воспроизведены их обученными механизмами; pipeline
проверяет другую baseline-гипотезу. Production/policy не менялись,0 новых Terra calls.

**Последний general correction — closure-aware V3:** новый schema2 calibration
recipe выбирает наибольший observed tau, сохраняющий все полезные bodies/facts
после неизменной closure, без raw-retention gate. Tau−3.352724552; calibration
20/20 facts, fresh validation27/27 и19/19 useful bodies, no-answer2/2 пусты
в каждом split. Но installed original T01 и original+translation дают **0/3**,
34/157 seeds →72 rows без CONTRIBUTING.md. Перенос порога **FAIL**, Terra
не запускалась. Default выключен; V1/V2 результаты неизменны. Новый wheel
9b95d287…, policy5683d27c…; точные hashes, контрактная разница и runtime:
`step10-calibration-v3/RESULTS.md`, `DESIGN.md`, `measurement/`.

**Обновление после возобновления квоты:** один post-fix Terra L0/T01-ru завершён,
3/3 фактов и цитат; all-step input+cache61419 против file5247 (**11.706×**).
V1 выбрал152/157 units, closure доставил157/157. Агент добавил кавычки к MCP
question — exact-question contract FAIL. Provider429 больше не текущий blocker;
acceptance остаётся FAIL. Полный L2 не обоснован. Подробный разбор, ограничения
сравнения и воспроизводимый аудит: `step10-agent-evaluation/renewed-results.md`.
Исторические quota-blocked результаты ниже сохранены как прежние попытки.

## Публичный маршрут и конфигурация

```sh
DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT=1
DOCATLAS_EXPERIMENT_MINI_PATH=/absolute/path/to/pinned-assets
DOCATLAS_MINIMAL_CONTEXT_POLICY=/absolute/path/to/policy.json
DOCATLAS_CONTEXT_COMPRESSION=off
```

Policy: `step10-calibration/measurement/policy.json`. Без policy выполняется
явно unverified keep-all diagnostic scan, а не произвольный relevance threshold.
Старые selection/budget overrides с candidate несовместимы.

1. `iter_scope_candidates` и project dispatcher получают весь разрешённый active
   generation без FTS/E5/256 admission. На один service call — одна acquisition
   и preparation; явные query lanes сохраняются. SQL keyset batch — не top-k.
2. Checked native sections превращаются в own-body scoring units. Полные
   question/body/ancestor token windows проходят pinned MiniLM, raw logits MaxP.
   Нет prefix truncation, словарей, MMR, filling budget или lexical fallback.
3. `minimal_context_structure.py` добавляет ancestor introductions, выбранные
   subtrees, footnotes/reference/fragment dependencies до fixpoint. Недоступные
   зависимости явно отмечаются. Scope/hash/source проверки выполняются до
   hydration и повторно перед выдачей; score не предоставляет authorization.
4. `minimal_context_selection.py` применяет frozen threshold, собирает целые
   проверенные spans и выбирает наименьшее обратимое представление. Только затем
   exact BPE count сравнивается с emergency **50000**. Превышение — body-free
   stop до публикации capabilities, а не обрезание или следующая страница.
5. Atomic source registry v2 без eviction128; whole-block reads без legacy
   600-token/40-line/2-read квот. Сохраняются expiry, replay и stale denial.
   `read_docs_source` даёт тот же reader через отдельный публичный MCP tool.
6. OpenCode native adapter в `integrations/opencode-v2-compact/` сохраняет
   точный compact text, убирает Code Mode object inflation и проверяет конечный
   model-visible размер. Требует явной установки, candidate wheel и Python.

Память: это **не end-to-end streaming**. Есть consumer list, per-document caches
и O(candidates × lanes) metadata; полные memo deepcopies и повторные acquisition
по каждому lookup удалены. Большие разрешённые корпусы всё ещё дороги.

## Независимая calibration/validation

Переносимые исходники, frozen hashes, labels и receipts:
`step10-calibration/`. Это отдельно написанные предметные fixtures, не внешний
benchmark. Calibration и validation разделены по документам/семействам.

- 4 настоящих public preparations, 18 public context calls; реальные компоненты.
- Tau `-7.280395030975342`, минимум calibration positives; до validation frozen.
- Policy SHA256 `327fc69db2c97e6d44abbe83118b01fad15a308c071fd5226880c14ee7679a4c`.
- Calibration: 12/12 useful units, 8 false positives из 22 negatives.
- Validation: напрямую 11/12 useful units; closure восстановил оставшийся unit;
  **14/14 обязательных фактов доставлены**. Один из двух no-answer случаев
  загрязнён нерелевантным контекстом. Приёмка **FAIL**, threshold не перенастраивался.
- Сокращение source text 16.69%; это не экономия полного Terra-диалога.
- Полные scores доступны только passive `observe_minimal_context()`, отдельно
  от model payload/protocol stdout. Исправлена обнаруженная diagnostic inflation,
  ранее ошибочно создававшая 195627-token emergency на 257 коротких документах.

## Выполненные проверки

| Граница | Фактический результат |
|---|---|
| Public preparation + storage scan | 257 фактов, scope, read-only и generation change PASS (2.82s) |
| Public MiniLM + MCP payload | 257 точных фактов, private scope exclusion, refs первого/последнего источника, replay/stale/read-only PASS (18.58s) |
| Public emergency | Настоящий fenced block >50k BPE, файл <256000 byte preparation limit; body-free stop PASS (22.93s) |
| OpenCode 2.2.5 provider-bound transport | 5356 → 4854 result tokens, 9.37%, exact text; scripted provider, не Terra quality |
| Adapter guards | Large output, client truncation и inflation emergency проверены |
| Installed simple stdio | 4 calls, точный CRLF source, dedicated read/replay, canonical error PASS |
| Legacy reader regression | 7 PASS/1 FAIL; тот же FAIL line142 reproduced на baseline HEAD, не Step10 regression |

Emergency fixture сначала ошибочно превышала неизменный preparation byte limit;
исправлен fixture до 3800 ledger lines, источник policy не ослаблялся.
Успешные наборы без новой причины не повторялись. Новые тесты только integration.

## Установка и воспроизведение

- Model `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, revision
  `1427fd652930e4ba29e8149678df786c240d8825`; все шесть pinned hashes проверены.
- Python3.13, torch2.10.0+cpu, transformers4.57.1, safetensors0.8.0.
  `/tmp/opencode/step10-mini-py313` использует shared dependency `.pth`: не hermetic.
- Installed wheel `/tmp/opencode/step10-wheel-public/doc_atlas-1.3.2-py3-none-any.whl`,
  SHA256 `663e294282ed6eb04cd052de5392eac57430f3c50ad310d3781495492f9768ef`.
- Installed servers запускаются без checkout `PYTHONPATH`.
- `prepare_installed_candidate.py` — confirmed public preparation frozen catalogs.
- `probe_minimal_delivery.py` — unchanged T01, original/translation/focus,
  trace OFF/ON, hashes/spans, live resource/replay и read-only.
- `run_gap_agent_study.py --arm file-current|minimal-context` — реальные Terra
  sessions без старого 12-step cap; timeout отдельно отмечается как censored.

Первый installed T01 отказал при startup: ancestor `/tmp/opencode` имел 0775
без sticky bit. Добавлен sticky bit, guard не изменялся. Второй запуск вернул
`member_store_uninitialized`: старые frozen directories не содержали DB.
Это не PASS retrieval. Сохранены обе попытки, остановлен ошибочный candidate run;
L0/L2 заново подготовлены через public `prepare_docs` с прежними catalog/hash.
Последующие receipts и реальные agent metrics фиксируются отдельно ниже.

## Consumer audit и финальный review

Existing public library/version integration под candidate: **1 PASS, 1.07s**.
Проверены точные версии/источники и неизменность SQLite. Общий full acquisition
и 50k wire guard согласованы; library/mixed selection сохраняет прежний library
policy, а не project calibrated structural algorithm. Alternate Python
`SourceReadController`/`ModelContextSession` не входят в поддержанный standalone
native adapter; их legacy-квоты не объявляются мигрированными.

Review нашёл valid multiline reference destination (`[ref]:` + URL на следующей
строке), который ранее не добавлял anchor dependency. Исправлен общий parser
definition handling, не topical правило. Stage-level public-acquisition probe
прошёл после изменения. Это отдельная граница доказательства от финального
semantic membership/ответа Terra. Переносимый probe: `probe_minimal_structure.py`.

Measured wheel `663e…` сохранён неизменным для исторического Terra замера.
Промежуточный wheel с одним structural-review product delta:
`/tmp/opencode/step10-wheel-final/doc_atlas-1.3.2-py3-none-any.whl`, SHA256
`8f1442dea261a0d28d64c7e6993b19e137dd574afb8f5d8e1a2d03bfe6648c46`.
Установлен отдельно в `/tmp/opencode/step10-final-py313`; импорт final structure
из site-packages подтверждён, SHA256
`aad12635c2208591db4d85ca4031d6b6597237325561b33d0eabc6288f2122f0`.
Terra-замер старого wheel не выдаётся за замер final wheel.

## Реальные агентные измерения

Первый file arm оказался infrastructure-invalid: все 16 sessions получили
`Permission denied: external_directory`, 0/46 facts и 44147 input tokens.
Это понесённая стоимость неудачной подготовки, не рабочий baseline.
Исправлено только узкое разрешение чтения frozen project directory; источники,
вопросы, модель и критерии не менялись. Повторный рабочий baseline завершён.

| Fresh file-current, 16 dev sessions | Значение |
|---|---:|
| Required final-answer facts | 42/46 |
| Полностью прошедшие ответы | 12/16 |
| Supported fact citations (отдельно от полноты ответа) | 45/46 |
| Uncached input | 138621 |
| Cache read | 31232 |
| Полный input с cache read | 169853 |
| Output | 9315 |
| Tool calls / errors | 50 / 0 |
| Сумма wall time sessions | 295.57s |

Оба T15 ответа пропустили structuredContent/content; L2 T12 — no-reconcile /
no-repository-write; L0 T19 — pinned-binary qualifier. Полная source citation
не исправляет пропущенный факт в конечном ответе. Подробные per-fact reasons,
исходные финальные ответы и reconciliation usage: `step10-agent-evaluation/`.
Provider возвращает cost=0 без тарифа: денежную стоимость не выводим из этого.

L2 full-scope calls оказались настолько дорогими, что реальные agent sessions
достигают установленного в study 900s timeout. Censored ответ не считается PASS,
а recorded provider usage для незавершённого шага — нижняя граница. Снимок
процесса candidate server показал RSS около 5.6 GB (не peak measurement).
Попытка read-only stack diagnosis `uvx --from py-spy==0.4.1 py-spy dump --pid …`
отклонена host ptrace policy: `Permission Denied`. Права/production guards не
менялись ради профилирования. Это ограничение диагностики, не оправдание качества.

Первый подготовленный installed T01 probe прерван неверным evaluator assertion:
public `content_sha256` — digest canonical source material, не SHA только snippet.
Исправлен evaluator: source span берётся из исходного файла, затем независимо
собирается контрактный материал `{path,section,content,snippet,version}`. Проверка
точного текста/строк сохранена; production и frozen вопрос не менялись.

### Завершённый measured candidate (wheel663e)

| Arm/subset | Факты | Полные ответы | Input + cache | Output | Censored |
|---|---:|---:|---:|---:|---:|
| Fresh file, all16 | 42/46 | 12/16 | 169853 | 9315 | 0 |
| Candidate, all16 | 16/46 | 5/16 | ≥400358 | ≥4043 | 8 |
| Fresh file, L0 | 21/23 | 6/8 | 57522 | 4454 | 0 |
| Candidate, L0 | 16/23 | 5/8 | 354608 | 3455 | 0 |
| Candidate, L2 | 0/23 | 0/8 | ≥45750 | ≥588 | 8 |

На полностью завершённом L0 candidate расходует **6.165×** input+cache и
теряет больше фактов. Общий recorded input ≥2.357× baseline; «экономия» L2
не имеет смысла, поскольку ни один L2 ответ не завершён. Все censored случаи
остались в знаменателе46. Emergency T02/T12 остановил packets50110/50297 tokens;
эти body-free rejected sizes не прибавляются к доставленным provider tokens.
Шесть L0 tool requests добавили кавычки вокруг frozen question — отдельный
контрактный дефект агента; evaluator не нормализовал его ради PASS.
Подробности: `step10-agent-evaluation/comparison.{json,md}` и `candidate.*`.

### Последующие общие исправления

Аудит выявил legacy rejection metadata `section>300`, `path>500`, `version>100`
в общем source projector. Для candidate эти membership ceilings удалены,
source authority/path checks сохранены; legacy default не изменён. Final2 wheel
`1d99b4eb71e8c8a30a223054a75c3ef6797ed5b1b468c41b3e6f4795e6df684f` проверен
installed stdio на source с длинным heading, теми же procedure facts и CRLF:
4 calls PASS,505 wire tokens,4.091s (`/tmp/opencode/step10-final2-installed-wire.json`).

30s прерванный диагностический cProfile L2 показал 8181 dependency-set builds,
7695 source_graph misses и 8184 parses ещё до MiniLM. Cache16 документов churn
на hydration-id порядке489 документов; старые bounded proposals не нужны новому
structural selector. Это измерение первой фазы, не полная latency attribution.
Точный raw/source/DB hash read-only сохранён. Разбор и коррекция этой общей
подготовки выполняются отдельно от неизменного измеренного wheel663e.

## Подтверждённые исправления подготовки и installed T01

В candidate documentation-read после обязательной native identity/hash/span
подготовки пропущены старые bounded dependency proposals. Новый полный
structural selector ими не пользуется; его provenance и terminal проверки
сохранены. Legacy/patch/library-маршруты этот bypass не получают. Public257
scope/ref/stale/read-only integration после изменения: PASS19.07s.

Следующий installed120s профиль выявил ещё одну причину: attachment каждого
source URI сериализовал весь preselection packet через `_refresh_estimate`.
За первые1066 refreshes потрачено42.7s при пуле~11674 строк; inference ещё
не начался. Исправлен pure-decoration loop: все bindings сохраняются, final
estimate вычисляется один раз. Public257 после этого: PASS19.42s.
Профили и ограничения сравнения: `step10-agent-evaluation/performance/`.

Wheel с обоими исправлениями и снятыми candidate metadata/path ceilings:
`/tmp/opencode/step10-wheel-batched/doc_atlas-1.3.2-py3-none-any.whl`, SHA256
`0651de09b30ad1a5fcf036a9ed403d5cbf8c399f27be89dea2da9cedb8769412`.
Installed `/tmp/opencode/step10-installed-T01-batched/receipt.json` завершён:

| Неизменный T01 L2 | Время | Результат | Факты |
|---|---:|---|---:|
| Original | 479.40s | body-free emergency; selected packet1179395 tokens;9327 pairs | 0/3 |
| Original + full translation | 816.79s | emergency1202140 tokens;18562 pairs | 0/3 |
| Explicit CONTRIBUTING.md focus | 1.55s | 7 целых sections,1729 delivered tokens | 3/3 |
| Original, trace ON | 432.01s | тот же emergency и те же9327 pairs | 0/3 |

Всего6 product calls, включая source read/replay. OFF/ON полные ответы совпали;
исходные тексты и SQLite SHA не изменились; source spans и canonical material
digests проверены независимо. Это PASS доставки/trace/ref/read-only контракта,
но **FAIL широкого поиска нужных фактов**, не исправленный T01. Миллион токенов
не передавался модели: terminal packet157 tokens без source body.

Повторный Terra запуск с этим wheel не измерил качество: provider вернул HTTP429,
`provider.quota`, `usage_limit_reached`, `The usage limit has been reached`,
weekly premium used100%, credits=false. Все16 attempt receipts сохранены в
`/tmp/opencode/terra-step10-batched`; не прибавляются к успешным/censored
результатам прежнего wheel. Другой answering model не подставлялся.

## Общая relevance-коррекция v2 (отдельный эксперимент)

Первый контекстный MaxP мог пропускать нерелевантный child благодаря релевантному
ancestor introduction. Новый явный recipe `complete-own-body-gated-maxp-v2`
добавляет независимый проход по own body с exact heading lines, без ancestor
introductory bodies. Membership score — минимум contextual MaxP и own-body
MaxP. Все окна и источники проходят оба расчёта; top-k/бюджетного заполнения
нет. Полная subtree/dependency closure и источниковые проверки сохраняются.
Это проверяемая гипотеза, не обещание устранения broad-root overinclusion.

Активируется отдельно `DOCATLAS_MINIMAL_CONTEXT_RECIPE=complete-own-body-gated-maxp-v2`;
старый policy recipe несовместим и не принимается. V1 default и исторический
threshold остаются неизменными. Новая calibration/fresh validation фиксируются
до inference в `step10-calibration-v2/`; Terra/frozen questions не используются
для выбора threshold. Итог v2 добавляется после независимой проверки.

### Итог v2: независимая проверка завершена, acceptance FAIL

Новые16 tasks/88 own-body labels, четыре независимых fictional manuals;
calibration и validation разделены по семействам. Input manifest SHA256
`7c7399ce4f257a383b158ad30132742a9a89083f6dc7ba8bf335dc450e96a539`
зафиксирован до inference. Выполнены4 public preparations и16 public queries.
Threshold `-6.489150047302246` выбран только по calibration positives;
policy SHA256 `5eb8d93aabd318bf24505383ed54c14733a8900eaf19a783f8f078cc953520ff`.

- Calibration:16/16 direct positives,3/28 false-positive units.
- Fresh validation:15/16 direct positives,16/16 delivered positives,**22/22 facts**.
- Direct false positives5/28; после closure доставлены12/28 negatives.
- Один из двух no-answer случаев возвращает полный нерелевантный документ.
- При одном и том же frozen v2 tau gate убирает2 прямых false positives (7→5)
  без дополнительных useful misses; closure возвращает оба обратно.
- Source text18348/21172 chars (сокращение13.34%), serialized JSON11199 tokens.
  Это не dialog savings и не независимо откалиброванное сравнение с v1.

Таким образом, исключение ancestor introductory body из второго score улучшает
часть direct membership, но **не устраняет overinclusion от релевантного parent
и обязательного subtree closure**. Незаметно ослаблять сохранение условий и
исключений ради PASS нельзя. Direct-retention и no-answer gates провалены;
порог/labels после validation не менялись. Последующие полные L2/v2 и Terra
серии не запускались: локальный gate уже FAIL, а answering provider недоступен.

Окончательный wheel, включающий оба performance fixes и opt-in v2:
`/tmp/opencode/step10-wheel-v2/doc_atlas-1.3.2-py3-none-any.whl`, SHA256
`b8ecfb99faba079faa6c74723be16b0ffee388d20365485f69a7e0ba7d457f8e`.
Он установлен в `/tmp/opencode/step10-final-py313`. Installed real-model stdio
v2 с frozen policy: long heading + long path,446 exact source bytes/CRLF,
source capability/read/replay, canonical error — **4 calls PASS,617 wire tokens,
4.046s**. Это позитивный контроль public route, не доказательство широкого T01.

Переносимые v2 источники, labels,40 output receipts и manifest:
`step10-calibration-v2/measurement/`, разбор `step10-calibration-v2/RESULTS.md`.
Provider blocker: `step10-agent-evaluation/provider-quota.{json,md}` содержит
точную команду, ошибки всех16 sessions и incurred usage16641 input+cache/197 output.
Reset по ответу provider: **2026-11-11 07:23:49 UTC**. Квота не сброшена ни
локальной подготовкой, ни исправлением server; повторные обращения к тому же
исчерпанному лимиту не дадут сопоставимый замер. Другой provider/model не заменяет
заданный Terra эксперимент; доступ к новому лимиту требует действий владельца.

## Закрытие работ и оставшиеся критерии P0–P7

| Этап | Фактический статус |
|---|---|
| P0 | Pinned provisioning, frozen inputs, separate calibration/validation выполнены; quality gates FAIL |
| P1 | Полная acquisition и общие performance corrections реализованы; source/scope/read-only checks PASS; full L2 всё ещё дорог |
| P2 | Checked structural hydration/closure и whole-block emergency работают; overinclusion подтверждён, а не скрыт |
| P3 | V1 и отдельно opt-in own-body-gated-v2 подключены к public route; обе empirical acceptance FAIL |
| P4 | Atomic refs, whole reads, native client presentation реализованы и проверены на заявленных границах |
| P5 | Целевые реальные integration/installed checks выполнены; единственный указанный legacy FAIL воспроизведён на baseline |
| P6 | Исходный16-case Terra замер завершён с8 censored; corrected installed T01 завершён; updated Terra answers BLOCKED429 |
| P7 | Исторические и новые результаты сохранены, negative acceptance зафиксирована; default выключен |

Итог: продуктовая интеграция и проверяемые общие коррекции выполнены, но цель
минимального полезного контекста не достигнута. Ни default enablement, ни
экономия диалога, ни full post-fix Terra acceptance не заявляются. Коммитов/push нет.
Финальные статические проверки: `git diff --check`, Python compileall,
побайтовое соответствие всех product files последнему wheel и разбор63 JSON
artifacts — PASS. Они не заменяют перечисленные runtime/quality проверки.

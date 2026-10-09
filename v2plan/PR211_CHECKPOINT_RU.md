# PR #211: checkpoint продолжения merge-readiness

## Текущая точка исполнения: 589a6366, 2026-10-09 19:00 UTC

**PR ещё не готов к merge.** Arbitrary output ceilings **6144 bytes / 800 tokens /
3 sources** не являются gates: оцениваем стоимость и сохраняем доказательства.
Operational input/read/work/consent boundaries остаются. Retrieval исправляется
в рамках позднее утверждённого плана, исходное blanket deferral больше не блокирует
подтверждённые потери фактов; о качестве судим по исходным вопросам и источникам.

Последний завершённый joint CI — `589a6366e33278fe542a0e3c971d2502e5e9f99f`:
[main 37975999319](https://github.com/Vanilla1999/DocAtlas/actions/runs/37975999319).
- core-tests-3.11.xml: **5996 PASS / 1883 FAIL / 0 ERROR / 10 SKIP**; XML SHA256 `359210d288a9a23f25bd430a5b052db063a6e707c90450e4d8cc11db34a1ac33`.
- core-tests-3.12.xml: **5996 PASS / 1883 FAIL / 0 ERROR / 10 SKIP**; XML SHA256 `c5f7797184e864c1872e63d6c9aa0b02a6e9dc83c56bd4d798f611a4c961c10c`.
- core-tests-3.13.xml: **5996 PASS / 1883 FAIL / 0 ERROR / 10 SKIP**; XML SHA256 `bf7471b05fa0a55b751ffed6a66fd675787f96379a0bbdbe38de9a1447dde065`.

[JUnit diagnostics job113978187064](https://github.com/Vanilla1999/DocAtlas/actions/runs/37975999319/job/113978187064)
пересчитывает существующие raw XML, не запускает тесты повторно. Нет расхождений
suite/case counts, duplicate IDs или скрытых console rows; полный JSON приложен
к этому же run. Matrix counts не складываются в один искусственно большой набор.
228 failing modules предыдущего ec85 не классифицируются целиком как legacy:
среди них есть настоящие fixture, source admission и retrieval quality проблемы.

Подтверждено на 589a6366:

- Task33: **57 PASS / 7 FAIL** ([job113974342130](https://github.com/Vanilla1999/DocAtlas/actions/runs/37975999425/job/113974342130)).
  Все4 fixes slices27/28 прошли: authority aliases и typed literal requirements.
  Два prior multi-target collisions уже закрыты slice25. Остаются три
  ActionPacket public/SDK cases и четыре task-level adapter cases.
- SourceMap late declaration/window identity положительные guards проходят.
  Generated-artifact fixture пока не получил текущий explicit finite grant.
- Read-next остаётся **22 PASS / 9 FAIL**. Slice31 сохраняет все исходные31cases,
  но меняет budget-driven range expectations на полные raw prefix/suffix и full
  183-line code block с snapshot binding. Его runtime ещё предстоит.
- Recovery: **11 baseline / 14 intended guard kills**, normal critical gate:
  **29 baseline PASS / 7 mutants killed**. Новый alias mutant падает только в
  `critical_alias_no_generated_queries` (1 failure, no errors/skips, exit1).
  [Advanced job113974342691](https://github.com/Vanilla1999/DocAtlas/actions/runs/37975999319/job/113974342691)
  также подтверждает неизменённый historical702/compact82 comparison с51mutants.
  Старые49 alias cases в этом SHA ещё собраны; отдельный retirement теперь можно
  готовить по frozen archive/crosswalk, без приписывания им source-quality coverage.
- Static, docs contract, installer, retrieval evidence, installed MCP и три
  platform smoke jobs SUCCESS. Required-ci, advanced/P1/downstream всё ещё FAIL.
  Настоящие Claude Code/Codex/OpenCode sessions **NOT RUN**; fixture SDK/stdio
  executions не выдаются за клиентский/модельный acceptance.

P1.4 наконец выполняет все14 frozen original-question cases на настоящем public
fixture retrieval. На ec85a496 **0/14 overall, 3/10 discovery, 2/5 complete facts,
0 runtime errors**; пять independent oracle controls и report integrity PASS.
Все14 дали read_only failure. Slice30 исправляет только optional missing sources
на honest insufficient и выводит actual before/after state diagnostics. Store
hash/generation/checks не ослаблены, warmup не вводится. Предполагаемая запись
при lazy SQLiteStore initialization требует проверки этими наблюдениями.

Текущая работа после этого snapshot:

1. Довести source-choice consent handoff: production сейчас теряет typed ask и
   его options при blanket confirmation veto. Evidence остаётся запрещено;
   source-embedded actions и автоматическое выполнение не разрешаются.
2. Task33 positive сохраняет VALUE=2 и исходные источники: явный filename source
   identity ошибочно превращается в body literal obligation. Исправлять только
   при explicit path DTO, сохранять отдельные public exact_term/fact guards.
3. Проверить read_next и P1.4 state diagnostics на следующем опубликованном SHA,
   затем закрывать фактические original-query/fact/contamination failures.
4. P1.5 finite public library/mixed fixtures и остальные P1 gates ещё открыты.
   Никакой финальный acceptance не заявлен, пока joint exact-SHA gates красные.

Рабочие refs: `implementation/pr211-merge-readiness` и PR ref
`integration/stage3-v2-identity-pr1`, ordinary fast-forward only. Local checkout
после0049c6d не синхронизирован: exec transport недоступен с18:09UTC. Все поздние
изменения готовятся exact-file GitHub API, source-reviewed и проверяются обычным
PR CI. Local AST/compile/import/runtime после outage **NOT RUN**.

## История до текущего snapshot

## Продолжение после 0049c6d: recovery подтверждён, остальные gates открыты

[Main CI 37971052890](https://github.com/Vanilla1999/DocAtlas/actions/runs/37971052890)
на `0049c6dd3643a8c214c7c899a08201495ab61d51` завершился FAILURE:
все три core jobs и required-ci красные. Нового полного JUnit подсчёта этой версии
здесь нет; числа 118e5d1 ниже не приписываются 0049c6d.

- [Advanced log](https://github.com/Vanilla1999/DocAtlas/actions/runs/37971052890/job/113957463606)
  подтверждает **11 recovery baseline PASS / 14 intended guard kills**.
  Original discovery не теряется при добавлении lookup; metadata и чужой source
  window не создают original credit. Это не полный retrieval quality PASS.
- Retrieval evidence, docs contract, installed MCP, installer и три platform
  smoke jobs SUCCESS. Реальные application/client sessions остаются **NOT RUN**.
- Static и federated выявили новый regression: part03 имеет 1011 строк при
  пределе1000. Slice19 механически вынес diagnostics в соседний57-line module,
  сохранив тела функций. Размер не повышался.
- Slice21 сохраняет существующий same-call diagnostics в no-results return.
  Truly-empty test не ослабляется. Slice22 исправляет реальную потерю late
  declaration после восьми ранних references; конечный source grant сохраняется.
- Slices20/23 мигрируют десять existing ActionPacket cases на явные SDK contracts
  и whole-window fidelity. Все20function names сохранены. Source replacement,
  missing requirement, missing create collision receipt и forged filename alias
  должны отклоняться своими guards; editing permission не выводится из prose.

Все эти новые slices прошли независимый source review. После потери local exec
transport изменения подготовлены через exact-file GitHub API и опубликованы
обычным fast-forward. Local AST/compile/runtime после outage **NOT RUN**;
результаты будущего CI здесь не предрешены. Нет force-push, merge или release.

Следующие blockers: read_next, оставшиеся current public ActionPacket/Task33
contracts, P1.4/1.5/1.6 fixtures/evaluators и подтверждённые потери original-only
retrieval. Полный quality/downstream acceptance ещё не выполнен.
**PR пока не готов к merge.**

## Подтверждённый результат 118e5d1; compact активирован

[Main CI 37968005070](https://github.com/Vanilla1999/DocAtlas/actions/runs/37968005070)
на `118e5d17af58679f3b109fb69e10586bc2423c72` завершился FAILURE.
Core Python 3.13: **7886 = 5979 PASS / 1897 FAIL / 0 ERROR / 10 SKIP**.
ZIP artifact `11634597182`, SHA256
`57fa3fa659bc23a6c9bbc445d6be6c6d03fb43a4ca2fea8695bb790af0716163`.
Остальные Python jobs также FAILURE; их JUnit здесь отдельно не пересчитаны.

- `docs-contract` теперь SUCCESS. Core подтверждает tool-choice archive 9/9,
  local membership 31/31, member transactions 109/109, active MCP examples 6/6,
  module policy 4/4 и historical atlas 7/7. Исторические model reports не стали
  evidence нового live model/client запуска.
- Compact уже подтверждён ordinary core на `fdbdc58`: 33 span + 49 compiler PASS,
  вместо 303 + 399. Всего на том SHA 7884 = 5960 PASS / 1914 FAIL / 0 ERROR /
  10 SKIP. Artifact `11633843530`, SHA256
  `5add6587bae801e9da165ecbcf5126d7a7f25f6ab884c1222d2d545df86a3f64`.
- 81 cost-only assert в 44 файлах изменён отдельным reviewed slice; исходные
  вопросы, facts, parameterization и guards сохранены по полному AST comparison.
  Full DTO cost остаётся измерением; operational read/work limits сохранены.
- ActionPacket 17 PASS / 14 FAIL. Пятнадцать мигрированных cases прошли; последний
  positive получил finite source grant, но выявил дальнейшую потерю поздней
  PermissionService declaration после ранних references. Это расследуемый product
  defect, а не основание снять требование найти все mutation/preserve targets.
- Continuation 22 PASS / 9 FAIL: после удаления output ceiling остаются следующие
  контрактные/фактические проверки. У observer quantum-rejection control PASS,
  no-candidate control FAIL на unclassified stage. V2 protocol 49 PASS / 1 FAIL;
  unobserved не приравнивается к observed empty.
- Static, installer, retrieval evidence, installed MCP harness и три platform
  smoke jobs SUCCESS. Реальные client sessions по-прежнему NOT RUN.

Следующий reviewed source-discovery slice сохраняет настоящий original hit при
добавлении lookup через private same-call receipt и fresh canonical qualification.
Он расширяет recovery до 11 programs / 14 intended mutants; прежние 10/12 outcomes
не переносятся на него без нового CI. P1/quality и остальные 1897 failures остаются
блокерами; PR ещё не готов к merge.

## Подтверждённый результат 2199002 и продолжение исполнения

На `2199002b96253fdaa538515056969713876993a6`
[main CI](https://github.com/Vanilla1999/DocAtlas/actions/runs/37963786931)
завершился FAILURE. Это актуальная проверенная точка; разделы ниже сохраняют историю.

- **Core Python 3.13:** 8504 = 6565 PASS / 1929 FAIL / 0 ERROR / 10 SKIP.
  Все прежние 61 setup ERROR устранены. На 8473 совпадающих с `99106c9` node IDs:
  29 ERROR → PASS, 16 FAIL → PASS и **16 PASS → FAIL**; 31 node добавлен, 40 удалены.
  Новые падения отдельно разбираются: восемь старых output ceilings, catalog/docs
  contracts, argv из pytest и историческая provenance отчётов. В других двух
  Python jobs итог FAILURE; их raw JUnit этим подсчётом отдельно не сертифицируется.
- **Recovery:** 10/10 PASS на этом SHA. На `50694b9` все 12 intended mutants
  обнаружены ожидаемыми assertion guards, без setup errors; исходные вопрос и
  source bytes, source-change и revocation controls проверены. Это не подтверждает
  весь retrieval quality.
- **Сокращение тестов:** historical 702/702 и compact 82/82 PASS. Все 51 production
  mutants обнаружены в обоих режимах. Независимая сверка всех 102 raw JUnit,
  rosters, изменённых source SHA и same-pytest imports сохранена в
  [LITERAL_REDUCTION_EVIDENCE.json](pr211-execution/LITERAL_REDUCTION_EVIDENCE.json).
  Следующий slice активирует compact default и требует нового core результата.
- **Agent adversarial:** 24/28 PASS, без execution errors; пять module-path
  диагностик исправлены. Четыре полезных положительных сценария остаются красными.
  V1 historical target-closed 8/11; отдельный explicit-catalog positive ещё красный.
- Advanced: 524 PASS / 98 FAIL из 622. V2 protocol 48/48 и release gate 52/52
  проходят в core. Общий quality/downstream acceptance остаётся незакрытым.
- Docs impact, static, installer, retrieval evidence, installed MCP harness и
  три platform smoke jobs SUCCESS. Реальные Claude Code/Codex/OpenCode sessions
  **NOT RUN**; SDK harness не заменяет client acceptance.

Артефакты main CI: core `11632303946`, ZIP SHA256
`6ab7fbce04f7e17009eedf95620f4396f9d3d6c88cc1cf0eaab94ad740fb5f41`;
advanced `11631544543`, SHA256
`bc40ef98720eb382c04c2c49aef80c99948b32d845d88e3a02bcb4a0decd8fad`;
mutation comparison `11631624539`, SHA256
`eafd9b4d52616e713d7fcb1492ac257b152f85d8ad79761c9549db0a8173f3b4`.

Продолжение: активировать доказанное сокращение, устранить оставшиеся cost-only
падения без потери source/consent guards, сохранить исторические model reports
без выдачи их за новый runtime, мигрировать явно заданные SDK mutation contracts,
затем продолжить P1/quality/retrieval. **PR пока не готов к merge.**

## Проверка docs/Agent slices и исправление collection

На `0e456906cc460e469e5e1f28ecde6f010bd59732` V2 впервые выполнился полностью:
25 cases; semantic usefulness natural 5/15, paraphrases 0/5. Legacy original
coverage остаётся 0 при minimum 12, contamination 0; lookup не засчитывается
за original. Hermetic quality и question gate PASS. Это диагностика реальных
потерь retrieval, не успешный quality acceptance.
[CI](https://github.com/Vanilla1999/DocAtlas/actions/runs/37960431539).

На `bfe9709160f4730d51311847ca9e0c5b2ab460a3` Agent v1 выполнил 11 исторических
задач и отдельный explicit-catalog positive; historical target-closed 8/11.
Adversarial 19/28 PASS, execution errors отсутствуют. Положительные задачи
behavior/requirements/comparison/CatalogReader теряют обязательные факты;
пять отрицательных path cases требуют проверки текущей error taxonomy.
[CI](https://github.com/Vanilla1999/DocAtlas/actions/runs/37960891349).
JSON обоих протоколов сохранён CI; artifact `11630609291`, ZIP SHA256
`500f1da0a1e802fd1de04af99048ed1c8efdde709fcce6730955a34f31b86bbb`.

На этих двух SHA core/advanced pytest остановлен при collection из-за stale
node hashes двух quality modules: случаев не исполнено, прежние 8513 outcomes
не приписываются новым SHA. Отдельные docs/platform failures — два ожидания
retired документационного текста. `59135469dae7bdaf78186d06aa246ed9022ca917`
исправляет hashes и проверяет действующий смысл docs; source review APPROVE,
обычный CI ожидается.

Следующий [literal context slice](pr211-execution/SLICE_05_LITERAL_CONTEXT_RU.md)
прошёл независимое review. Он допускает полезный body-фрагмент с точным
синтаксическим symbol исходного вопроса, сохраняя missing original, source/member/
snapshot guards и запрет answer/edit authority. Recovery имеет 10 baseline cases
и 12 intended mutants; runtime нового slice ещё не подтверждён. Он не заявлен
решением всей multilingual/quality проблемы. PR пока не готов к merge.

## Проверка 99106c9 и следующий docs/catalog/quality slice

На `99106c93b48def75c13ee411473b1f6fef1c418e`
[advanced/downstream CI](https://github.com/Vanilla1999/DocAtlas/actions/runs/37959180386/job/113917342535)
подтвердил question surface PASS, включая original positive, absent negative и
source-removal metamorphic case. Recovery: 8 PASS / 2 FAIL / 0 ERROR — оба
положительных сценария теряют исходный факт при delivery. Mutation gate честно
останавливается на красной baseline; kills для recovery не заявляются.

Core Python 3.13: 8513 = 6513 PASS / 1929 FAIL / 61 ERROR / 10 SKIP.
Все 303 span и 399 direct-compiler cases PASS; это зелёная baseline для
предстоящего сравнения старого и сокращённого набора. Advanced: 524 PASS / 98 FAIL
из 622. ZIP core SHA256 `9c47b5d0d25ae34d0f4c2bd478be619e75a231e93beec9080728b9281e8f7e17`,
advanced `6690ee979325f1679d1cec68a39693dd18c5698998cd578c7c1302f951ee0559`.
Остальные Python core jobs этим подсчётом не подтверждаются.

Docs/static/retrieval-evidence, installed-MCP harness и три platform smoke jobs
завершены SUCCESS. Это не успешные реальные Claude Code/Codex/OpenCode sessions.
Main CI ещё не является зелёным; PR не готов к merge.

Следующий [docs/catalog/quality slice](pr211-execution/SLICE_02_DOCS_QUALITY_RU.md)
прошёл независимый source review: 14 explicit members, 25 исходных V2 вопросов и
41 obligation ID сохранены; 6 witness migrations описаны отдельно. 800-token
ceiling в self-host/V2 заменён измерениями; Legacy original floor 12 и source/
safety/identity controls сохранены. Runtime этого slice ожидается после публикации.

## Исполнение плана: первый contract slice

2026-10-09 владелец поручил оценить, скорректировать и выполнить план.
Реализация предусмотренного этапа retrieval теперь разрешена; новое решение
записано в current decisions. Первым подготовлен
[question/recovery slice](pr211-execution/SLICE_01_CONTRACTS_RU.md): текущий
literal request contract, реальные member-backed positives/negatives,
source-removal transformation, приоритет authoritative conflict и отсутствие
next action при hard stop, строгие mutation reports и миграция семи span failures.
Исходные 288/399 parametrized cases пока сохраняются до сравнения силы проверок.

Baseline перед реализацией подтверждён raw artifacts `1148923`: core Python 3.12
8513 = 6506 PASS / 1936 FAIL / 61 ERROR / 10 SKIP; advanced 622 = 524 PASS / 98 FAIL.
Состав core и outcomes совпадают с `fe48e7b`; остальные Python matrices этим
сравнением заново не сертифицируются. Все FAIL/ERROR включены в
`pr211-execution/BASELINE_FAILURES.json.gz`, неизвестные причины остаются открытыми.

Статические проверки и независимое review первого slice завершены перед
публикацией; новый runtime и mutation outcomes ожидаются из обычного PR CI.
Готовность к merge не заявляется. Следом идут Agent/adversarial fixtures и
docs/catalog/quality, затем retrieval и оставшиеся семьи падений.

## Текущий план и проверенный результат e4f0ae0

Обновление: 2026-10-09. По запросу владельца составлен
[план сокращения тестов и завершения acceptance](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md):
миграция контрактов и fixtures, согласование docs/catalog/quality, независимые
oracles и mutation controls, обоснованное сокращение тестов, устранение повторного
core CI и совместный acceptance. Это план; перечисленные изменения ещё не выполнены.
Историческое ограничение на deferred retrieval действовало до поручения выполнить план;
более позднее решение об исполнении приведено выше.

На HEAD `e4f0ae09221b80ba1afddf983a2a6e3001220c52` удаление обязательного
800-token ceiling проверено: [retrieval job](https://github.com/Vanilla1999/DocAtlas/actions/runs/37950861568/job/113888965198)
SUCCESS. Все 80 payload/assessment/cost результатов совпадают с `fe48e7b`;
все 17 сохранённых проверок соблюдены. Максимум 1451 tokens и 24/48 исторических
превышения 800 остаются измерениями, не merge gate. Artifact `11625443959`,
ZIP SHA256 `1c7593cb5c28bc8163da99a78ad77c7cdca1f27d3f197b6de752758014f34be0`.
Merge checkout `65d959a31bcf4b6ce6f9060ab8afb3a6b6971644` имеет то же дерево
`d66c5441d148616db03f12f1837683d67f84f7e5`, что и HEAD.

Все 17 workflows этого HEAD завершены: 8 SUCCESS / 8 FAILURE / 1 SKIPPED;
[main CI](https://github.com/Vanilla1999/DocAtlas/actions/runs/37950861568) и
[P1](https://github.com/Vanilla1999/DocAtlas/actions/runs/37950861406) FAILURE.
Полные core JUnit counts ниже относятся к `fe48e7b`, отдельно на `e4f0ae0`
они не пересчитаны. Отмена ceiling не исправляет остальные quality/runtime blockers.

## Полный результат fe48e7b и отмена retrieval ceiling

На HEAD `fe48e7b414f3743b9424e8a7d675f0217b1286ee` завершены все 17 workflows:
8 SUCCESS / 8 FAILURE / 1 SKIPPED. Merge checkout
`36cd32b77b15b1c52cc9286b95471c6a61b07674` имеет то же дерево
`613b051d11df5d9ec94a933f6907b7d1b2fbc011`, что и HEAD.

- Все три Python 3.11/3.12/3.13: 8513 cases = 6506 PASS / 1936 FAIL /
  61 ERROR / 10 SKIP. Против `7a78c51` ровно девять normative FAIL→PASS,
  без добавлений/удалений и новых падений. Все 1997 оставшихся FAIL/ERROR
  сохраняют прежние первые причины.
- Critical gate: baseline 28 PASS; шесть mutations дают ожидаемые assertion
  failures 15/26/9/9/1/1, без errors/skips. Проверены raw JUnit и 98 import-origin
  записей. Advanced сохраняет 524 PASS / 98 FAIL из 622; восемь других downstream
  gates FAIL, dependent adversarial mutation SKIPPED после красного baseline.
- Установленный MCP: 15 SDK stdio запусков, 30 structured/text lanes,
  420 наблюдений; все шесть platform jobs и scripted harness PASS. Release
  validation PASS; реальные Claude Code/Codex/OpenCode sessions NOT RUN.
- Legacy self-host: 2815 tracked files, 119662253 bytes, 10 members / 98 sections;
  quality 10/16, original coverage 0 < 12, contamination 1. V2 останавливается
  на inactive `wiki/Commands.md`; собственного V2 JSON нет.
- Retrieval artifact `11597193405`, ZIP SHA256
  `1230c8d2a7c89c4ba182caca672b59d3656ba519904837f61ac606cfb730b118`:
  все 80 payloads/assessments/costs совпадают с `7a78c51`. В прежней группе
  из 48 cases 24 выше прежнего 800-token ceiling; максимум 1451. Это measurement
  старой политики, не доказательство потери данных или разрешение менять gold.

Источники: [main CI](https://github.com/Vanilla1999/DocAtlas/actions/runs/37888242626),
[P1](https://github.com/Vanilla1999/DocAtlas/actions/runs/37888242618),
[release](https://github.com/Vanilla1999/DocAtlas/actions/runs/37888242554).
Required CI `113685640523` и P1 aggregate `113685405445` завершились FAILURE.

Следующее явное решение владельца снимает обязательный 800-token ceiling,
сохраняя полное измерение объёма и остальные проверки. Оно реализовано отдельным
узким изменением `run_systemic_retrieval_plan_gate.py`; policy и report v3 описаны
в current decisions и `eval/systemic_retrieval_plan/README.md`. Новое поведение
проверяется существующим PR CI после публикации следующего HEAD. Результаты
`fe48e7b` не переносятся на новый commit автоматически. Сокращение тестов и
исправление downstream/quality пока остаются предметом запрошенного анализа.

## Последний полный прогон: 7a78c51; продолжение critical slice

Обновление: 2026-10-09. На опубликованном HEAD
`7a78c516a62304fc258bda5d5eb2b11544c829b5` завершены все 17 workflows:
**8 SUCCESS / 8 FAILURE / 1 SKIPPED**. Merge checkout
`8ecb256bb6e3fbacae3529df6ce60a631485830a` имеет то же дерево
`a439647fdd726d4db65f9cd7f0fb17fa5e772958`, что и HEAD.

- Main Python 3.11/3.12/3.13: **8513 = 6497 PASS / 1945 FAIL / 61 ERROR / 10 SKIP**.
  Полные roster/outcomes одинаковы; против `991638f` ровно один FAIL→PASS,
  добавлений/удалений и PASS regressions нет. Все шесть self-host tests,
  семь предыдущих member/mtime fixes и 141 security controls PASS.
- Исправленный новый self-host positive использует явно переданный literal lookup,
  сохраняет исходный question/CRLF/hash/generation/store guards и обязательно
  оставляет `query-original` missing. Original-only retrieval этим не исправлен.
- Advanced: **622 = 524 PASS / 98 FAIL**. Critical baseline **28 = 19 PASS / 9 FAIL**;
  прежние critical mutants не запущены из-за baseline failure. Девять независимых
  downstream steps FAIL; dependent adversarial mutation SKIPPED.
- Все шесть main/P1 platform SDK jobs SUCCESS. Actual runtime audit: 19 scoped
  logs, 15 SDK invocations, 30 structured/text lanes, 420 prepared observations.
  Во всех 30 restart/repeat lanes `derived_writes=0`, source/generation сохранены,
  stale-null CAS отклонён. Installed scripted harness 1/1 PASS.
- Release build/wheels/sdist/installer/required-release SUCCESS; publish/public/
  registry SKIPPED. Реальные Claude Code/Codex/OpenCode sessions — **NOT RUN**.
- Legacy self-host: 2812 tracked files / 119596587 bytes, 10 members / 98 sections;
  подготовка подтверждена, quality **10/16**, original-query lineage **0 < 12**.
  V2 останавливается на inactive catalog witness `wiki/Commands.md`; собственного
  V2 JSON/provenance нет. Retrieval evidence: 24/48 budget cases выше сохранённого
  800-token gate, максимум 1451 по pinned offline BPE. Все эти gates остаются FAIL.

Источники: [main CI 37843013319](https://github.com/Vanilla1999/DocAtlas/actions/runs/37843013319),
[P1 37843013402](https://github.com/Vanilla1999/DocAtlas/actions/runs/37843013402),
[release 37843013743](https://github.com/Vanilla1999/DocAtlas/actions/runs/37843013743).
`required-ci` job `113541340466` и `p1-stack-exact` job `113541501846` — FAILURE.
Это полный наблюдавшийся CI, а не merge-ready результат.

Перед critical migration исходные core JUnit повторно получены из GitHub artifacts
и проверены по опубликованным ZIP SHA256:

| Python | Artifact ID | ZIP SHA256 |
| --- | --- | --- |
| 3.11 | 11579011225 | `b9d31db8369a9de5fb8f0f71d1b8d473697ebe63bcf2b1a76cc291e23371138f` |
| 3.12 | 11578144988 | `1112bd66f10cab9f91471e457dcca457820d090d735b91499ca7babe1d234abd` |
| 3.13 | 11578578769 | `21efeb193c23b5c9e2bd489d6e2d773657da97ad8686c903a97b3621b2eb0c2f` |

Следующее разрешённое продолжение — узкая миграция
`PR211_CRITICAL_CONTRACT_PROPOSAL_RU.md`; ownership и уточнение двух literal
complete cases зафиксированы в current decisions и completion ledger.
Этот раздел сохраняет baseline **7a78c51**. Новый slice считается проверенным
только по фактическому CI его последующего HEAD; чужой PASS не наследуется.

## Исторический полный прогон: 991638f; member/mtime и self-host setup

Обновление: 2026-10-08. Полный [CI 37840422988](https://github.com/Vanilla1999/DocAtlas/actions/runs/37840422988)
завершён на HEAD `991638f28ecff659c320b45738edfaa8b9fd375e`, merge checkout
`e499c39704d4923164dc50c1460a2e1c50b81d7f`, tree
`955bac94d5ca6b847f558b0e7dbd0dcb8265e9df`. Все 25 опубликованных файлов сверены
с reviewed bytes; четыре commits — обычный fast-forward обеих веток.

- Python 3.11/3.12/3.13: **8513 = 6496 PASS / 1946 FAIL / 61 ERROR / 10 SKIP**.
  Полные concrete roster и outcomes одинаковы. Против 04ff ровно **7 FAIL→PASS**,
  добавлены шесть новых self-host nodes: пять PASS, один FAIL. Удалений и прежних
  PASS regressions нет. Реконструкция полного roster из baseline + delta точная.
- Семь из восьми member/read/mtime targets прошли, включая foreign same-path,
  hash-first stale reads, exact descriptor mtime и mtime-only touch без read writes.
  Module manifest target прошёл explicit sync, но сохранил FAIL уже на public
  `insufficient_evidence / required_evidence_missing`; исходные вопросы не изменены.
- **141/141** member/descriptor/trusted-storage/hash/CAS controls PASS в каждой Python.
  Из 2006 старых nodes с прежним FAIL/ERROR у десяти первый barrier прошёл дальше:
  module manifest и девять self-host downstream consumers. Остальные 1996 первые
  причины прежние; 47 diagnostic ERROR сохранили exact messages и barriers.
  Эти десять advances не являются PASS или исправлением deferred retrieval.
- Пять новых self-host safety tests PASS: полный tracked mirror/config/hash
  fidelity, точный catalog membership с physical distractors, cold no-grant,
  conflict/hash/CAS отказ до записи и environment/original preservation.
  Шестой test прошёл cold/prepare/generation/store guards, затем получил public
  `status=insufficient_evidence`. JUnit содержит только status; reason/kind и полный
  DTO этого нового node не раскрыты, CRLF failure не установлен.
- Advanced: **622 = 524 PASS / 98 FAIL**, прежние roster/states. Девять независимых
  downstream steps фактически FAIL; dependent adversarial mutation SKIP после
  красного baseline. Critical baseline **19/28 PASS**, mutants не стартовали.
- Legacy self-host JSON подтверждает **2807 tracked files / 119478143 bytes**, exact
  merge/tree, cold_read_verified=True, **10 members / 98 sections**, zero deletions
  и origin_unchanged_after_calls=True. Теперь **10/16 cases PASS**; оставшиеся
  frozen floors включают original_query_coverage **0 < 12** и contamination count 1.
- V2 остановился на validate_corpus: `witness is not an active catalog document:
  wiki/Commands.md`. Его JSON/provenance не создан; собственный V2 prepare не
  объявляется доказанным только из порядка вызовов. Catalog/gold не подменялись.
- Все **6 platform SDK jobs PASS**. Main package/CLI **77/77** на Ubuntu, macOS ARM
  и Intel. Проверены **19 logs / 15 SDK invocations / 30 lanes / 420 observations**;
  source bindings и outcomes совпадают с 04ff. Во всех 30 restart/repeat lanes
  derived_writes=0, stale-null CAS rejected, source/generation rows unchanged.
- Installed scripted harness **1/1 PASS**. Release build, три wheels,
  sdist/installer и required-release **PASS**; публикация release SKIP.
  Actual Claude Code/Codex/OpenCode sessions **NOT RUN**; SDK не заменяет эти apps.
- Все 17 workflows completed: **8 SUCCESS / 8 FAILURE / 1 SKIPPED**. Required CI
  **113532153123 FAILURE**, P1 aggregate **113532324954 FAILURE**.

Catalog source не менялся: прежние **6918 bytes**, docs output schema **860 bytes**.
Владелец снял fixed catalog ceilings; продолжается минимизация с сохранением guards.
Отдельные output <1000 и frozen retrieval 800 сохранены. Все 80 BPE values прежние,
80/80 canonical UTF-8 byte measurements сверены; max **1451** и **24/48** within-budget
cases выше 800. Это pinned offline BPE, не цена actual app/model sessions.

[Полный acceptance 991638f](PR211_991638F_ACCEPTANCE.json) содержит завершённые jobs,
actual runtime, downstream/Legacy provenance и границы утверждений.
[Core delta](PR211_991638F_CORE_ACCEPTANCE.json) содержит все семь transitions,
шесть новых состояний, три JUnit bindings и security/first-barrier comparison.
Исторические reports ниже не переносят PASS на последующие commits.

### Следующий узкий successor нового synthetic positive

Source review установил самостоятельный literal qualification blocker: исходный
вопрос ``What does `MirrorNeedle` require?`` даёт четыре raw terms; в прежнем RULES
совпадает только MirrorNeedle. require не равен requires по текущему контракту,
1/4 < 0.4. Это source-grounded blocker, не восстановленный hidden CI reason.

В новом fixture test сохраняются исходные question, RULES/CRLF и все source/hash/
snapshot/storage guards. Только prepared public call получает отдельно заданный
host lookup `` `MirrorNeedle` explicit preparation ``. Lookup должен иметь собственный
credit, не credit query-original; answer/edit authority остаются False. Это
synthetic lifecycle/read-wiring positive, не исправление original-question quality.
[Author review](PR211_SELF_HOST_LITERAL_LOOKUP_REVIEW_RU.md) и
[independent review](PR211_SELF_HOST_LITERAL_LOOKUP_INDEPENDENT_REVIEW_RU.md).
Runtime этого successor **NOT RUN** на момент записи; следующий actual CI проверяется
на новом HEAD после обычного push. Frozen downstream questions/corpus/scoring,
production retrieval и qualification не меняются.

**PR пока НЕ ГОТОВ к merge.** Required gates остаются красными. Отдельный
[critical contract proposal](PR211_CRITICAL_CONTRACT_PROPOSAL_RU.md) описывает
устаревшие classifier expectations и отсутствующий mutation anchor; это PENDING
согласования frozen criteria. Три deferred retrieval направления, gold и остальные
gates сохранены по CURRENT_WAVE_DECISIONS_RU.md. Merge/force-push/release не выполнялись.


## Исторический полный прогон: 04ff1dd; четыре migrations подтверждены

Обновление: 2026-10-08. Полный [CI 37833279436](https://github.com/Vanilla1999/DocAtlas/actions/runs/37833279436)
завершён на HEAD `04ff1dda57efb5236d7b3577d4e2736b2820df5b`, merge checkout
`1d750c0f2926ccad325f4ecb1440c623022110ec`, tree
`745fc099952eacbbe1fb5fb462e02ff0b0d0eaac`.

- Python 3.11/3.12/3.13: **8507 = 6484 PASS / 1952 FAIL / 61 ERROR / 10 SKIP**.
  Roster и outcomes одинаковы. Против 0358365 ровно **4 FAIL→PASS**: provenance,
  identity collision, policy text fidelity и exact Dartdoc. Новых/удалённых nodes,
  PASS regressions и неожиданных transitions нет.
- Из 2013 сохранивших FAIL/ERROR nodes у 47 диагностических fixture errors вместо
  IndexError теперь содержательный AssertionError; у остальных 1966 первая
  причина прежняя. Эти 47 errors **не исправлены**.
- Все 47 cases на каждой Python показывают `insufficient_evidence / docs_context /
  required_evidence_missing`, `error=None`, `source_count=0`. Видны stage counts:
  retrieved_candidates=1, query_window=1, rankings=0, qualified_fragments=0;
  projector stage пуст. Дополнительные flags и missing requirement IDs сокращены
  pytest и остаются неизвестны. Source ordering подтверждает typed block до
  projector, но не доказывает конкретную скрытую причину admission. Обход этого
  block или изменение исходных вопросов ради запуска guard tail не выполнялись.
- Advanced: **622 = 524 PASS / 98 FAIL**, полный roster/states прежние. Все девять
  независимых downstream steps выполнены и FAIL с прежними первыми причинами;
  зависимый adversarial mutation SKIP после красного baseline. Critical baseline
  **19/28 PASS**, mutants не стартовали.
- Все **6 platform SDK jobs PASS**. Main package/CLI: **77/77 PASS** на Ubuntu,
  macOS ARM и Intel. Проверены 19 actual logs, 15 SDK invocations, 30 structured/text
  lanes и 420 observations; source bindings, default/advanced cold guards,
  large/partial delivery и restart/CAS совпадают с 0358365.
- Installed scripted harness **1/1 PASS**. Release build, три wheels,
  sdist/installer и required-release **PASS**. Actual Claude Code/Codex/OpenCode
  application sessions **NOT RUN**; CLI stubs и SDK их не заменяют.
- Все 17 workflows завершились: **8 SUCCESS / 8 FAILURE / 1 SKIPPED**.
  required-ci **113507696834 FAILURE**, P1 aggregate **113507192604 FAILURE**.

Catalog source не менялся: прежнее измерение **6918 bytes**, docs output schema
**860 bytes**. Фиксированные catalog ceilings сняты владельцем; продолжается
обоснованная минимизация без нового magic number. Output schema <1000 и отдельный
frozen retrieval criterion 800 остаются. Retrieval max **1451 pinned offline BPE
 tokens**, **24/48** within-budget cases выше 800; все 80 BPE values прежние,
80/80 canonical UTF-8 byte measurements сверены. Это не стоимость app sessions.

[Полный acceptance 04ff1dd](PR211_04FF_ACCEPTANCE.json) содержит завершённые
workflows/jobs, advanced/downstream/retrieval и installed SDK matrix.
[Core delta](PR211_04FF_CORE_ACCEPTANCE.json) содержит четыре точных transitions,
три JUnit artifact bindings и диагностические/source-order evidence.
Исторические reports ниже сохраняются; PASS не переносится на следующие commits.

**PR пока НЕ ГОТОВ к merge:** полный core/advanced и required gates красные,
actual app-client acceptance отсутствует. Следующие возможные fixture setup
migrations рассматриваются отдельно по текущему контракту. Deferred retrieval,
gold, thresholds и guards не меняются; ordinary push разрешён, merge/release/
force-push не выполнялись.

## Подготовленный следующий пакет: member/read и mtime

Следующие source changes имеют independent review, но runtime **NOT RUN** на
момент записи. Предыдущие6484 PASS и actual SDK outcomes относятся только к04ff.

- Шесть существующих module/foreign/stale-read fixtures используют настоящий
  explicit member transaction. Два прежних catalogs сохранены буквально;
  четыре README fixtures получили единственное supporting/overview membership.
  Foreign upsert использует captured CAS того же store; owned и foreign rows
  сохраняются вместе. Перед stale negatives есть реальное непустое чтение
  исходного вопроса. [Author review](PR211_MEMBER_READ_FIXTURE_REVIEW_RU.md),
  [independent review](PR211_MEMBER_READ_FIXTURE_INDEPENDENT_REVIEW_RU.md).
- Production member transaction сохраняет mtime из уже checked descriptor.
  Это устраняет отсутствующий timestamp/ложный metadata drift, сохраняя
  hash-first stale contract. Два прежних tests проверяют exact mtime, отсутствие
  drift до touch и неизменность source/generation rows после чтения. Первая
  последующая **явная** sync старой metadata либо после mtime-only touch может
  создать generation; read-path repair не добавлен. [Author review](PR211_MEMBER_MTIME_REVIEW_RU.md),
  [independent review](PR211_MEMBER_MTIME_INDEPENDENT_REVIEW_RU.md).
- Дополнительный review поймал обязательную description в двух новых catalogs;
  она исправлена до publication. Старое одобрение отозвано, corrected bytes и
  объединённые три functions в test_docs_service.py перепроверены.
  [Integration review](PR211_MEMBER_INTEGRATION_REVIEW_RU.md).

Восемь targets фактически FAIL на baseline04ff, пять modules содержат108 cases
(32 PASS/76 FAIL) и97 base names. Collection/decorators/параметры не меняются.
Отдельно проверяются ранее зелёные109 member/descriptor tests,30 trusted-storage
и2 fixture hash/CAS controls. Production metadata change не даёт оснований
переносить прежний zero-write SDK repeat PASS на новый SHA.

Self-host setup подготовлен отдельным slice: полная копия всех tracked regular
files сохраняет физические unselected distractors; membership берётся только из
неизменённого literal catalog. В copied config меняется только index.db_path на
изолированный host store. Настоящий cold public read должен подтвердить отсутствие
storage/grant; затем требуется explicit confirmed preparation с полными original
content/catalog/entry hashes и CAS None. Ошибочный cold ответ останавливает run
до подготовки и вопросов. Исходные questions, lookup_queries, scopes, positive/
negative loops и scoring/floors сохранены. Actual checkout/import origins, все
копируемые bytes и generation записываются в additive artifact provenance.
[Author review](PR211_SELF_HOST_FIXTURE_REVIEW_RU.md) и
[independent review](PR211_SELF_HOST_FIXTURE_INDEPENDENT_REVIEW_RU.md) фиксируют
точный scope; шесть новых fixture safety tests дополняют прежний roster.
Runtime нового setup **NOT RUN** на момент записи; Git witness копии — not_git,
это не проверка original storage config, Git auto-sync или actual app client.

Отдельный [critical gate contract proposal](PR211_CRITICAL_CONTRACT_PROPOSAL_RU.md)
подтверждает две причины: девять ожиданий required/forbidden относятся к retired
prose classifier, а mutation anchor отсутствует в текущем source. Предложены
проверки сохранности исходного текста/отрицаний/границ и отсутствия authority,
сохраняющие все 26 fixtures и Python grammar controls. Это **предложение для
согласования frozen criteria**, tests/gate/gold не изменены и mutants не запущены.

Deferred retrieval, frozen gold/thresholds и client requirements сохраняются.
После обычного push проверять actual GitHub CI нового HEAD; исторические
acceptance documents не являются динамическим status CI.

## Исторический полный прогон: 0358365; четыре contract-fixture migrations

Обновление: 2026-10-08. Полный [CI 37830452263](https://github.com/Vanilla1999/DocAtlas/actions/runs/37830452263)
завершён на HEAD `03583656617336a746e9192249467017d6131f29`, merge checkout
`96767d8d8499b28a701bc20055277a7362d63aa3`, tree
`b77cb4c3ed5bd60dd0ab47cd0398f1664bfd6ae1`.

- Все три Python 3.11/3.12/3.13: **8507 = 6480 PASS / 1956 FAIL /
  61 ERROR / 10 SKIP**. Против 3be9c34 ровно **24 FAIL→PASS**, ноль новых,
  удалённых, PASS→FAIL или неожиданных state transitions. Исходный focused
  791/801 не был этой полной CI-матрицей.
- Из предыдущих 25 targets прошли 24. Source-continuation fixture теперь
  действительно проходит confirmed member preparation, затем останавливается
  на `assert 'query-original' in ['query-lookup-1']`. Перенос lookup coverage на
  исходный вопрос не разрешён; этот deferred retrieval failure не скрывается.
- Промежуточный `4320a68` добавил module-size regression (1039 строк). В
  `0358365` тело fidelity test AST-exact перенесено в существующий shared helper;
  test IDs и guards прежние, модуль теперь 974 строки. Static, P2 federated и
  соответствующий core guard снова **PASS**, предел 1000 не изменён.
- Advanced: **622 = 524 PASS / 98 FAIL**, roster/states совпадают с 3be9c34 и
  4320a68. Все девять независимых downstream steps выполнены и FAIL с прежними
  первыми причинами. Critical baseline **19/28 PASS**, mutants не запускались.
- Все **6 platform SDK jobs PASS**; main package/CLI — **77/77 PASS** на каждой
  платформе. 19 actual logs подтвердили 15 SDK invocations, 30 structured/text
  lanes и 420 prepared observations. Source-binding digests и outcomes прежние.
  Release build, три wheels, sdist/installer и required-release **PASS**.
- Все 17 workflows завершились: **8 SUCCESS / 8 FAILURE / 1 SKIPPED**.
  `required-ci` job **113497770623 FAILURE**, P1 aggregate **113498272845 FAILURE**.
  Actual Claude Code/Codex/OpenCode sessions по-прежнему **NOT RUN**.

Catalog остаётся **6918 bytes**, отдельная docs output schema **860 bytes**.
Фиксированные catalog ceilings 6144/10240 сняты владельцем; нового magic number
нет. Остальные guards, output schema <1000 и frozen retrieval criterion 800
сохраняются. Retrieval gate: maximum **1451 pinned offline BPE tokens**,
**24/48** within-budget cases выше 800; все 80 measurements прежние. Это не
фактическая стоимость в приложениях или за целую задачу.

### Следующий пакет и границы его проверки

| Slice | Сохранённое проверяемое свойство |
|---|---|
| Provenance API fixture | Точный ValueError для hidden_test_answer; убран только retired positional display budget |
| Identity collision | Разные content bindings одного stable ID отвергаются; одинаковые bindings дают валидные непустые data без edit authority |
| Policy text fidelity | Все три исходные фразы и весь text/hash/path сохраняются как untrusted source data; не выводятся policy или edit permissions |
| Exact Dartdoc fixture | Прежний class URL и отдельный robots control; настоящий pinned transport через MockTransport, те же extraction/browser guards, negatives без дополнительных requests |
| Guard setup diagnostics | 47 прежних ERROR остаются; metadata/stage counts должны показать настоящий upstream reason вместо одного IndexError |

Production, retrieval, исходные вопросы/corpora, gold, thresholds и workflows
не меняются. Collection IDs/параметры сохранены. Независимые reviews описывают
точные bytes; source-collision и provenance меняют разные nodes одного файла,
поэтому их integration проверяется отдельно по AST. Runtime следующего пакета
**NOT RUN** на момент записи: результаты 0358365 на него не переносятся.

[Полный compact acceptance 0358365](PR211_CONTRACT_FIXTURE_ACCEPTANCE.json) содержит
завершённые workflows/jobs, advanced/downstream/retrieval, actual installed SDK
matrix и границы claims. [Core delta](PR211_CONTRACT_FIXTURE_CORE_ACCEPTANCE.json)
содержит все 24 transitions, hashes и три JUnit artifacts. Исторические baseline
и оставшиеся причины ниже сохраняются. Deferred retrieval не исправлялся.

**PR пока НЕ ГОТОВ к merge:** полный core/advanced и required gates красные,
actual app-client acceptance отсутствует. Обычный push разрешён; merge,
release и force-push не выполнялись. Продолжаются только обоснованные narrow
migrations и диагностика; ошибки не переводятся в PASS заменой gold/thresholds.

## Исторический полный прогон: 3be9c34 и пакет из 25 targets

Обновление: 2026-10-08. Последний полностью выполненный main CI:
[37824782946](https://github.com/Vanilla1999/DocAtlas/actions/runs/37824782946),
HEAD `3be9c34afa49dcf4278d2910ec29ed37c305225c`, merge checkout
`fc1b4cf20e3e561a03230adcd67dd920e8464bdc`, одинаковый tree
`b27a3a70a6e3796e5e76a59395330843c7784656`.

- Core Python 3.11/3.12/3.13: на каждой **8507 = 6456 PASS / 1980 FAIL /
  61 ERROR / 10 SKIP**. Все concrete IDs и outcomes совпали. Против 40032f7
  ровно **6 FAIL→PASS** — шесть indexed MCP fixtures; новых/удалённых nodes,
  PASS regressions и иных state changes нет. Предыдущие 35 исправлений также
  сохраняются. Исторический focused 791/801 не заменяет эту полную матрицу.
- Advanced: **622 = 524 PASS / 98 FAIL**, все states прежние. Все девять
  независимых downstream steps выполнены и FAIL; adversarial mutation правильно
  SKIPPED после красного полного baseline. Required CI **FAILURE**.
- Docs contract, static, installer и installed MCP harness PASS. Все три main
  platform suites дали **77/77 PASS**, затем реальный SDK stdio PASS.
  Все три P1 stack platform SDK также PASS. Release build, wheels 3.11/3.12/3.13,
  sdist/installer и required-release PASS; release не публиковался.
- Actual SDK: 19 logs, 15 invocations, 30 structured/text prepared lanes и
  420 case observations. Все matrix outcomes, metrics и normalized source
  bindings совпадают с 40032f7. Large delivery: **39372 unique UTF-8 bytes,
  50 sources**; partial: **94 bytes**, один source и прежний missing marker.
  Это реальный MCP SDK transport и installed package evidence. Claude Code,
  Codex и OpenCode application sessions по-прежнему **NOT RUN**.
- Все 17 workflows завершились: **8 SUCCESS / 8 FAILURE / 1 SKIPPED**.
  P1 stack overall FAIL при зелёных installed SDK lanes. Green release validation
  не означает green main CI или разрешение выпуска.

Catalog **6918 bytes**, output schema **860 bytes**. Владелец снял фиксированные
catalog ceilings 6144/10240; продолжаются минимизация и измерение без нового
magic number. Output schema <1000 и остальные guards/gates не отменены.
[Актуальные решения](CURRENT_WAVE_DECISIONS_RU.md).

## Следующий пакет на публикацию и общий CI

Подготовлены отдельные reviewed slices для **25 известных baseline failures**:

| Slice | Смысл изменения | Прежние FAIL nodes |
|---|---|---:|
| Recovery diagnostics | Display cap 220 заменён точным сохранением длинного исходного вопроса; parser prohibition прежний | 3 |
| Unified MCP surface | Nullable scope с schema negatives; fidelity/no-authority guidance; реальные library examples без mode | 3 |
| Model-visible projection | Отменённый display cap и удаление missing IDs заменены full-DTO fidelity; validator/authority/confirmation/hard-stop guards сохранены | 4 |
| Source continuation | Настоящий confirmed member transaction для прежнего finite docs/jobs.md fixture; весь public read/tamper/change tail прежний | 1 |
| Installed bootstrap | Canonical/root guidance сокращён 267→249 managed words при сохранении правил; installer threshold не повышен | 8 |
| Installed lookup meaning | Две полные эквивалентные clauses сохраняют запрет переноса coverage на original question | 6 |

Все base IDs/параметры и diagnostic inventories сохранены. Новые negative controls
добавлены внутри существующих cases. Production retrieval, corpora, gold, thresholds
и workflow configuration не меняются. Из product files меняются только canonical
agent guidance и синхронный root SKILL tail. Ранние варианты compaction получили
CHANGES REQUIRED из-за literal-clause/root parity regressions; они исправлены до
публикации. Финальные review reports связаны с точными source hashes.

Runtime этого следующего пакета **NOT RUN** на момент записи checkpoint. Ни один
из 25 исправленных tests не объявляется PASS до CI следующего опубликованного SHA.
Source continuation может открыть следующую границу после исправления setup;
сравнение обязано учитывать и такой FAIL→FAIL с новой причиной.

## Подтверждённые оставшиеся причины на 3be9c34

| Gate | Первая фактическая граница |
|---|---|
| Recovery | Ожидаемый parsing origin против actual retrieval_miss; до fixture setup |
| Recovery mutation | Красный полный recovery baseline; mutants не запускались |
| Hermetic project context | 1/16 PASS, 15 FAIL по frozen query-plan/intent contract; retrieval не выполнялся |
| Legacy и V2 self-host | Legacy sync без explicit mutation; отдельный project-config/host-storage conflict также требует решения |
| Question surface | 0/100 по frozen semantic expectations |
| Agent V1 и adversarial | Setup теперь дошёл до ValueError: fixture requires a nonempty finite docs-only catalog; missing catalogs не создавались; собственные adversarial cases не достигнуты |
| Critical mutation | Baseline 28 cases: 19 PASS / 9 FAIL по normative modality; mutants не запускались |
| Retrieval evidence | **1451** tokens maximum full DTO при frozen criterion **800**; превышают **24/48** within_budget cases |

1451 — счётчик pinned offline `docatlas-offline:o200k_base`, не фактически
измеренная стоимость в приложениях Claude Code/Codex/OpenCode и не история
повторных запросов. Catalog policy не снимает этот отдельный frozen gate.

Triage core выделяет 89 mutation-grant failures, 61 setup error, 30 stale ABI
failures и 19 remote explicit-member failures. Это формы ошибок, не обещание
механических fixes: lifecycle groups включают auto-prune/vector semantics,
а ABI tests также требуют старых caps и inferred authority. У десяти admission
invariant ERROR пустой captured projection; их последующие query-need/typed_local
expectations также конфликтуют с текущим literal qualifier. Подстановка lookup
или ручных proof flags не является сохранением этих guard tests.

Это не разрешение заменить ожидания фактическими значениями, снизить thresholds,
переписать frozen gold или исправлять deferred retrieval. Исходный HEAD 21fe472d
имеет существующий красный [CI 37796983129](https://github.com/Vanilla1999/DocAtlas/actions/runs/37796983129).
Точное per-node сопоставление с ним не выполнено: JUnit artifacts отсутствуют,
а connector отклонил original core log из-за предела response body 8 MiB.
По одному job status нельзя назвать весь остаток pre-existing относительно 21fe.
Прежняя фраза «полный CI на 21fe не выполнялся» исправлена этим уточнением.

## Evidence

- [Полный compact acceptance 3be9c34](PR211_RUNTIME_FOLLOWUP_ACCEPTANCE.json):
  workflows/jobs, advanced/downstream, retrieval metrics, реальные SDK origins и
  30 ссылок на одну одинаковую нормализованную 14-case delivery matrix.
- [Core delta 3be9c34](PR211_RUNTIME_FOLLOWUP_CORE_ACCEPTANCE.json): точные шесть
  transitions, hashes и три JUnit matrices; roster восстанавливается из f0 +400 delta.
- [Core delta 40032f7](PR211_FOLLOWUP_CORE_ACCEPTANCE.json): прежние 35 transitions.
- Полный f0 baseline: [manifest](PR211_CONTINUATION_ACCEPTANCE.json),
  [roster](PR211_CONTINUATION_OUTCOMES.json.gz), [отчёт](PR211_CONTINUATION_ACCEPTANCE_RU.md).

**PR НЕ ГОТОВ к merge:** required CI и семантические gates красные, actual client
acceptance не выполнен. Обычный push разрешён; merge, release и force-push — нет.
Deferred retrieval остаётся без изменений. После публикации нужен один совместный
CI нового HEAD с полным concrete-node сравнением; PASS snapshots не наследуется.

## Историческое состояние перед f0ed956

## Текущая волна от df9b682 — review завершено, новый CI ожидается

Обновление: 2026-10-08. Работа продолжается от
`df9b682fdd13d8f4d1c5bff6cc4bfc0286e5f8ce`; это следующий snapshot существующей
PR #211. Новые runtime outcomes пока **NOT RUN** и не наследуют PASS исходного CI.

Владелец явно отменил фиксированный catalog ceiling и указал стремиться к минимуму.
Прежние 6144/10240 bytes больше не являются default merge gates; нового числового
порога нет. Canonical catalog сокращён 7066→6918 bytes, output schema остаётся
860 bytes. Measurement, per-tool attribution, normal/advanced separation,
validation и source/consent/authority guards сохранены.
[Актуальное решение](CURRENT_WAVE_DECISIONS_RU.md),
[policy review](PR211_CATALOG_POLICY_REVIEW_RU.md).

Собраны отдельные reviewed slices:

- [Confirmed member transactions](PR211_MUTATION_FIXTURE_REVIEW_RU.md),
  [независимый review](PR211_MUTATION_FIXTURE_INDEPENDENT_REVIEW_RU.md) и
  [точечное обновление diagnostic inventory](PR211_MUTATION_INVENTORY_INDEPENDENT_REVIEW_RU.md).
  Сохранены 21 прежний concrete case, добавлены два integrity tests.
- [Finite code membership fixtures](PR211_MEMBERSHIP_FIXTURE_REVIEW_RU.md) и
  [независимый review](PR211_MEMBERSHIP_FIXTURE_INDEPENDENT_REVIEW_RU.md).
  Все 64 прежних test nodes и 218 assert AST сохранены.
- [Literal question boundary](PR211_QUESTION_BOUNDARY_REVIEW_RU.md) и
  [независимый review](PR211_QUESTION_BOUNDARY_INDEPENDENT_REVIEW_RU.md).
  303 прежних concrete nodes сохранены; изменены 295 cases в шести functions.
  Это producer-boundary tests, не сертификат downstream semantic sufficiency.
- [Дополнительное сокращение catalog](PR211_CATALOG_CONTINUATION_REVIEW_RU.md) и
  [независимый review](PR211_CATALOG_CONTINUATION_INDEPENDENT_REVIEW_RU.md):
  constraints и output прежние, 38 meaningful negative controls проверены review.
- [Literal source/gap fixtures](PR211_DICTIONARY_FIXTURE_REVIEW_RU.md) и
  [независимый review](PR211_DICTIONARY_FIXTURE_INDEPENDENT_REVIEW_RU.md):
  27 затронутых baseline failures, все 129 прежних nodes и 112 assert AST сохранены.

Последний полностью выполненный baseline —
[df9b682 CI 37811010878](https://github.com/Vanilla1999/DocAtlas/actions/runs/37811010878):
core на каждой Python 3.11/3.12/3.13 — 8505 cases, 6031 PASS, 2403 FAIL,
61 ERROR, 10 SKIP; advanced — 622 cases, 524 PASS, 98 FAIL.
После публикации нового snapshot обязателен полный совместный CI с concrete-node
сравнением, отдельным учётом двух новых tests и проверкой прежних PASS.

Deferred retrieval и frozen gold остаются без изменений. Остальные CI/downstream
и installed/client requirements не отменены. PR пока **НЕ ГОТОВ к merge**.
Merge, release и force-push не разрешены.

## Исторический checkpoint предыдущей волны

Дата: 2026-10-08. **PR пока НЕ ГОТОВ к merge.** Это evidence и точный остаток,
не merge/release approval. Retrieval, frozen gold, thresholds и действующие
числовые gates не изменены.

## Ветка и проверенная версия

- Начальная точка этой волны: `21fe472d983f394130849d6fd4e582043d58e9ba`.
- Рабочая ветка: `implementation/pr211-merge-readiness`, создана от PR #211.
- Все одобренные slices собраны обычным fast-forward в существующую
  `integration/stage3-v2-identity-pr1`, [PR #211](https://github.com/Vanilla1999/DocAtlas/pull/211).
- Tested source/test HEAD: `0a60111dc6de50f78f08239bd3ee9fcc3a31ad0d`.
- Фактический checkout основного CI: merge SHA `87403a079ac209641edc4b83bd08e9fd37855d46`.
- Base main: `d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c`.
- Git tree HEAD и merge checkout идентичен: `2cdd8e5eb4c51cbd4b067e538c43e1fbe5a24023`. Конкретные run/job IDs,
  Python versions, artifact/XML hashes и правила подсчёта сохранены в
  [acceptance manifest](PR211_ACCEPTANCE.json).

Этот checkpoint и evidence публикуются отдельным documentation commit после
проверенного source/test HEAD. Source, tests и CI configuration в нём не меняются;
обычный CI запускается также на его HEAD. Самоссылочный SHA документа не требуется.
Force-push, merge, release и публикация сообщений от имени владельца не выполнялись.

## Что завершено

1. **Три исходные test migrations.** Resource examples используют unified
   library call; scope guidance проверяет сохранённый смысл и связь с нужным
   параметром; отменённый output cap ≤200 заменён fidelity-проверкой полного
   результата. Source/hash/span, missing, hard-stop и no-edit-authority guards
   сохранены. [Первый review](PR211_SLICE1_REVIEW_RU.md).
2. **Trust-resource conflict разрешён по контракту.** Root AGENTS/CLAUDE и
   другие repository files остаются `untrusted_data`; имя и scope дают
   attribution, но не instruction authority или разрешение WebFetch.
   Положительные и отрицательные controls используют реальные annotator и
   policy builder; forged caller policy не принимается.
   [Обоснование trust](PR211_TRUST_CONTRACT_REVIEW_RU.md).
3. **Catalog сокращён 7602→7066 bytes без смены лимита.** Удалены только
   логически избыточные schema конструкции и повторяющиеся пояснения. Output
   schema сохранена буквально: 860 bytes. Пять equivalence tests выполняют
   authored boundary matrix из 417 cases; проверяют прежнюю область допустимых
   inputs и отказы до service I/O.
   [Schema review](PR211_CATALOG_REVIEW_RU.md),
   [независимый review](PR211_CATALOG_INDEPENDENT_REVIEW_RU.md).
4. **Безопасный runtime выполнен.** Все пять прежних scope scenarios прошли.
   Source stdio и installed wheel/sdist проверки используют отдельные fixture
   homes и реальные MCP sessions. SDK validation-text error корректно отделён
   от обычного JSON decoding; default и advanced sessions проверяются отдельно.
   [Статический review harness](PR211_RUNTIME_REVIEW_RU.md);
   фактические runtime outcomes и job IDs — в
   [acceptance manifest](PR211_ACCEPTANCE.json).
5. **Дополнительные узкие migrations прошли review и CI.** Guidance не требует
   прежних inferred rewrites; release-resource checks проверяют public schemas
   и реальный resource getter; четыре MCP fixtures объявляют finite source
   membership и сохраняют реальные wide/narrow budget controls. Семь v4 caller
   fixtures задают явные literal content requirements и сохраняют complete
   positives, valid-partial negatives, host binding и прежние ceilings.
   [Caller follow-up](PR211_TASK_CALLER_CONTENT_WITNESS_REVIEW_RU.md),
   [независимый review](PR211_TASK_CALLER_SELECTOR_INDEPENDENT_REVIEW_RU.md).

Ни один прежний test node не удалён, не переименован, не переведён в skip/xfail
ради PASS. Старые assertions в узких slices сохранялись либо получали отдельно
обоснованный successor; семантические conflicts не подменялись actual values.
CI instrumentation добавила JUnit к существующим core/advanced commands и upload,
без изменения selectors, matrix, dependencies, timeouts, exit semantics или gates.

## Совместный acceptance

Основной [CI run 37808083737](https://github.com/Vanilla1999/DocAtlas/actions/runs/37808083737),
[release validation 37808083795](https://github.com/Vanilla1999/DocAtlas/actions/runs/37808083795).

| Проверка | Фактический результат на tested source/test HEAD |
|---|---|
| Core, Python 3.11 / 3.12 / 3.13 | **8505: 6031 PASS / 2403 FAIL / 61 ERROR / 10 SKIP**; roster и outcomes одинаковы во всех трёх versions |
| Advanced, Python 3.12 | **622: 524 PASS / 98 FAIL / 0 ERROR / 0 SKIP** |
| Пять scope variants | **5/5 PASS** |
| Source stdio / delivery module | **45 PASS** в delivery module, включая два actual source-stdio cases; эти два уже входят в 45 |
| Catalog equivalence | **5/5 PASS**, внутри них 417 authored boundary cases |
| Docs contract / static / installer | **PASS** |
| Installed platform smoke: Linux, macOS ARM, macOS Intel | **PASS** на всех трёх платформах |
| Installed-MCP harness | **PASS** |
| Required release: build, sdist/installer, wheels 3.11/3.12/3.13 | **PASS**; publish/registry/public-release jobs SKIPPED |
| Retrieval-evidence | **FAIL** на frozen 800-token criterion |
| Required CI | **FAIL** |

Числа core не суммируют три Python versions: сравниваются одинаковые конкретные
node IDs и их outcomes. В JUnit не обнаружено повторяющихся concrete node IDs; setup errors учитываются как
ERROR, существующие skips — отдельно. Десять skips: девять без local Qdrant и
один без generated story-PDF fixture. Они не добавлены этой волной.

По сравнению с первым полным CI на `b68759e`:

- Core: 5983 PASS / 2451 FAIL / 61 ERROR / 10 SKIP → 6031 PASS / 2403 FAIL / 61 ERROR / 10 SKIP; ровно **48 FAIL→PASS**.
- Advanced: 513 PASS / 109 FAIL → 524 PASS / 98 FAIL; ровно **11 FAIL→PASS**.
- Добавленных и удалённых cases нет. Переходов PASS→FAIL/ERROR/SKIP нет. Итого 59 улучшений в двух непересекающихся группах, без суммирования Python matrices.

Точный roster с outcomes сохранён в
[PR211_ACCEPTANCE_OUTCOMES.json.gz](PR211_ACCEPTANCE_OUTCOMES.json.gz), без raw
stack traces, DB/cache и user data. SHA-256 gzip и canonical JSON — в manifest;
gzip имеет mtime=0. JUnit classname с class suffix преобразуется через найденный
repository module, затем `::Class::test`, а не слепой заменой всех точек на `/`.

Прочитать сохранённый roster можно обычным Python stdlib:

```python
import gzip, json
from pathlib import Path
ledger = json.loads(gzip.decompress(Path("v2plan/PR211_ACCEPTANCE_OUTCOMES.json.gz").read_bytes()))
```

## Что подтвердил настоящий MCP delivery

Source tests используют настоящий SDK/server subprocess. Installed checks
загружают `docmancer` из site-packages вне checkout, после установки wheel;
release validation отдельно проверяет sdist и wheels трёх Python versions.

Отдельные cold sessions проверяют отказы и default preparation; после перезапуска
default server проверяются повторное чтение и CAS. Source pytest подтверждает эти
фазы и отдельный advanced positive. Полная матрица scope/module/version, partial
и large delivery выполняется в prepared advanced фазе **installed smoke**.
В обоих transport lanes — structured и text — large case сохраняет **39372 уникальных
UTF-8 bytes из 50 sources**. Partial сохраняет source и точный missing reason;
несовпадающие scope/version не возвращают source bytes. Source/library generation
rows после read checks неизменны. Числа wire payload и конкретная platform
provenance сохранены в manifest; это не model tokens и не измерение UI клиента.

Project preparation проходит через confirmed cold MCP sync. Library-version
fixtures предварительно заполнены тестом; это transport/version proof, не
сертификация network library lifecycle. SDK stdio не подменяет настоящие
Claude Code, Codex или OpenCode clients. Их доступных executables в локальном
окружении нет; реальные application/client visibility checks — **NOT RUN**.
Новые локальные dependency/model/client downloads, provider calls и обращения
к пользовательским индексам не выполнялись.

## Оставшиеся blockers

### Catalog ceiling

Действующий gate **≤6144 bytes** остаётся FAIL: **7066**, превышение **922**.
Output gate **<1000** отдельно проходит: **860**. Catalog уже содержит output
schema; эти числа нельзя складывать или переводить в обещанные model tokens.

Независимые дополнительные structural/prose passes не нашли полного сокращения
до 6144 без потери условий или изменения интерфейса. Это не доказательство
математической невозможности. Конкретное предложение для отдельного решения
владельца — **catalog ≤7168 bytes (7 KiB)**, output <1000 без изменения.
Текущий catalog оставляет 102 bytes до предложенного ceiling. **Предложение
не одобрено; число в test/gate не заменено.** Основание для необходимости
отдельного решения: пункт 3 [CURRENT_WAVE_DECISIONS_RU.md](CURRENT_WAVE_DECISIONS_RU.md).

### Полный CI и текущие contracts

Количество failures существенно больше старого focused run 791/801.
[Исторический triage b687](PR211_CORE_FAILURE_TRIAGE_RU.md) воспроизводимо
выделяет 1013 FAIL и все 61 ERROR: question planning/aliases, semantic admission,
старые ingest/sync без mutation grant, отсутствующие captured projector stages
и finite source membership. Это cohorts, не обещание простых fixes.

Для части read fixtures возможны узкие migrations на реальные member transactions
и explicit code_files с положительными source/hash/span controls. Другие tests
требуют прежних inferred policy/absence/edit semantics. Причина раннего delivery
veto в ряде projector fixtures пока не установлена по каждому seed. Остальные
failures нельзя автоматически объявлять устаревшими или pre-existing: полного
сопоставимого core CI на исходном 21fe нет.

Frozen retrieval gate по-прежнему отклоняет full model-visible DTO, превышающий
800-token ceiling по estimator этого gate. Advanced downstream recovery/mutation/project-context gates
**SKIPPED** после failure advanced pytest; JUnit upload прошёл. В связанных workflows остаются **FAIL** в P1 stack, P1 Agent Truth closure, P1.4, P1.5, P1.6, Language flow и Task 33C;
первые причины и точные run/job IDs отражены в manifest. P1.6 support mismatch
для legitimate_fact_survives_hostile_tail сам по себе не доказывает успешную
prompt injection; обязательный положительный support control не выполнен.

Original-only paraphrase, multi-section/long diversity и partial qualification/
admission остаются явно отложенными в
[RETRIEVAL_DEFERRED_ANALYSIS_RU.md](after-merge/RETRIEVAL_DEFERRED_ANALYSIS_RU.md).
Отсрочка не означает PASS и не разрешает исключить эти сценарии из gates.
Повышение одного catalog ceiling также не сделает весь PR зелёным.

## Исторический checkpoint 791/801

Предыдущий focused run относился к
`5310e6da83a09daa0938efa9cf68e2c0f7c99851`, не к конечному SHA этой волны и не
к полному CI. Исходный документ сохранён в
[21fe checkpoint](https://github.com/Vanilla1999/DocAtlas/blob/21fe472d983f394130849d6fd4e582043d58e9ba/v2plan/PR211_CHECKPOINT_RU.md).
Его exact 801-node roster и старые `/tmp/opencode/...` artifacts не доступны
в текущем workspace; равенство новому roster не заявляется. Новое evidence
сохранено отдельно, без суммирования пересекающихся запусков.

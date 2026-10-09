# PR #211: checkpoint продолжения

Обновлено 2026-10-09, 23:46 UTC. Reviewed code следующей публикации — до
`bdd9207bc6a935306e5922574a22691976f888a4` (slice83).
Slices77–83 прошли source review и exact commit/tree/blob verification.
Их совместный runtime ещё **PENDING**.

**PR пока не готов к merge.** Последний полный CI на1c6 собрал suite:
на каждой Python **7789 = 6031 PASS / 1748 FAIL / 0 ERROR / 10 SKIP**.
Снижение FAIL на30 включает retirement30; три исправившихся fixture cases
уравновешены тремя новыми failures. Одно суммарное число скрывает эту разницу.

## Действующие решения

- Потолки **6144 bytes / 800 tokens / 3 sources** отменены. Измеряем и сокращаем
  объём, сохраняя полные факты, source identity, scope/version/hash и consent guards.
- Операционные input/read/work/call/time ограничения сохраняются.
- Retrieval включён в позднее утверждённый план; прежний blanket deferral снят.
- Retirement требует собственного зелёного baseline, intended mutation kills и
  проверки всех сохраняемых helpers/imports/selectors. Остальные FAIL автоматически
  устаревшими не объявляются.
- Реальные Claude Code/Codex/OpenCode sessions **NOT RUN**. Installed SDK/stdio
  harness не подтверждает такие sessions.

План: [PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md).
Решения: [CURRENT_WAVE_DECISIONS_RU.md](CURRENT_WAVE_DECISIONS_RU.md).
История до067 сохранена в
[CHECKPOINT_067dd560_RU.md](pr211-execution/CHECKPOINT_067dd560_RU.md).
Последующие checkpoint и полный receipt ошибки collection38da доступны в Git history.
Local checkout устарел; начинать чтение с точного текущего PR HEAD.

## Последний фактический полный CI:1c6

PR HEAD: `1c6c2c8454cdd6fe797fe80e85f3b651aef01a0a`.
Фактический GitHub merge checkout:
`64caa3caf213a6a67d44c92546660ef1ced23d87`.
Parents: main `d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c` и этот PR HEAD.
Проверенное одинаковое дерево:
`8a544267409f0dbf3ab498dfa864c07b13cdfb73`.

[Main run38003248365](https://github.com/Vanilla1999/DocAtlas/actions/runs/38003248365).
[JUnit reader114068441329](https://github.com/Vanilla1999/DocAtlas/actions/runs/38003248365/job/114068441329):
все три Python3.11/3.12/3.13 имеют **6031 PASS / 1748 FAIL / 0 ERROR / 10 SKIP**,
integrity_issues=[] и omitted_rows=0. Матричные повторы не суммируются.

| Python | SHA256 JUnit1c6 |
| --- | --- |
|3.11|`5bdc3055863aab02c2717eaf47efc9fdb29b308377c23d7587f8c623421e0d6a`|
|3.12|`029b4916b92443138805214da1f8f005639f4a24659fdab75814dea304215307`|
|3.13|`9bd80acd9b653d77ad73084b1639aa6926f1b3cf5f53c4ee27217b0164be2298`|

Карта всех **218 failing modules / 1748 FAIL**:
[CORE_FAILURE_MAP_1c6c2c84.jsonl](pr211-execution/CORE_FAILURE_MAP_1c6c2c84.jsonl).
Содержит counts, первый node/message, доказанную triage и явный not_investigated.
Первый failure не классифицирует весь модуль. Старые карты0855/a348 сохранены.

### Что изменилось после предыдущего полного a348

a348: 7818 = 6030 PASS / 1778 FAIL / 0 ERROR / 10 SKIP.
38da между ними был collection ERROR, а не успешный пустой suite.
Slice71 восстановил внешний helper demand: на1c6 сбор снова полный.

| Модуль | Было PASS/FAIL | На1c6 PASS/FAIL | Значение |
| --- | ---: | ---: | --- |
|admission_meaning|4/30|4/0|30 obsolete cases retired; четыре live guards сохранены.|
|generic_context_workflows|20/41|23/38|Три настоящих fixture improvements; остальные требуют разбора.|
|context_projection_boundaries|14/6|13/7|Новый +1 FAIL; exact новый node в first-failure reader не виден.|
|pr211_catalog_equivalence|5/0|4/1|Routing spy не принимает новый read_only_startup keyword.|
|mcp_delivery_dispatch_boundary|3/0|2/1|Та же устаревшая сигнатура до intended PermissionError.|

Один новый независимый default control даёт ещё1 PASS; collected уменьшился на29.
Slice83 мигрирует два spy и source-confirmed fixture defect в projection:
setup после fingerprint создавал writable service и ставил spy на неиспользуемый
объект. Before/final fingerprints сохранены; теперь проверяется реальный reader
и отсутствие созданного writer. Связь этого дефекта именно с новым +1 FAIL до
нового traceback не заявлена. Existing JUnit reader расширен точечными node/trace
records. См. [READ_FACADE_TEST_MIGRATION](PR211_READ_FACADE_TEST_MIGRATION_RU.md).

### Отдельные проверенные семейства и jobs

| Семейство | Actual1c6 PASS/FAIL |
| --- | ---: |
|ActionPacket main / part02|31/0 и8/0|
|Context completion followup|1/1|
|Docs read-next|31/0|
|SourceMap|29/0|
|Member transactions|116/0|
|Alias / project-intent current contracts|1/0 и1/0|

Все семь invalid-storage и три real-service member nodes явно PASS на каждой lane.
Cold read начинается после fingerprint, не вызывает schema/job maintenance;
проверены denied SQL writes, invalid ledgers, Unicode spans, последующая explicit
writable preparation и чтение нового поколения прежним reader.
Member116 — доказательство этой границы, не всех library read paths.
Completion mkdocs-05 priority fact остаётся исходным реальным FAIL.

Docs-contract, docs-impact, static-contract, retrieval-evidence, installer,
installed MCP harness и все три platform-smoke jobs SUCCESS.
Core/advanced/required-ci FAIL; p1-harden-branch SKIP.
Installed harness не считается реальной client session.

## Сокращение тестов и сила контроля

[Advanced114066061733](https://github.com/Vanilla1999/DocAtlas/actions/runs/38003248365/job/114066061733):
normal critical **32 baseline PASS / 13 intended mutants killed**,
без baseline ERROR/SKIP. Четыре default faults дают по1 ожидаемому FAIL
с правильными named guards, не посторонними исключениями.
Baseline roster:
`cd00681fc050a2f1e9fba4c08557d257e4cbce6aafdb5e59236c5c454f17d200`.

Отдельный literal comparison на том же1c6:
historical702/compact82 baseline PASS, **51 парное направленное сравнение PASS**.
Это не подмена own proof других API.

Slice82 `ac6063087b8739db465fb53c25441a972768904e` после actual32/13
удаляет **15 obsolete default functions / 42 cases**. Сохраняются побайтно
live tail, default_need, все imports/docstring/non-test lines; frozen43 inputs,
raw archive и independent control остаются.
Все metadata roster/source/input hashes, actual receipts и аудит1547 source/config
files зафиксированы в crosswalk.
[ADMISSION_LOCAL_BINDING_RETIREMENT](pr211-execution/ADMISSION_LOCAL_BINDING_RETIREMENT_RU.md).
Семейство с current control: **44→2 collected cases**; это ещё не actual outcome
после retirement.

Slice79 мигрирует только три существующих relation guard bodies:
identity/freshness/raw-risk metadata, crop/anonymous lookup credit и no-I/O.
CASES/probe/qualify,16 names/98cases и77 остальных случаев остаются.
Добавлены шесть intended mutants; цель **53 baseline PASS / 19 kills** ещё PENDING.
[RELATION_LIVE_GUARDS](pr211-execution/RELATION_LIVE_GUARDS_RU.md).
Original-query semantic quality не заменяется host lookup credit.

Прежние выполненные сокращения: alias49→1; literal702→82; intent32→2;
admission34→5. Внутренние iterations не выдаются за уменьшение actual work.
Следующий предложенный precheck:21 Context7 alias-only inputs, которые ещё
не исполняет current alias control. Эти21 и все соседние live cases пока collected.

## Recovery и cold read

На1c6 **11 PASS / 0 FAIL / 1 ERROR**. closed_literal_context, включая первое
source-bound чтение и обе requirements forms, теперь PASS без сдвига fingerprint.
Ошибка exact_document_recovery возникает в fixture setup:
оно пытается получить writer agent через read facade до public call.

Slice77 `1b45d278fcf93d74b74eca847b6c03b1abf8d103` переключает только spy lookup
на существующий _read_agent_instance().store — именно этот store использует
настоящий fallback. Все12 cases, request/assertions и запрет list_sections_for_embedding
сохранены. Цель existing recovery **12 PASS / 18 intended kills**, runtime PENDING.
Ошибка baseline1c6 честно блокирует mutation credit.
[COLD_STARTUP_READ_BOUNDARY](PR211_COLD_STARTUP_READ_BOUNDARY_RU.md).

Slice78 поддерживает явно quoted single-character literal: два bounds2→1
в query_terms приведены к уже действующему quoted mention contract1..160.
Existing Cyrillic с cases дают coverage; empty/whitespace/160max и unquoted
правила сохранены. Два других bare-uppercase expectations этим не решаются.
[SINGLE_CHARACTER_QUOTED_LITERALS](PR211_SINGLE_CHARACTER_QUOTED_LITERALS_RU.md).

## Current quality / downstream:1c6

[Current closure38003248410/job114066061198](https://github.com/Vanilla1999/DocAtlas/actions/runs/38003248410/job/114066061198)
получил все три actual reports, integrity=True,12 реальных outcomes.

| Gate | Actual1c6 | Следующая причина |
| --- | --- | --- |
|P1.4|11/14; discovery7/10; required full facts5/5;0errors|Policy retry-count и два alias-only natural questions.|
|P1.5|4/7; full facts2/6;0errors|Generation/capture integrity, document-source binding, mixed project context.|
|P1.6|6/6; full fact1/1;0errors|Current public delivery PASS; отдельный adversarial остаётся24/28.|

P14 улучшился с9/14 и4/5fullfacts: две closed requirements forms теперь реально
доставляют нужные полные факты. Все5 P14 oracle controls PASS; P15/P16 — по6.
P16 report SHA256:
`51561f91d44baab3fb89c355195c526635796d3b0384c320fb09983763629264`.
Это fixture dispatcher/handler/projector/validator и MCP structured/text delivery,
не actual external client session.

Closure: **8 SUCCESS / 4 FAIL**. Реальные failing outcomes:
p14_quality, p15_quality, adversarial, adversarial_mutation.
Итог честно FAIL по current_quality и required_gates_succeeded;
**4/4 closure controls PASS**, saved integrity PASS.
Closure SHA256:
`26694313406a18e6abcc643a2297337310cb8f3d06f6b3668d56fd0dd00ba091`.

### P15: два разных дефекта, два узких исправления

[P15 actual job114066060666](https://github.com/Vanilla1999/DocAtlas/actions/runs/38003248308/job/114066060666).
Finite metadata fix72 сработал: exact8.2.3 lexical filter получает настоящий
library child, полный65-byte факт доставлен. Source integrity правильно FAIL:

1. При втором add SQL generation перенесённого child новый, JSON generation
   старый. Slice80 `23bd25289b39181a7bc3a928351cf5d6912010cd` обновляет JSON
   только на producer copy-path. Existing21-name parent-child module усилен:
   старые rows неизменны; все остальные поля совпадают; actual query/hydration
   возвращают новое поколение.
   [COPIED_CHILD_GENERATION](PR211_COPIED_CHILD_GENERATION_RU.md).
2. P15 observer сохранял только top-level lineage; library original metadata
   уже находится в настоящем snapshot. Это capture loss, не production projection
   loss. Slice81 `04fa18738e6c97d5679b654d2c0fd5c0805c82ad` сохраняет оба raw
   словаря; oracle соединяет только документированные representations, отклоняя
   каждый present conflict, missing field и malformed/contradictory span.
   Шесть existing controls сохраняются и усилены independent DTO/fault pairs.
   [LIBRARY_SNAPSHOT_PROVENANCE](PR211_LIBRARY_SNAPSHOT_PROVENANCE_RU.md).

Frozen7questions/13candidates/6facts/2negatives, bytes, original questions и
строгий committed child binding не меняются. Новый runtime80/81 PENDING.

Оставшиеся P14 alias bodies уже полностью acquired. Нельзя исправить relevance
снижением общего ratio, stopword/synonym dictionary или lexical overlap из двух слов.
Нужен отдельно обоснованный общий relevance contract; чужие modifiers/negation
должны оставаться различимы.
Narrow How many phrase does identifier allow? pair-witness proposal пока
разрабатывается отдельно; без own reviewed code/runtime PASS не заявляется.

P15 document statement не содержит literal path и имеет противоречащие documents.
Нельзя присвоить gold через case name; finite structural source-locator contract
ещё проектируется. Mixed question получает project fact, но original qualification
его отклоняет; library full fact не даёт project-role credit.

### Другие реальные downstream результаты

- Question-surface gate **PASS на100 исходных inputs**, с actual member-backed
  positive, absent-fact negative и source-removal transformation. Это не доказывает
  semantic usefulness всех100 вопросов. Отдельный question_frame_paraphrase_e2e
  про supported source types всё ещё insufficient_evidence.
- Legacy compatibility floor **FAIL: original-query coverage0 < 12**.
  Gold/coverage не ослаблены.
- V2 теперь выдаёт настоящий отчёт: natural usefulness6/15, lookup attribution19/36,
  verified full semantic coverage6/15; exposed usefulness1/5, attribution6/12,
  full coverage1/5. Acceptance FAIL; прежний catalog setup blocker уже не первый.
- Agent Developer target FAIL: cross-module comparison и explicit CatalogReader
  context пусты; module-only expected evidence rate0.25 вместо1.
- Adversarial **24/28**, исходные полезные facts не доставлены в четырёх cases;
  max observed trajectory761 tokens, ceiling отсутствует. Failed baseline
  не даёт adversarial mutation credit.
- Advanced ordinary subset: **528 PASS / 94 FAIL**, отдельно от full core.
  Полного успешного P1-stack/Legacy/V2/Agent Developer/advanced результата нет.

## Reviewed slices следующей публикации

| Slice | Commit | Изменение |
| --- | --- | --- |
|77|`1b45d278`|Recovery fixture spy использует тот же read store.|
|78|`eed0fb75`|Односимвольные quoted literals; существующие controls.|
|79|`08b5d27c`|Три live relation guard bodies и6 mutants;53/19 pending.|
|80|`23bd2528`|Canonical generation скопированного child; existing regression усилен.|
|81|`04fa1873`|P15 raw metadata capture и strict library provenance oracle.|
|82|`ac606308`|Retirement42 после собственного actual32/13, все helpers сохранены.|
|83|`bdd9207b`|Read-facade spies и focused JUnit diagnostics.|

## Следующие действия

1. Опубликовать reviewed77–83 с текущим checkpoint/map; проверить actual merge
   parents/tree и полный CI на новом SHA.
2. Проверить relation53/19, recovery12/18, retirement42, member116, новые spy
   и existing copied-child regression. Baseline failure не считать mutant kill.
3. Прочитать P15 raw top/nested/SQL lineage после80/81; сохранить original gold,
   завершить source-locator и mixed/relevance contracts отдельными slices.
4. Новый Context7 precheck получает собственный normal/mutant proof до удаления21.
5. Разобрать остальные218 failing modules и quality/downstream gaps по источникам.
6. Final acceptance: один конечный SHA/проверенное merge tree, полный core,
   advanced, required CI/P1/downstream, installed/transport/platform и необходимые
   отдельные client evidence. Merge — отдельное действие.

## Рабочая среда

Refs: implementation/pr211-merge-readiness и integration/stage3-v2-identity-pr1.
Только ordinary fast-forward; force/merge/release/внешние комментарии не выполнялись.
Local checkout устарел после0049c6d; exec transport недоступен с18:09UTC.
После outage local AST/import/compile/runtime **NOT RUN**.
Exact-file GitHub API и существующий разрешённый PR CI — действующий маршрут.
Пользовательские индексы, новые модели/providers и реальные clients не запускаются.
Volatile tool state не является checkpoint: exact reviewed commits и этот файл
сохранены в Git.

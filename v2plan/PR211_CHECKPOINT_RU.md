# PR #211: checkpoint продолжения

Обновлено 2026-10-10, 00:19 UTC.
Reviewed code следующего совместного прогона — до
`6225be914656fbbc4b6d49235b1f412320a2395d` (slice88).
Slices85–88 прошли exact Git verification; source changes86–88 — independent review.
Их новый совместный runtime **PENDING**.

Последний фактический полный CI относится к PR HEAD:
`80c8fbbb3e8c379467a9075f93f7165d080f8432`, дерево
`a838749f57ff0165ab925590656f64e0799a2e05`.
Slices77–83 прошли source review, exact Git verification и совместный runtime80c8.

**PR пока не готов к merge.** Полный core на каждой Python:
**7747 = 6057 PASS / 1680 FAIL / 0 ERROR / 10 SKIP**.
По сравнению с1c6 исчезли68 FAIL:42 retired cases и26 настоящих улучшений.
Это разные результаты; одно уменьшение FAIL не доказывает исправление продукта.

## Действующие решения

- Потолки **6144 bytes / 800 tokens / 3 sources** отменены. Измеряем и сокращаем
  объём, сохраняя полные факты, source identity, scope/version/hash и consent guards.
- Операционные input/read/work/call/time ограничения сохраняются.
- Retrieval включён в позднее утверждённый план; прежний blanket deferral снят.
- Retirement требует собственного зелёного baseline, intended mutation kills и
  проверки сохраняемых helpers/imports/selectors. Остальные FAIL автоматически
  устаревшими не объявляются.
- Реальные Claude Code/Codex/OpenCode sessions **NOT RUN**. Installed SDK/stdio
  harness не подтверждает такие sessions.
- Quality floors и исходные gold facts сохраняются. Original coverage12 —
  обязательство качества, а не отменённый потолок output cost.

План: [PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md).
Решения: [CURRENT_WAVE_DECISIONS_RU.md](CURRENT_WAVE_DECISIONS_RU.md).
История до067: [CHECKPOINT_067dd560_RU.md](pr211-execution/CHECKPOINT_067dd560_RU.md).
Последующие checkpoints, collection error38da и exact reviewed slices доступны
в Git history. Local checkout устарел; читать точный текущий PR HEAD.

## Полный фактический CI:80c8

Фактический GitHub merge checkout:
`f04b42774b00dadbca48ca579ca9ea234442b750`.
Проверены оба parent: main
`d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c` и PR80c8.
Дерево merge checkout совпадает с PR: `a838749f57ff0165ab925590656f64e0799a2e05`.

[Main run38006157209](https://github.com/Vanilla1999/DocAtlas/actions/runs/38006157209).
[JUnit reader114077935805](https://github.com/Vanilla1999/DocAtlas/actions/runs/38006157209/job/114077935805).
На всех Python3.11/3.12/3.13:6057P/1680F/0E/10S,
integrity_issues=[] и omitted_rows=0. Матричные повторы не суммируются.

| Python | SHA256 JUnit80c8 |
| --- | --- |
|3.11|`5f63b79277b026b10016ec568b802e3df730cc10de034fd14886bdb1dd264047`|
|3.12|`751890a134178f8bd44423c7520859ef1933ff89c2ec044f9323fbff0bcfdb2a`|
|3.13|`fddb34296375b22e7d16c65194b2b0fbb750493eed0bac5a9d92aba651da34d8`|

[CORE_FAILURE_MAP_80c8fbbb.jsonl](pr211-execution/CORE_FAILURE_MAP_80c8fbbb.jsonl):
**215 failing modules / 1680 FAIL**, counts и первый node/message, явная triage.
Первый failure не классифицирует весь модуль.
[Reviewed runtime receipt80c8](pr211-execution/RUNTIME_EVIDENCE_80c8fbbb.json)
содержит critical/recovery/mutation evidence, tracked/focused JUnit, P15 и closure.
Предыдущие карты1c6/a348/0855 сохранены.

### Изменения относительно1c6

1c6:7789=6031P/1748F/0E/10S;80c8:7747=6057P/1680F/0E/10S.

| Модуль | 1c6 PASS/FAIL | 80c8 PASS/FAIL | Объяснение |
| --- | ---: | ---: | --- |
|admission_local_binding|1/42|1/0|42 obsolete cases retired после собственного proof.|
|admission_relation_safety|2/24|8/18|6 настоящих PASS; прочие обязанности остаются.|
|admission_relation_witnesses|8/64|23/49|15 настоящих PASS по source-policy guards.|
|admission_role_boundaries|28/4|30/2|Два явно quoted Cyrillic literals теперь PASS.|
|context_projection_boundaries|13/7|14/6|Read-only fixture исправлен; шесть прежних failures остаются.|
|pr211_catalog_equivalence|4/1|5/0|Spy принимает актуальный read_only_startup.|
|mcp_delivery_dispatch_boundary|2/1|3/0|То же; intended denial guard действительно достигнут.|

Новых failing modules и других module-count изменений не найдено.
Это сравнение counts, не доказательство равенства каждого из7747 nodes.
Все три новых failures предыдущего полного прогона теперь устранены.
Focused reader прямо показывает PASS для
test_gap_quote_is_not_a_mutation_grant и шесть оставшихся projection failures.

### Отдельные проверенные семейства и jobs

| Семейство | Actual80c8 PASS/FAIL |
| --- | ---: |
|ActionPacket main / part02|31/0 и8/0|
|Context completion followup|1/1|
|Docs read-next / SourceMap|31/0 и29/0|
|Member transactions|116/0|
|Parent-child index|21/0|
|Alias / project-intent current controls|1/0 и1/0|
|Catalog equivalence / MCP dispatch|5/0 и3/0|

Existing copied-child regression явно PASS, включая actual query/hydration.
Member116 подтверждает read-only boundary этого семейства, не все library paths.
Completion mkdocs-05 priority fact остаётся реальным FAIL.

Docs-contract, docs-impact, static-contract, retrieval-evidence, installer,
installed MCP harness и все три platform smoke jobs SUCCESS.
Core/advanced/required-ci FAIL; p1-harden-branch SKIP.
[P1 stack38006157238](https://github.com/Vanilla1999/DocAtlas/actions/runs/38006157238):
build, sdist installer, wheel3lanes и platform3lanes SUCCESS;
core3lanes, advanced-security и p1-stack-exact FAIL.
Installed harness не считается реальной client session.

## Сокращение тестов и собственные проверки

[Advanced114075319327](https://github.com/Vanilla1999/DocAtlas/actions/runs/38006157209/job/114075319327):
normal critical **53 baseline PASS / 19 intended mutants killed**.
Каждый mutant дал ожидаемые failure count, intended guard и returncode1;
anchor_count1, ERROR/SKIP0. Baseline roster:
`b4a630000b9791fdb09c4b245bc2b213cba2cb8914b1898bc58116354cc5d585`.

Slice79 сохранил16 names/98 cases и изменил только три live guard bodies.
21 case теперь PASS; identity/freshness/raw-risk, crop/anonymous credit и no-I/O
имеют шесть собственных intended kills. Остальные77 cases не удалялись.
[RELATION_LIVE_GUARDS](pr211-execution/RELATION_LIVE_GUARDS_RU.md).

Slice82 удалил15 obsolete default functions/42 cases после actual1c6 proof32/13.
Frozen43 inputs, raw archive, independent control, live tail/default_need,
все imports и non-test lines сохранены.
Семейство с current control:44→2 collected; новый80c8 collection здоров,
его четыре intended faults по-прежнему обнаружены.
[ADMISSION_LOCAL_BINDING_RETIREMENT](pr211-execution/ADMISSION_LOCAL_BINDING_RETIREMENT_RU.md).

Отдельный literal comparison на том же80c8:
historical702/compact82 baseline PASS и51 парное направленное сравнение PASS.
Это не заменяет собственные доказательства других API.
Прежние сокращения: alias49→1, literal702→82, intent32→2, admission34→5.
Количество внутренних iterations отдельно от количества collected cases.

Slice87 добавляет в existing alias-control21 точный исходный Context7 input:
теперь3 прежних+21 новых входов. Независимые plan/lookup positives сохранены,
добавлен scoped Russian topic-router mutant, недостижимый прежними тремя входами.
Raw archive/source spans/records/hashes и все остальные AST nodes сохраняются.
Цель **53 baseline PASS /20 intended kills** — PENDING.
До собственного нового proof эти21 и все соседние live cases остаются collected.
[CONTEXT7_ALIAS_INPUT_PRECHECK](pr211-execution/CONTEXT7_ALIAS_INPUT_PRECHECK_RU.md).

## Recovery:12/18 PASS

Все12 существующих cases PASS; все18 intended mutants обнаружены.
Gate SHA256:
`52bf526d75951a9b32eab6a7179f74d22ac8ec824877e7c707af5444a332cedf`.
Closed literal case:9 positive queries,20 negatives,29 state fingerprints.
Exact-document recovery теперь использует actual read store для spy;
запрет list_sections_for_embedding и immutable fingerprints сохранены.
[COLD_STARTUP_READ_BOUNDARY](PR211_COLD_STARTUP_READ_BOUNDARY_RU.md).

Slice78 расширил только явно quoted single-character literals; оба Cyrillic
case PASS. Два остальных bare-uppercase/per-occurrence expectations требуют
собственного current-contract разбора.
[SINGLE_CHARACTER_QUOTED_LITERALS](PR211_SINGLE_CHARACTER_QUOTED_LITERALS_RU.md).

## Current quality и downstream:80c8

| Gate | Actual80c8 | Оставшаяся причина |
| --- | --- | --- |
|P1.4|11/14; discovery7/10; full facts5/5;0errors;5/5controls|Policy retry-count и два alias-only natural questions.|
|P1.5|5/7; verified full facts3/6;0errors;6/6controls|Document-source binding и mixed project context.|
|P1.6|6/6; full fact1/1;0errors;6/6controls|Current public delivery PASS; separate adversarial24/28.|

[P14 job114075318958](https://github.com/Vanilla1999/DocAtlas/actions/runs/38006157206/job/114075318958).
[P15 job114075319048](https://github.com/Vanilla1999/DocAtlas/actions/runs/38006157207/job/114075319048).
[Closure114075318873](https://github.com/Vanilla1999/DocAtlas/actions/runs/38006157215/job/114075318873).

P15 dependency exact-version fact теперь PASS после production generation fix80
и observer/oracle fix81. В двух remaining failures source_errors=[].
Full original metadata не терялась в production: observer теперь сохраняет
top-level и nested representations отдельно, oracle отвергает каждый conflict.
Frozen7questions/13candidates/6facts/2negatives и committed child binding сохранены.
[COPIED_CHILD_GENERATION](PR211_COPIED_CHILD_GENERATION_RU.md),
[LIBRARY_SNAPSHOT_PROVENANCE](PR211_LIBRARY_SNAPSHOT_PROVENANCE_RU.md).

P16 report SHA256:
`b255d2b15b58e78fe5551395e2d81d39699a7b26508fcdb41b64c3546f5511bb`.
Closure:8 SUCCESS/4 FAIL; failing outcomes:
p14_quality, p15_quality, adversarial, adversarial_mutation.
4/4 closure controls и integrity PASS; итог current_quality/required gates FAIL.
Closure SHA256:
`86f461ffa1f3b15c7e0b2a2bbbbf81eb617962ea20939f51fd8616f577ee23ae`.

P14 alias bodies уже acquired; нельзя повышать coverage снижением ratio,
словарём из gold или host lookup credit. Общий relevance contract пока открыт.
Slice86 реализует отдельно reviewed закрытую count source-context форму:
exact identifier и whole phrase в одном raw body unit, без quantity/permission
inference и без original-query/answer/edit credit. +2 intended mutants.
Это ещё не runtime result.
[LITERAL_COUNT_CONTEXT](PR211_LITERAL_COUNT_CONTEXT_RU.md).

P15 document statement не содержит literal path и имеет противоречащие документы:
нужен explicit finite structural filename-binding contract.
Same-call diagnostics mixed request показывают acquisition обеих raw facts,
но public sources=[]/source_bindings=[]: пустой source_errors=[] не доказывает
успешный mixed source binding. Slice88 реализует полностью закрытую Explain
literal-list форму, exact source-bound context и3 intended mutants.
Старый negative What does A and B do? сохраняется. Runtime PENDING.
[LITERAL_EXPLAIN_CONTEXT](PR211_LITERAL_EXPLAIN_CONTEXT_RU.md).

После count+Explain остаются12 recovery cases; цель **12/12 baseline +23 kills**.
Existing closed case ожидает16 positive+54 negative=70 state fingerprints;
source/current/hash/consent replay и запрет original-query/answer/edit grants сохранены.
Это ожидаемые проверки, не полученный результат.

### Другие обязательства

На80c8 advanced ordinary subset528P/94F. Legacy original-query coverage0<12.
V2 verified full semantic coverage natural6/15 и exposed1/5.
Agent Developer module-only expected evidence rate0.25 вместо1;
cross-module comparison и CatalogReader остаются предметом разбора.
Adversarial24/28, observed maximum761 trajectory tokens, output ceiling отсутствует.
Failed adversarial baseline не даёт mutation credit.

Предыдущий1c6 question-surface PASS на100 original inputs с member-backed
positive/absent-fact negative/source-removal transform не доказывает usefulness
всех100. Отдельный question-frame source-types E2E остаётся незакрытым обязательством.
Полного успешного Legacy/V2/Agent Developer/advanced/P1-stack отчёта нет.

## Reviewed slices следующей публикации

| Slice | Commit | Изменение |
| --- | --- | --- |
|85|`7856a818`|Полный actual80c8 receipt и215-module failure map.|
|86|`926cb5af`|Закрытый count frame, raw pair witnesses и2 mutants.|
|87|`357bbbfb`|21 Context7 input в existing control и scoped mutant; retirement0.|
|88|`6225be91`|Закрытый Explain list, exact partial source context и3 mutants.|

Новых ordinary test functions и удалённых cases в86–88 нет.
Actual53/19 и12/18 на80c8 остаются базой сравнения, а не доказательством новых53/20 и12/23.

## Следующие действия

1. Опубликовать reviewed85–88 и этот checkpoint обычным fast-forward;
   проверить фактические merge parents/tree и совместный CI.
2. Проверить critical53/20 и recovery12/23, полный core, P14 count и P15 mixed
   на следующем фактическом SHA.
   Не удалять Context7 cases до собственного нового proof.
3. Закончить document source-locator contract, затем остальные quality obligations,
   сохраняя исходные questions/gold и полные source facts.
4. Разобрать215 failing modules по действующим контрактам и live guards.
5. Final acceptance на одном конечном SHA/проверенном merge tree:
   full core, advanced, required CI/P1/downstream, installed/transport/platform
   и отдельные необходимые client evidence. Merge — отдельное действие.

## Рабочая среда

Refs: implementation/pr211-merge-readiness и integration/stage3-v2-identity-pr1.
Только ordinary fast-forward; force/merge/release/внешние комментарии не выполнялись.
Local checkout устарел после0049c6d; exec transport недоступен с18:09UTC9октября.
После outage local AST/import/compile/runtime NOT RUN.
Exact-file GitHub API и существующий разрешённый PR CI — действующий маршрут.
Пользовательские индексы, новые модели/providers и реальные clients не запускаются.
Exact commits и этот checkpoint сохраняют результаты независимо от volatile state.

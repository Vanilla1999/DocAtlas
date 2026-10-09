# PR #211: checkpoint продолжения

Обновлено 2026-10-09, 23:09 UTC. Reviewed code этой публикации — до
`931be4a3f0296695d78cae9cb87da419a7124456`.
Следующий commit сохраняет этот checkpoint. Slices70–75 прошли source review,
но их совместный runtime ещё **PENDING**.

**PR пока не готов к merge.** Последний запуск38da остановил core на ошибке
collection; это не успешный прогон с нулём failures. Последний полный core —
a348: 6030PASS / 1778FAIL / 0ERROR / 10SKIP на каждой Python lane.

## Действующие решения

- Потолки **6144 bytes / 800 tokens / 3 sources** отменены. Измеряем и сокращаем
  объём, сохраняя полные факты, source identity, scope/version/hash и consent guards.
- Операционные input/read/work/call/time ограничения сохраняются.
- Retrieval включён в позднее утверждённый план; прежний blanket deferral снят.
- Сокращение tests требует собственного зелёного baseline и доказанного обнаружения
  дефектов. Другие FAIL не объявляются устаревшими автоматически.
- Реальные Claude Code/Codex/OpenCode sessions **NOT RUN**. Installed SDK/stdio
  harness не подтверждает такие sessions.

План: [PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md).
Решения: [CURRENT_WAVE_DECISIONS_RU.md](CURRENT_WAVE_DECISIONS_RU.md).
История до067 сохранена побайтно:
[CHECKPOINT_067dd560_RU.md](pr211-execution/CHECKPOINT_067dd560_RU.md),
git blob `7659d17450bcb4dff2260cd2481be61d1153f5ff`.
Позднейшие checkpoint доступны в Git history; local checkout устарел.

## Последний фактический запуск:38da — collection ERROR

PR HEAD: `38da10d347ae2227eee6d1624db58dbf30938674`.
Фактический GitHub merge checkout:
`984bb65205140221552728fc03dc8b5121f3e218`.
Его родители — main `d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c` и этот PR HEAD.
Дерево обоих checkout совпадает:
`a915bd89c7dcdcc327d0687057e847c6e5686943`.
Parent/tree identity проверена через Git commit metadata.

[Main run38000724569](https://github.com/Vanilla1999/DocAtlas/actions/runs/38000724569).
[JUnit reader114058136097](https://github.com/Vanilla1999/DocAtlas/actions/runs/38000724569/job/114058136097):
на каждой Python3.11/3.12/3.13 **0PASS / 0FAIL / 1ERROR / 0SKIP**,
integrity issues пусты, console omissions0. Сбор suite прерван:
`tests/docs/test_admission_mapping_assignments.py` импортирует `demand`
из `test_admission_meaning.py`, а slice65 удалил этот shared helper.

Это регрессия retirement65, не устаревшее тестовое ожидание.
Slice71 восстанавливает helper побайтно и добавляет сохранение его AST
в существующий current control. Четыре оставшихся admission tests и helper
`demands` не меняются. Crosswalk обновляет source hash и честно сохраняет ошибку.
Исправление collection ещё требует CI.

| Python | SHA256 JUnit38da |
|---|---|
|3.11|`3018614b7554d9e185dcfcde25b15181c29314465214b9486ffe5e0ef14fd69a`|
|3.12|`1bffe410b73277cb4263e72e8d455a1454b378fbbc138de085479392068eb691`|
|3.13|`fe06a6c47d388b9a7ea7b34a4ad10eed88bbf561b94b9488f1dd3cd0853458cd`|

На38da docs-contract, docs-impact, static-contract, retrieval-evidence,
installer, installed MCP harness и все3platform-smoke jobs SUCCESS.
Advanced и required-ci FAIL. Эти отдельные PASS не заменяют прерванный core.
Четыре migrated fixtures slice66 пока не имеют нового подтверждённого core outcome.

## Последний полный core: a348cafb

PR HEAD: `a348cafb4807a5b4af852e0029cf6b98ff7a3f91`.
Actual merge checkout: `0e84988d21bb06a86c14714e077098e5cf0cb5d9`.
Parents: тот же main и этот PR HEAD.
Проверенное общее дерево: `8e10b447f3f6d7e8ee09ac5e1de05f73eacd6ad4`.

[Main run37998331818](https://github.com/Vanilla1999/DocAtlas/actions/runs/37998331818).
Каждая Python lane3.11/3.12/3.13:
**7818 = 6030PASS / 1778FAIL / 0ERROR / 10SKIP**.
Матричные повторы не суммируются.
[JUnit reader114053345530](https://github.com/Vanilla1999/DocAtlas/actions/runs/37998331818/job/114053345530):
integrity issues пусты, console omissions0.

| Python | SHA256 JUnit a348 |
|---|---|
|3.11|`f435346b5497c771062d8b772e89faaf22de1145985af71142c8f3d05e3a816f`|
|3.12|`3d46049bf5c841a04ffde8174a7840af32014d439eba8ad8005fde06cfd924e0`|
|3.13|`d7c2b6de543d5d29ef33b974d526f01257c95e1ce66fa27feb0f1e08395c84bd`|

Карта всех217 failing modules с1778FAIL:
[CORE_FAILURE_MAP_a348cafb.jsonl](pr211-execution/CORE_FAILURE_MAP_a348cafb.jsonl).
Содержит counts/первый node/message, исследованные причины и явный
`not_investigated` для остальных. Первый failure не классифицирует весь модуль.
Карта0855 и более ранние карты сохранены; collection ERROR38da их не обнуляет.

Сравнение с0855: 7818 = 6025PASS / 1783FAIL / 0ERROR / 10SKIP.
Ровно5FAIL сталиPASS без изменения collected: admission current contract1,
MCP output contract1, dictionary read tails2, dictionary unit helpers1.
Других изменений failing-module counts и новых failing modules нет.

| Семейство | PASS / FAIL наa348 |
|---|---|
|ActionPacket main|31 / 0|
|ActionPacket part02|8 / 0|
|Context completion followup|1 / 1|
|Docs read-next|31 / 0|
|SourceMap|29 / 0|
|Member transactions|116 / 0|
|Alias current contract|1 / 0|
|Project intent current contract|1 / 0|

Generated SourceMap node, семь invalid-storage и три real-service nodes явно
присутствуют в JUNIT_TRACKED какPASS на каждой lane. Три real-service варианта
проверяют committed lineage и Unicode byte spans.
Второй completion test с полным mkdocs-05 priority fact остаётся исходным и падает.

## Сила заменяющих проверок

[Advanced38da/job114057857873](https://github.com/Vanilla1999/DocAtlas/actions/runs/38000724569/job/114057857873):
normal critical **31baselinePASS / 9intendedkills**.
Каждый mutant обнаружен ожидаемым guard; errors/skips и чужие failures
не засчитываются. Admission mutant:
`admission_meaning_no_inferred_equivalence`, 1FAIL/0ERROR/0SKIP,
marker `critical_admission_meaning_no_inferred_equivalence`.
Baseline roster:
`2452628f600f2730e2491a23666561137b3a3d8c2d6bf4dacbee6db9cb58c424`.

Retirement65 удалил30 obsolete admission cases после собственного31/9proof наa348.
Остаются4 исходных live tests +1 current control, frozen archive и crosswalk.
Ошибка внешнего helper исправляется71; сам31/9PASS её не поймал.

Отдельный literal comparison наa348: historical702/compact82 baselinePASS,
51directedmutation comparisonsPASS. Это не доказательство default-binding family.

Slice74 добавляет **precheck default/local-binding**: все43 старых cases остаются
collected. Один независимый control сохраняет frozen43-input roster, unknown ABI
`(None, ())`, original/host_lookup positive, trace fidelity и отсутствие inherited
need credit. Четыре production mutations направлены на True/False вместо unknown,
ложное qualification и стирание здорового trace.
Цель следующего CI — **32baselinePASS / 13intendedkills**, сейчас PENDING.
Unsupported-tail test и `default_need` helper сохранены.
Любой следующий retirement требует этих результатов и проверки внешних consumers/selectors.

Общие уже выполненные сокращения: alias49→1; literal702→82; intent32→2; admission34→5.
Внутренние iterations не объявляются уменьшением actual work.

## Recovery и первый cold read

На38da recovery **11PASS / 1FAIL / 0ERROR**.
`closed_literal_context` упал на `recovery_closed_context_is_read_only`.
Первое чтение: `What does OrdersDraftStore do?`, docs/literal-context.md.
Меняется только store_sha256:
`812eb49e188d71d1244376a9d6b13f78b56b9e4e8821fca8eacfea725c5ba986` →
`ea7277895dea3821904c780627b69951cda4bb513be213aa49b6cb631cd1fdd6`.
Generation, document и catalog fingerprints совпадают.
Before-hash/equality guard не двигались; warming не применяется.

Slice73 разделяет cold member read facade и явную write preparation.
Registry/job reads используют owned read-only connection, не создают schema,
не interrupt/prune/resume jobs и отклоняют неподдержанную schema.
Write entrypoints registry/job stores и открытие member writer через read facade
отклоняются до SQL или изменения tracker state.
Три существующих real-service tests начинают fingerprint до первого public read,
сохраняют116-case roster, проверяют отсутствие startup writes, real MCP validation,
SQL schema forgeries и позднюю explicit prepare/current-generation совместимость.
Это граница member read; полный read-only startup всех library paths не заявляется.

Slice70 добавляет две полностью потреблённые requirements forms:
`What does X require?` и `Which conditions are required by X?`.
Bare identifiers, лишние modifiers, alias expansion, role/answer/edit credit
не получают нового разрешения. Independent body и отрицательные cases добавлены
в существующий recovery case; два новых mutants проверяют именно эту границу.
Новая цель recovery — **12baselinePASS / 18intendedkills**, runtime PENDING.
Failed baseline38da не даёт mutation credit.

## Текущие P1 quality и closure на38da

[Current closure run38000724789/job114057858648](https://github.com/Vanilla1999/DocAtlas/actions/runs/38000724789/job/114057858648)
сформировал все3 current reports с integrityPASS, сохранил12 реальных outcomes.

| Gate | Actual38da | Что осталось |
|---|---|---|
|P1.4|9/14; discovery5/10; full facts4/5;0errors|Requirements contract/conditions, retry policy, два alias cases.|
|P1.5|4/7; full facts2/6;0errors|Dependency fact, document-statement, mixed two-claim case.|
|P1.6|6/6; полный полезный факт1/1;0errors|Current public delivery прошёл; отдельный adversarial остаётся24/28.|

P14 state guards и5oracle controlsPASS; P15 иP16 — по6oracle controlsPASS.
P16 использует actual dispatcher/handler/projector/validator и structured/text
MCP serialization. Это fixture public delivery, не indexed retrieval, stdio или client session.

Closure получил8SUCCESS/4FAIL: p14_quality, p15_quality, adversarial,
adversarial_mutation действительноFAIL.
Текущий closure честноFAIL только по `current_quality` и `required_gates_succeeded`.
**4/4 closure controlsPASS**, saved integrity, syntax и historical guardsPASS.
Closure SHA256:
`9b99a21138276037ba14934abfd7ecc18db19b790325873da484ae0e7d22f6a6`.
Historical assertions и7installed source identities остаются обязательными,
но не объявляются current transport/quality proof.

### Локализованная потеря P1.5

[P15 run38000724676/job114057857626](https://github.com/Vanilla1999/DocAtlas/actions/runs/38000724676/job/114057857626):
Tenacity resolve возвращает available/local/exact8.2.3,
но get_docs получает0 lexical candidates при exact library/version filters.
Source review показывает, что finite prefetch записывал legacy version,
не передавая resolved_version/docs_snapshot_exact для promoted filters.
Это source-derived причина; фактические SQL values отдельно не прочитаны.

Slice72 использует existing metadata_for_record, сохраняя canonical URL identity
и version-binding policy. Independent oracle проверяет exact8.2.3 и exactness
каждого stored child; положительные bool/int варианты и20 negative mutations
встроены в прежние6controls. Preparation metadata печатаются без body.
Frozen7questions/13candidates/6facts/2negatives и actual filter guards не меняются.

Document-statement question не содержит literal path. Нельзя присвоить ему
gold source через имя case или разрешить одновременно противоречащие documents.
Нужен отдельно обоснованный finite source-locator contract.
Mixed question пока имеет project not_found/no_reliable_context и library no_results.
Slice75 наблюдает существующий get_project_context return и same-call pipeline,
без дополнительных calls или изменения result. Runtime observer и исправление72 PENDING.

P1-stack wiring68 уже использует actual reports/outcomes и прежние production commands.
Ранний failure сохраняет SKIP/FAIL зависимых gates. Отдельный полный успешный
P1-stack/Legacy/V2/Agent Developer результат пока не получен.

## Reviewed slices новой публикации

| Slice | Commit | Изменение |
|---|---|---|
|70|`8060c8ea`|Closed requirements literal context и2 адресных recovery mutants.|
|71|`1c455eea`|Восстановлен shared demand helper; AST preservation и честный collection-error receipt.|
|72|`42480d6c`|Exact library child metadata и independent per-child oracle.|
|73|`50f7e650`|Cold member read boundary; registry/jobs без startup writes и усиленные существующие real-service controls.|
|74|`d4003130`|Default/local-binding precheck; старые43cases остаются, новая цель32/13.|
|75|`931be4a3`|P15 same-call project trace, diagnostic serialization без dataclass.|

Все code slices прошли root + independent source review и exact
parent/tree/blob verification. **Совместный runtime70–75 PENDING.**
Slices64–69 и их отчёты сохранены в Git history; полная картаa348 остаётся актуальной
картой последнего завершившего collection core.

## Следующие действия

1. Опубликовать70–76; восстановить full collection и прочитать новый полный JUnit.
2. Проверить cold first read, member116cases, recovery12/18 и default32/13.
3. Проверить P15 child/version metadata, фактические library/project returns,
   P14 requirements и current closure; расследовать следующий реальный first loss.
4. Мигрировать живые source-policy/crop/public/no-I/O tests отдельно от retired
   NL classifier expectations. Общие helpers и pytest selectors сохранять.
5. Разобрать оставшиеся P14/P15/Legacy/V2/Agent Developer/adversarial/language/core
   failures без ослабления gold, safety или quality guards.
6. Итоговый acceptance на конечномSHA: полный core, advanced, required CI/P1,
   необходимые downstream, installed/transport/platform и отдельные client evidence.
   Merge-ready только после обязательных gates; сам merge — отдельное действие.

## Рабочая среда

Refs: implementation/pr211-merge-readiness и integration/stage3-v2-identity-pr1.
Только ordinary fast-forward; force/merge/release/внешние комментарии не выполнялись.
Local checkout устарел после0049c6d; exec transport недоступен с18:09UTC.
После outage local AST/import/compile/runtime **NOT RUN**.
Изменения готовятся exact-file GitHub API и проверяются разрешённым PR CI.
Пользовательские индексы, новые модели/providers/реальные clients не запускаются.

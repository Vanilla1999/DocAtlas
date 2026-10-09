# PR #211: checkpoint продолжения

Обновлено 2026-10-09, 22:43 UTC. Reviewed code этой публикации — до
`befa475d397fd2bb19edbce363b04a363fc09252`.
Следующий commit добавляет этот checkpoint и карту последнего полного core.

**PR пока не готов к merge.** Slices64–68 прошли source review и требуют общего CI.
Фактические результаты ниже относятся к a348cafb; ожидаемые улучшения не засчитываются.

## Действующие решения

- Потолки **6144 bytes / 800 tokens / 3 sources** отменены. Измеряем и сокращаем
  объём, сохраняя полные факты, source identity, scope/version/hash и consent guards.
- Операционные input/read/work/call/time ограничения сохраняются.
- Retrieval включён в позднее утверждённый план; прежний blanket deferral снят.
- Сокращение tests требует собственного зелёного baseline и доказанного обнаружения
  дефектов. Остальные FAIL не объявляются устаревшими автоматически.
- Реальные Claude Code/Codex/OpenCode sessions **NOT RUN**. Installed SDK/stdio
  harness не подтверждает такие sessions.

План: [PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md).
Решения: [CURRENT_WAVE_DECISIONS_RU.md](CURRENT_WAVE_DECISIONS_RU.md).
История до067 сохранена побайтно:
[CHECKPOINT_067dd560_RU.md](pr211-execution/CHECKPOINT_067dd560_RU.md),
git blob `7659d17450bcb4dff2260cd2481be61d1153f5ff`.
Позднейшие версии checkpoint доступны в Git history; local checkout устарел.

## Последний полностью прочитанный core: a348cafb

PR HEAD: `a348cafb4807a5b4af852e0029cf6b98ff7a3f91`.
Фактический GitHub merge checkout:
`0e84988d21bb06a86c14714e077098e5cf0cb5d9`.
Его родители — main `d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c` и этот PR HEAD.
Дерево обоих checkout побайтно совпадает:
`8e10b447f3f6d7e8ee09ac5e1de05f73eacd6ad4`.
Это проверено через Git commit metadata, а не предполагается из названия ветки.

[Main run37998331818](https://github.com/Vanilla1999/DocAtlas/actions/runs/37998331818).
Каждая Python lane **3.11 / 3.12 / 3.13**:
**7818 = 6030 PASS / 1778 FAIL / 0 ERROR / 10 SKIP**.
Матричные повторы не суммируются.
[JUnit reader114053345530](https://github.com/Vanilla1999/DocAtlas/actions/runs/37998331818/job/114053345530):
integrity issues пусты, console omissions0.

| Python | SHA256 JUnit |
|---|---|
|3.11|`f435346b5497c771062d8b772e89faaf22de1145985af71142c8f3d05e3a816f`|
|3.12|`3d46049bf5c841a04ffde8174a7840af32014d439eba8ad8005fde06cfd924e0`|
|3.13|`d7c2b6de543d5d29ef33b974d526f01257c95e1ce66fa27feb0f1e08395c84bd`|

Карта всех217 failing modules с1778FAIL:
[CORE_FAILURE_MAP_a348cafb.jsonl](pr211-execution/CORE_FAILURE_MAP_a348cafb.jsonl).
Она содержит exact counts/первый node/message, исследованные причины и явный
`not_investigated` для остальных. Первый failure не классифицирует весь модуль.
Карта0855 и более ранние карты сохранены.

Сравнение с0855: **7818 = 6025 PASS / 1783 FAIL / 0 ERROR / 10 SKIP**.
Ровно5FAIL сталиPASS без изменения collected: admission current contract1,
MCP output contract1, dictionary read tails2, dictionary unit helpers1.
Других изменений failing-module counts и новых failing modules нет.
Четыре соответствующих модуля больше не имеют failures.

### Сохранённые outcomes

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
присутствуют в JUNIT_TRACKED со статусомPASS на каждой lane. Три real-service
варианта теперь дополнительно проверяют actual committed lineage и Unicode byte spans.
Второй completion test с полным mkdocs-05 priority fact остаётся исходным и падает.

Наa348 docs-contract, docs-impact, static-contract, retrieval-evidence,
installer, installed MCP harness и все3platform-smoke jobs SUCCESS.
Advanced и required-ci FAIL. Успешный installed harness не заменяет real client sessions.

## Сила заменяющих проверок и сокращение admission

[Advanced job114049950632](https://github.com/Vanilla1999/DocAtlas/actions/runs/37998331818/job/114049950632):
**normal critical31baselinePASS / 9intendedkills** подтверждены наa348.
Baseline31tests,0FAIL/0ERROR/0SKIP. Каждый из9mutants обнаружен своим
ожидаемым guard; errors/skips и чужие failures не засчитываются.
Admission mutant: `admission_meaning_no_inferred_equivalence`,
1FAIL/0ERROR/0SKIP, marker `critical_admission_meaning_no_inferred_equivalence`.
Normal baseline roster:
`2452628f600f2730e2491a23666561137b3a3d8c2d6bf4dacbee6db9cb58c424`.

Slice65 после этого доказательства удаляет ровно30obsolete admission cases.
Сохраняются четыре исходных live tests и demands helper побайтно:
unknown residue, unsupported second clause, A-and-B versus A-or-B,
mismatched ReferencePlan. Frozen archive, crosswalk и runtime proof сохранены;
диагностический shard меняет только hash нового collected roster.
До precheck было34cases, после precheck35; после retirement остаются
4исходных +1новый contract =5. Разница с проверенным precheck SHA — минус30.
Final runtime после удаления ещё pending.

Отдельный literal comparison наa348: historical702/compact82 baselinePASS,
51directedmutation comparisonsPASS. Это не доказательство default-binding family.
Следующий default-binding precheck проектируется отдельно: старые43cases пока
collected; нужны собственные baseline и intended kills до любого retirement.

## Recovery: доказанная проблема первого чтения

Наa348 recovery **11 PASS / 1 FAIL / 0 ERROR**.
`closed_literal_context` упал на `recovery_closed_context_is_read_only`.
Первое чтение: `What does OrdersDraftStore do?`, docs/literal-context.md.
Меняется только `store_sha256`:
`e3a6dd2903477da5fe182e8ec6f43969c8d411499b68cb3dfbec28fef3eee047` →
`d2f4ede7bcb63f399f1a2bc1e0b6fbea184be8663ac7793b0d8b3097d17a0059`.
Generation, document и catalog fingerprints совпадают.
Это actual failure-only diagnostic62; before-hash и equality guard не двигались.

Статически обнаружены startup writes LibraryRegistry/DocsJobTracker при первом
cold.materialize. Production deferral/read-only boundary готовится отдельно.
Warming и маскировка writes не разрешают failure.
**12baseline/16intendedkills пока не подтверждены**: failed baseline не даёт credit.

## Текущие P1 quality results

### P1.4

[Run37998331831 / job114049949393](https://github.com/Vanilla1999/DocAtlas/actions/runs/37998331831/job/114049949393):
**9/14 total**, discovery **5/10**, full facts **4/5**, runtime errors0.
Все14 READ_STATE совпали, пятьoracle controls/integrityPASS.
Оба behavior cases OrdersDraftStore/PaymentOutbox PASS.
Остаются requirements contract/conditions, retry policy и два alias cases.
Полезные bodies найдены, но qualification отвергает эти вопросы.
Нельзя закрывать это снижением quality facts или произвольным снижением порога.

### P1.5

[Run37998331846 / job114049949697](https://github.com/Vanilla1999/DocAtlas/actions/runs/37998331846/job/114049949697):
**4/7 total**, **2/6 verified full facts**, runtime errors0;
шестьoracle controls/integrityPASS.
Combined lineage58/class59 исправили canonical policy и implementation facts,
сохранив все child/owner/scope/authority/hash/span/generation guards.

Остаются dependency_fact_prefers_dependency_docs,
document_statement_binds_exact_path и two_claims_require_two_allowed_roles:
четыре обязательных source facts отсутствуют в трёх cases.
Source errors, preparation/authority/state differences пусты.
Slice64 наблюдает фактический unified return и существующие resolve_library/get_docs
вызовы; не выполняет дополнительных reads и не меняет scorer/state boundary.
Новый diagnostic должен локализовать library/mixed путь в следующем CI.

### P1.6 и общий closure

[Run37998331760 / job114049949409](https://github.com/Vanilla1999/DocAtlas/actions/runs/37998331760/job/114049949409):
current public delivery **6/6PASS**, полезный полный факт **1/1**,
runtime errors0; **6/6oracle controls**, integrity/syntaxPASS.
Все исходные questions/candidates/requirements и independent frozen oracle сохранены.
Dispatcher, handler, projector, validator и structured/text fallback MCP serialization реальные.
Это fixture public delivery, не indexed retrieval, stdio или LLM/client session.

P16 workflow в целом FAIL: прежний adversarial **24/28** и отказ mutation gate
из-за failed baseline сохранены. Новая P16 часть не отменяет эти failures.

Slice67 переводит closure на current P14/P15/P16 reports, actual checkout SHA,
current source manifests и12настоящих workflow outcomes.
Исторические assertions и7installed source identities остаются обязательными,
но не объявляются current transport/quality proof.
Четыре исходных controls сохраняются; существующий qualityFAIL не считается kill.
Без отчётов или outcome receipt closure сохраняет явныйFAIL.
Сам новый closure runtime ещё pending.

Slice68 подключает P1-stack к тем же current reports и реальным outcomes.
Все прежние production commands, ранние failures и остальные jobs сохранены;
четыре отсутствовавших wrapper filenames заменены существующими build --check guards.
Wiring прошло независимое source review, runtime ещё pending.
Legacy/V2/Agent Developer и остальные core failures также ещё открыты;
предыдущие числа067 не объявляются результатами новогоa348.

## Reviewed slices этой публикации

| Slice | Commit | Изменение |
|---|---|---|
|64|`fd0e63d1`|P15 actual return/library-stage diagnostics без новых операций и без изменения verdict.|
|65|`e8faf845`|Удаление30admission cases после31/9proof;4исходных guards и архив сохранены.|
|66|`14776d3e`|Четыре fixtures используют finite public prepare/index grant; прежние вопросы и все assertions сохранены.|
|67|`ff5e6022`|Current closure, SHA/manifests/outcomes, прежние history guards и4controls.|
|68|`befa475d`|P1-stack actual outcome/report wiring, прежние production gates и short-circuit сохранены.|

Все slices прошли независимое source review и exact parent/tree/blob verification.
Runtime64–68 pending. В66 один question-frame и три generic workflow variants:
names/params/counts прежние, assertions перенесены только под isolated_service;
прочие16generic functions побайтно сохранены. Исправление подготовки может выявить
следующий реальный retrieval failure; заранее PASS не заявляется.

Общие сокращения: alias49→1; literal702→82; intent32→2; admission34→5.
Перенос внутренних iterations в одну функцию не считается уменьшением actual work.

## Следующие действия

1. Новый совместный CI для64–68; прочитать P15 actual return diagnostics и closure controls.
2. Исправить cold startup write и подтвердить recovery12baseline/16kills.
3. Проверить actual P1-stack outcome wiring; разобрать P14/P15/Legacy/V2/Agent Developer/
   adversarial/language/core failures по actual evidence без ослабления gold/guards.
4. Default-binding family: собственный precheck и mutation proof до retirement.
5. Итоговый acceptance: полный core, advanced, required CI/P1 и все необходимые
   downstream на конечномSHA, installed/transport/platform и отдельные client evidence.
6. Merge-ready только после обязательных gates. Сам merge — отдельное действие.

## Рабочая среда

Refs: implementation/pr211-merge-readiness и integration/stage3-v2-identity-pr1.
Только ordinary fast-forward; force/merge/release/внешние комментарии не выполнялись.
Local checkout устарел после0049c6d; exec transport недоступен с18:09UTC.
После outage local AST/import/compile/runtime **NOT RUN**.
Изменения готовятся exact-file GitHub API и проверяются разрешённым PR CI.
Пользовательские индексы, новые модели/providers/реальныеclients не запускаются
без соответствующего уже имеющегося разрешения.

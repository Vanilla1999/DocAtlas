# PR #211: checkpoint продолжения

Обновлено 2026-10-09, 22:16 UTC. Reviewed code этой публикации — до
`4726085b394911d9c09688804871217febb15e55`.
Следующий commit добавляет этот checkpoint и карту последнего полного core.

**PR пока не готов к merge.** Slices57–62 требуют общего CI.
Ожидаемые улучшения не засчитываются как PASS.

## Действующие решения

- Потолки **6144 bytes / 800 tokens / 3 sources** отменены. Измеряем и сокращаем
  объём, сохраняя полные факты, source identity, scope/version/hash и consent guards.
- Операционные input/read/work/call/time ограничения сохраняются.
- Retrieval включён в позднее утверждённый план; прежний blanket deferral снят.
- Сокращение tests требует собственного зелёного baseline и доказанного обнаружения
  дефектов. Не считать оставшиеся FAIL устаревшими автоматически и не заменять
  обязательные quality facts фактическим пустым результатом.
- Реальные Claude Code/Codex/OpenCode sessions **NOT RUN**. Installed SDK/stdio
  harness не подтверждает такие sessions.

План: [PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md).
Решения: [CURRENT_WAVE_DECISIONS_RU.md](CURRENT_WAVE_DECISIONS_RU.md).
История до067 сохранена побайтно:
[CHECKPOINT_067dd560_RU.md](pr211-execution/CHECKPOINT_067dd560_RU.md),
git blob `7659d17450bcb4dff2260cd2481be61d1153f5ff`.
Позднейшие версии checkpoint доступны в Git history; local checkout устарел.

## Последний полностью прочитанный core: 0855fb49

SHA: `0855fb491ec388100cce92e57fe64b889c4cd3e0`.
[Main run37996655986](https://github.com/Vanilla1999/DocAtlas/actions/runs/37996655986).
Каждая Python lane **3.11 / 3.12 / 3.13**:
**7818 = 6025 PASS / 1783 FAIL / 0 ERROR / 10 SKIP**.
Матричные повторы не суммируются.
[JUnit reader114047940486](https://github.com/Vanilla1999/DocAtlas/actions/runs/37996655986/job/114047940486):
integrity issues пусты, console omissions0.

| Python | SHA256 JUnit |
|---|---|
|3.11|`e55628e72827287645f7573167aae9e54751a0bfb927c7bba18245d15e6ce010`|
|3.12|`e86a485bf7d395f92f37b16d5b375418c22515e16efac548fee7e54d0d08e666`|
|3.13|`7bf8f61dd61f0ce56af31dbdb22bbd2785b3be2acf22e2b68bcf1f04acdf2ea6`|

Карта всех221 failing modules с1783FAIL:
[CORE_FAILURE_MAP_0855fb49.jsonl](pr211-execution/CORE_FAILURE_MAP_0855fb49.jsonl).
Она содержит exact counts/первый node/message, исследованные причины и явный
`not_investigated` для остальных. Первый failure не классифицирует весь модуль.
Предыдущая карта2acf сохранена для сравнения.

Сравнение с полным c1e058cb:
**7849 = 6013 PASS / 1826 FAIL / 0 ERROR / 10 SKIP** на каждой lane.
На0855 удалён31 intent classifier case (26FAIL + 5PASS), а17 terminal/schema
ожиданий исправлены и проходят. Это точно объясняет +12PASS/−43FAIL/−31collected.
Три terminal модуля больше не имеют failures; сохранённый mixed intent test остаётсяFAIL.
Новых collection errors и необъяснённых изменений module counts нет.

### Точные сохранённые outcomes

| Семейство | PASS / FAIL на0855 |
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
присутствуют в JUNIT_TRACKED со статусомPASS на каждой lane.
Второй completion test с полным mkdocs-05 priority fact остаётся исходным и падает.
Task33C64/64 подтверждён наc1e058cb; workflow на0855 такжеSUCCESS.

## Recovery и сила заменяющих проверок

[Advanced0855 / job114044351234](https://github.com/Vanilla1999/DocAtlas/actions/runs/37996655986/job/114044351234):
новый recovery baseline **11 PASS / 1 FAIL / 0 ERROR**.
`closed_literal_context` упал на `recovery_closed_context_is_read_only`.
Directed16mutant kills не подтверждены: failed baseline не даёт mutation credit.
Прежние11cases/14kills были подтверждены наc1e058cb.

Slice62 сохраняет те же четыре state fingerprints и строгий equality guard,
добавляя failure-only log с конкретным read/question и changed fields.
Статически обнаружены startup writes LibraryRegistry/DocsJobTracker при первом
cold.materialize после before-hash; точный actual changed field ещё должен показать CI.
Warming, перенос before-hash за initialization и ослабление guard не выполнены.

Normal critical baseline на0855 по-прежнемуFAIL из-за нового admission precheck.
Наc1 first failure: ValueError, too many values to unpack. В вопросе
«Can a handler for `for` be synchronous?» были два одинаковых по тексту mentions.
Slice57 выбирает quoted occurrence по независимым offsets [19,22), сохраняя
отдельный unresolved connective [14,17) и все50оригинальных occurrences.
Нужны actual **31baselinePASS / 9intendedkills** до удаления30obsolete cases.
Старые34admission tests пока collected.

Последний normal critical PASS на2acf: **30baseline / 8intendedkills**,
включая точный intent mutant guard и 1FAIL/0ERROR/0SKIP.
Этого было достаточно для узкого intent retirement52, но не для admission retirement.

## Current quality evidence

### P1.4

[Run37996655933 / job114044350157](https://github.com/Vanilla1999/DocAtlas/actions/runs/37996655933/job/114044350157),
SHA0855: **9/14 total**, discovery **5/10**, full facts **4/5**, runtime errors0.
Все14 READ_STATE проверки совпали; пятьoracle controls/integrity/syntaxPASS.
Оба целевых behavior cases OrdersDraftStore/PaymentOutbox теперьPASS.
Остаются requirements validation contract/conditions, retry policy и два alias cases.
Полезные bodies найдены, но current qualification продолжает отвергать эти вопросы.

### P1.5

[Run37996655934 / job114044350172](https://github.com/Vanilla1999/DocAtlas/actions/runs/37996655934/job/114044350172),
SHA0855: **2/7 total**, **0/6 verified full facts**, errors0,
шестьoracle controls/integrity/syntaxPASS.
Полные canonical policy и implementation факты теперь видимы, но не засчитываются
из-за source_integrity. По каждому найден ровно один matching committed child.
Ровно четыре поля отсутствуют в snapshot: source_identity, source_content_hash,
byte_start, byte_end. Прочие сравниваемые поля совпадают.
Snapshot class=project_doc; stored class=project_file.

Slice58 переносит эти уже существующие metadata в context DTO.
Slice59 отдельно обосновывает точную пару storage/DTO классов и требует её
одновременно с прежними child/owner/scope/authority/hash/span/generation guards.
Шесть class и три committed metadata forgeries добавлены внутрь прежних controls.
Три прочих positive cases ещё требуют полного факта; library/mixed stage пока
нуждается в наблюдении фактического unified return, не в догадке о ranker.

### P1.6 и общий closure

Slice60 сохраняет все6исходных questions/candidates/requirements и historical report.
Подменён только retrieval boundary; dispatcher, handler, projector, validator и обе
сериализации установленных MCP models реальные. Полный положительный факт [0,32)
проверяется независимым frozen oracle, не добавляется в запрос.
Шесть прежних self-test names сохранены; fault control требует passing actual baseline.
Current6cases/6controls ещё должны пройти CI.
Это не indexed retrieval, stdio session или LLM/client evidence.

P1 closure ещё читает historical committed v1 reports. Такой green не означает
current P14/P15/P16 acceptance. Отдельная current-evidence integration готовится.

Последние подробно разобранные quality числа067: V2 full facts6/15natural,
1/5paraphrase; Legacy original coverage0<12; Agent Developer closure8/11,
adversarial24/28. Эти исторические числа не подменяют новый CI.

## Reviewed slices этой публикации

| Slice | Commit | Изменение |
|---|---|---|
|57|`dfedcc08`|Exact quoted occurrence в admission precheck; краткая диагностика failed baseline из существующего JUnit.|
|58|`cd38b5da`|Copy-only source/raw-hash/byte lineage handoff; те же3real-service fixtures проверяют actual stored rows и Unicode bytes.|
|59|`11b980ef`|Точная пара project_file/project_doc и прежние provenance guards; отдельный crosswalk и negative controls.|
|60|`32bfd370`|Current evidence-is-data public delivery, frozen independent oracle, real MCP serialization и прежние downstream gates.|
|61|`dcb4798c`|Четыре оставшихся ожидания output truncation заменены full-value/digest assertions; names/params/операционные guards прежние.|
|62|`4726085b`|Failure-only recovery state diagnostics; verdict и guard не меняются.|

Все slices прошли независимое source review и exact parent/tree/blob verification.
Локальное исполнение не выполнялось; runtime новых57–62ещё pending.
Предыдущие slices49–56 подробно сохранены в checkpoint0855 и их отдельных notes.

Сокращения: alias49→1; literal702→82; intent32→2 (current contract + retained mixed).
Перенос внутренних iterations в одну функцию не считается уменьшением actual work.
Admission retirement не разрешён до его собственного зелёного baseline и intended kills.

## Следующие действия

1. Прочитать recovery changed-field diagnostic; исправить доказанную cold startup
   boundary без маскирования writes, затем подтвердить12baseline/16intendedkills.
2. Получить31baseline/9kills critical gate и лишь затем удалить30obsolete admission
   cases с сохранением четырёхliveguards.
3. Подтвердить combined P1.5 lineage/class changes и P1.6 delivery/self-controls.
4. Разобрать оставшиеся P1.4/P1.5/original-query/V2/closure/adversarial/language/core
   failures по actual evidence; gold facts и guards не ослаблять.
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

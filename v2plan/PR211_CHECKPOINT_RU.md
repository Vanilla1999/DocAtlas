# PR #211: checkpoint продолжения

Обновлено 2026-10-09, 21:57 UTC. Код и diagnostics этой публикации — до
`ecf41c57954eb910ce13b6857b9df415f763789b`.
Commit checkpoint добавляет этот файл и карту последнего полного core.

**PR пока не готов к merge.** Новый общий CI должен проверить slices52–55.
Неподтверждённый ожидаемый результат не считается PASS.

## Действующие решения

- Потолки **6144 bytes / 800 tokens / 3 sources** отменены. Измеряем и сокращаем
  объём, сохраняя полные факты, source identity, scope/version/hash и consent guards.
- Операционные input/read/work/call/time ограничения сохраняются.
- Retrieval включён в позднее утверждённый план; прежний blanket deferral снят.
- Сокращение tests требует собственного зелёного baseline и доказанного обнаружения
  дефектов. Не считать все оставшиеся FAIL устаревшими и не заменять quality facts
  фактическим пустым результатом.
- Реальные Claude Code/Codex/OpenCode sessions **NOT RUN**. Installed SDK/stdio
  harness не является доказательством таких sessions.

План: [PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md).
Решения: [CURRENT_WAVE_DECISIONS_RU.md](CURRENT_WAVE_DECISIONS_RU.md).
История до067 сохранена побайтно:
[CHECKPOINT_067dd560_RU.md](pr211-execution/CHECKPOINT_067dd560_RU.md),
git blob `7659d17450bcb4dff2260cd2481be61d1153f5ff`.
Позднейшие checkpoint версии доступны в Git history; не использовать старый local checkout.

## Последний полностью прочитанный core: 2acfaa4f

SHA: `2acfaa4fdac8cc599d84ae1c48836335e9cd29a7`.
[Main run37994136625](https://github.com/Vanilla1999/DocAtlas/actions/runs/37994136625).
Каждая Python lane **3.11 / 3.12 / 3.13**:
**7848 = 6011 PASS / 1827 FAIL / 0 ERROR / 10 SKIP**.
Не суммировать матричные повторы.
[JUnit reader114038915258](https://github.com/Vanilla1999/DocAtlas/actions/runs/37994136625/job/114038915258):
integrity issues пусты, console omissions0.

| Python | SHA256 JUnit |
|---|---|
|3.11|`bd30d0ebc7671cc2f9aa29cbeb9ebc892485add0b5c8534c4d6958c9876a4c0b`|
|3.12|`9e0dae5e1ab140787006846bbcffe996ab45ab14ca339d9542888483fac8cb1a`|
|3.13|`9ac5c178e42b8456259de0e5bf8fa95a16e2af4afc281d02759d3fb7c6891569`|

Карта всех224 failing modules с1827FAIL:
[CORE_FAILURE_MAP_2acfaa4f.jsonl](pr211-execution/CORE_FAILURE_MAP_2acfaa4f.jsonl).
Она содержит exact counts/первый node/message, исследованные причины и явный
`not_investigated` для остальных. Первый failure не классифицирует весь модуль.
Карта не означает устранение остальных ошибок.

### Точные tracked outcomes на2acf

| Семейство | PASS / FAIL |
|---|---|
|ActionPacket main|29 / 2|
|ActionPacket part02|8 / 0|
|Context completion followup|1 / 1|
|Docs read-next|31 / 0|
|SourceMap|29 / 0|
|Member transactions|116 / 0|
|Alias current contract|1 / 0|
|Project intent current contract|1 / 0|

Generated SourceMap node, семь invalid-storage и три real-service nodes явно
присутствуют в JUNIT_TRACKED со статусомPASS на каждой lane.
Второй completion test с полным `mkdocs-05` priority fact остаётся исходным и падает.

На2acf normal critical gate: **30 baseline PASS / 8 intended mutant kills**.
Новый intent mutant обнаружен ровно guard `critical_project_intent_no_inferred_roles`,
**1 test / 1 FAIL / 0 ERROR / 0 SKIP**.
[Advanced114035684048](https://github.com/Vanilla1999/DocAtlas/actions/runs/37994136625/job/114035684048).
Literal comparison historical702/compact82/51directed mutants такжеPASS.
Эти данные разрешают только соответствующее узкое сокращение.

## Более новый частичный acceptance: c1e058cb

SHA: `c1e058cb51072f02620329000e2d68706a96bd67`.
[Main run37995500411](https://github.com/Vanilla1999/DocAtlas/actions/runs/37995500411).
Полный core reader ещё не получен на момент записи.

- [Task33C114040356892](https://github.com/Vanilla1999/DocAtlas/actions/runs/37995500248/job/114040356892):
  **64 PASS**, 3.31s, workflowSUCCESS. Исправление SDK envelope/raw packet validation
  подтвердилось; прежние два failures отсутствуют.
- [P1.5 114040357202](https://github.com/Vanilla1999/DocAtlas/actions/runs/37995500399/job/114040357202):
  **2/7 total**, **0/6 verified full facts**, **0 runtime errors**.
  Все пять внешних preparations завершились; robots/host ownership barriers сняты.
  Все6oracle controls, report integrity и syntaxPASS.
  Canonical policy получает исходный полный факт, но source_integrity даёт
  `different_project_scope_or_authority` и `source_not_bound_to_committed_child`.
  Четыре других positives не доставляют полные факты. Authority/preparation/state
  errors пусты; это не разрешает скрыть source/fact failures.
- [Advanced114040357523](https://github.com/Vanilla1999/DocAtlas/actions/runs/37995500411/job/114040357523):
  recovery **11 baseline PASS / 14 intended guard kills**.
  Новый общий critical precheck завершился **BASELINE FAILED** после добавления
  admission-meaning control; normal9mutants не засчитаны и retirement запрещён.
  Причина baseline исследуется. Старые34admission cases остаютсяcollected.
- Installed MCP harness, static/docs contract и часть platform jobs ужеSUCCESS;
  это не полный итог всех workflows и не real client sessions.

## Сохранённые quality gaps

P1.4 на2acf: **14/14 read-only checks PASS**, **7/14 total**, discovery **3/10**,
full facts **2/5**, runtime errors0; пятьoracle controlsPASS.
[Job114035683658](https://github.com/Vanilla1999/DocAtlas/actions/runs/37994136669/job/114035683658).
Для original `What does OrdersDraftStore do?` весь правильный85-char body найден;
canonical qualifier отвергает его за1/4lexical ratio, bare mention остаётсяunresolved.
Новый slice53 адресует эту точную admission boundary; собственный CI ещё обязателен.

Последние подробно разобранные quality результаты067: V2 full facts6/15natural,
1/5paraphrase; Legacy original coverage0<12; Agent Developer closure8/11,
adversarial24/28. Новые результаты нельзя подменять этими числами.
P1.6 ожидает миграцию от устаревшего support certificate к реальному public-delivery
fixture с полным положительным фактом и наблюдаемыми action/authority/source guards.
Исходные6questions/texts/metadata и historical report сохраняются.

## Reviewed slices после предыдущего checkpoint

| Slice | Commit | Изменение |
|---|---|---|
|49|`2953de69`|Канонический owned fixture home до P1.5 member/library preparation.|
|50|`e703d0c5`|SDK wire `kind=patch_context` проверяется отдельно; raw validator получает полный packet без единственного transport key и с корректным estimate.|
|51|`c1e058cb`|Admission-meaning precheck с независимым oracle/новым mutant; baselineFAIL, старыеcases сохранены.|
|52|`1171832b`|После actual intent proof удалены31classifier-onlycases; mixed ranking function целиком сохранён.|
|53|`c7a5af0f`|Полностью замкнутые literal questions получают source-bound context;23real reads/13replay guards/2directed mutants.|
|54|`d30150e5`|Полный Docs DTO и snapshot fidelity вместо output ceilings; сохранены invalid-patch и schema security guards.|
|55|`ecf41c57`|Body-free diagnostics actual P1.5 source/committed-child fields; scorer и saved report неизменны.|

Все slices прошли независимый source review и exact parent/tree/blob verification.
Runtime новых52–55изменений ещё должен пройти на общемSHA.
Details: [closed literal](PR211_CLOSED_LITERAL_CONTEXT_RU.md),
[intent retirement](pr211-execution/PROJECT_QUERY_INTENT_RETIREMENT_RU.md),
[terminal/schema](pr211-execution/TERMINAL_DELIVERY_AND_SCHEMA_MEANING_RU.md),
[P1.5 diagnostics](PR211_P15_COMMITTED_CHILD_DIAGNOSTICS_RU.md).

Сокращение intent: исходные32cases → current control1 + retained mixed1 =2,
net−30; этот slice снимает31case из уже расширенной precheck collection.
Ранее доказаны alias49→1 и literal702→82. Не выдавать уменьшение ordinary collection
за уменьшение всех внутренних property comparisons или всех CI executions.

## Следующие действия

1. Получить actual recovery12baseline/16mutants, P1.4, terminal/schema и full core
   на SHA этой публикации. НовыеP1.4guarantees не считать подтверждёнными заранее.
2. Исправить точную причину admission precheck baselineFAIL; доказать baseline/9kills
   перед retirement30obsolete grammar cases. Четыреliveguards сохранить.
3. По новымP1.5diagnostics подтвердить source_class mapping и возможную потерю
   source_identity/source_content_hash/byte spans в context DTO. Проверку настоящего
   committed child не заменять совпадением видимого текста.
4. ЗавершитьP1.6public-delivery migration и разобрать remaining original-query/full-fact,
   closure/adversarial/language/core failures по карте без ослабления gold.
5. Итоговый acceptance: полный core, advanced, required CI/P1 и обязательные downstream
   на конечномSHA; установочные/transport/platform проверки и отдельные client evidence.
6. Готовность к merge заявлять только после всех обязательных gates. Сам merge — отдельное действие.

## Рабочая среда

Refs: `implementation/pr211-merge-readiness` и `integration/stage3-v2-identity-pr1`.
Только ordinary fast-forward. Force/merge/release/внешние комментарии не выполнялись.
Local checkout устарел после0049c6d; exec transport недоступен с18:09UTC.
После outage local AST/import/compile/runtime **NOT RUN**.
Изменения готовятся exact-file GitHub API и проверяются разрешённым PR CI.
Не запускать пользовательские индексы, новые модели/providers/реальныеclients
без соответствующего уже имеющегося разрешения.

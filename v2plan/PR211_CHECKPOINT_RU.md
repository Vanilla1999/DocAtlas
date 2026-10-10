# PR #211: checkpoint продолжения

Обновлено: 2026-10-10 03:30 UTC.

**PR пока не готов к merge.** Последний завершённый фактический CI:
PR HEAD `cadeef515ea78c78338821f38b15fed3bde7c993` (118),
merge checkout `9f25f147c522d84f61a57abb1d731d2b6e792c9a`,
общий tree `62d727c3ffbb35e77f0301d0e961e6f60ed4ebe2`.
Reviewed slices119–120 описаны ниже; их собственный runtime **PENDING**.

## Действующие решения

- Потолки **6144 bytes / 800 tokens / 3 sources** отменены. Сокращаем полный
  полезный output с сохранением фактов, source identity, scope/version/hash и consent.
- Операционные input/read/work/call/time ограничения остаются.
- Retrieval включён в утверждённый план; прежний blanket deferral снят.
- Retirement — после независимого oracle, собственного зелёного baseline,
  intended mutation proof и сохранности helpers/imports/selectors/archive.
- Legacy acceptance по ADR0003: полный frozen fact coverage исходных cases
  с floor **12/15**. Raw original-query coverage — отдельная метрика;
  lookup/parent credit не повышает её. Миграция явно версионирована.
- Реальные Claude Code/Codex/OpenCode sessions **NOT RUN**. Installed SDK/stdio
  подтверждает CI transport, но не эти клиентские sessions.
- Локальные runtime/import/pytest/AST/install не выполняются. Используются
  существующие авторизованные PR workflows без новых providers/models.
- Обычные commits и fast-forward двух refs разрешены. Merge/release,
  force-push и внешние comments/messages не выполняются.

План: [PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md).
Решения: [CURRENT_WAVE_DECISIONS_RU.md](CURRENT_WAVE_DECISIONS_RU.md).
Старый local checkout не является актуальной базой.

## Фактический CI: 118

[Main run](https://github.com/Vanilla1999/DocAtlas/actions/runs/38019193867).
[P1-stack](https://github.com/Vanilla1999/DocAtlas/actions/runs/38019193889).
[Acceptance reader](https://github.com/Vanilla1999/DocAtlas/actions/runs/38019193867/job/114118025694).
[Выбранные точные runtime records118](pr211-execution/RUNTIME_EVIDENCE_cadeef51.json).

На **каждом** Python 3.11/3.12/3.13:
**7727 = 6065 PASS / 1652 FAIL / 0 ERROR / 10 SKIP**.
Матрица не складывается в один baseline. JUnit integrity issues пусты.
По сравнению с113: один исправленный mixed control, collection прежняя.
С107 устранено 41 падение: 40 в optional observers и одно в mixed fixture.
Старые cases в114–118 не удалялись.

| Python | SHA-256 JUnit |
| --- | --- |
|3.11|`7aaa2b1d076691f16ecf3e144f904aa5c8547bfb5725afb19cb0f956d7eb58b3`|
|3.12|`91c369fe9b2f47bc5f1f1acd6434a884bdac99a76bade2384c2c7661f432f813`|
|3.13|`221cb1d1db49ed879b8c44732315c4f79d2877c66f86c7bf997248f9bdf1caa7`|

| Gate | Actual118 | Практическая граница |
| --- | --- | --- |
|Critical|**54P/0F/0E/0S; step SUCCESS**|29 intended kills подтверждены строгим producer целиком; individual hashes ещё не получены из console.|
|Recovery|**12P/0F/0E; 33 mutants killed**|Stored summary status=passed; baseline healthy. Не все individual records включены в receipt.|
|Literal historical/compact comparison|SUCCESS|Отдельный existing comparison step; не подменяет DQP33 proof.|
|P1.4|12/14; discovery8/10; facts5/5; oracle5/5|Два original-only discovery failures.|
|P1.5|**7/7; facts6/6; oracle6/6**|Current provenance PASS.|
|P1.6 current|**6/6; facts1/1; oracle6/6**|Retained adversarial24/28 и его mutation baseline FAIL.|
|Legacy live|Source-fact acceptance **8/15**, raw original coverage0|Floor12/15 не достигнут; report FAIL.|
|V2 live|Natural facts6/15; paraphrase facts1/5|Report сформирован, REPORT_ONLY; production runner FAIL.|
|Current closure|Reports integrity PASS; oracle4/4|Current quality и required outcomes FAIL.|
|Installed MCP|**1/1; self-test7/7; report verification PASS**|Reviewed wheel, deterministic SDK/stdio; false-supported0, contamination0.|
|Retrieval evidence / platforms / build / wheel / sdist|SUCCESS|Это отдельные завершённые jobs.|
|Required CI / P1-stack exact|**FAIL**|Core и advanced остаются красными.|

Hermetic quality16/16 проверяет literal query identity без retrieval.
Legacy raw report8/16 и positive7/15 отличаются от принятого source-fact oracle8/15.
Agent Developer v1:11tasks executed,4target gaps; false_supported=0,
forbidden_source_contamination=0. Ошибки получения полезного контекста сохраняются.

Reader log: 586750 UTF-8 bytes, SHA-256
`c531b3800493f54970adadb724b84a49ccbb12535d86aebc254bc5612f3bb7c2`.
Разобраны 326 JSON records без ошибок. JUnit console omitted=0.
Artifact console: 128 selected / 51 printed / 77 omitted.
Все три compact V2 headers получены. **Все 29 individual critical mutant records
не попали в console118**; для DQP33 нужны четыре конкретных own receipts.
Aggregate SUCCESS не заменяет их before/after/import hashes.

Receipt сохраняет 27 выбранных parsed records целиком, metadata jobs и точные
короткие downstream/installed console lines. Это не полный diagnostic ledger.
SHA-256 receipt: `ea98324651792ea224aca6aac6988ef396593f698a888109c0e58e293ee47f8a`;
333370 UTF-8 bytes. Остальные observed rows остаются в CI artifacts.

## Установленные причины retrieval failures

### 1. Cache reset / architecture: failed qualification

[Аудит exact113](pr211-execution/V2_QUALIFIED_WINDOW_AUDIT_113_RU.md)
сопоставляет полные current source bytes, шесть raw/public window hashes и
frozen facts. Все qualified member windows **3/1** дошли до public.
Числа20→3/1 сами по себе не означают потерю после квалификации.
Нужные cleanup/infrastructure paragraphs были найдены, но имели пустые
`qualified_query_ids`. Этот source finding относится к113; actual118 quality
counts приведены отдельно выше.

Для полезного partial context требуется отдельный admission contract с
relevance/body/identity/scope/current/hash guards. Нельзя просто понизить ratio
под эти cases, пропустить любой body hit либо изменить gold/host lookups.
Unknown-modifier/lunar-policy negative controls сохраняются.

### 2. Request flow: post-acquisition view truncation блокирует delivery

Actual118 `v2-natural-request-flow`: member 31 windows, 15 qualified;
project и Unified 20 windows, 9 qualified. Наблюдённый `project_docs` stage:
observed 27 items / 18457 bytes → retained 20 items / 12016 bytes,
item_limit 20, byte_limit 65536, `budget_exceeded=true`, status=insufficient.
Остальные routing stages не превышены. Project/Unified result status=success,
consent не требуется, но delivery=false; public sources 0.

Срез отдельно разбирает post-acquisition control view и реальные acquisition
bounds. Он ещё не исправлен. Нельзя повысить20 до другого magic number,
безусловно игнорировать budget flag или обходить ACK/consent/stale/work guards.

## Reviewed пакет после118: собственный runtime pending

| Slice | Commit | Изменение |
| --- | --- | --- |
|119|`93bc8d82ec7ec3f0618f9b12624030026566c48e`|Relation25 precheck:2 original representatives/2plan calls,1 directed generation mutant;0new ordinary functions,25oldcases пока collected.|
|120|`9d1ea6a0bc1a789aee36ec52eb6a5a5260f94c4c`|Priority critical/recovery operands с actual import stdout;4existing lossless-case outcomes в JUnit reader.|

[Relation precheck](pr211-execution/RELATION_COMPILER_PRECHECK_RU.md).
[Priority reader](pr211-execution/ACCEPTANCE_OPERANDS_PRIORITY_RU.md).
Code slices имеют root и независимый peer source review.
Новый target — critical 54 healthy / 30 intended kills; это не runtime PASS.
Import probe — **отдельный subprocess до pytest**, не same-process attestation.

## Следующие конкретные действия

1. Опубликовать reviewed119–120 и этот checkpoint обычным fast-forward
   implementation/pr211-merge-readiness и integration/stage3-v2-identity-pr1.
   Получить own critical operands на новом joint SHA.
2. После четырёх DQP named guards+source/import receipts применить reviewed
   retirement 33: 29→16 functions, 70→37 cases. После собственного нового relation
   kill — отдельный retirement 25: 6→4 functions, 72→47 cases.
   Helpers/imports/unselected safety/body/condition cases и diagnostic hashes сохранить.
3. Старый один test с default3/800 пока отдельно pending: реальные четыре
   lossless successors уже есть, но dedicated cap mutants ещё не выполнены.
   Не объявлять их runtime из агрегата всего module.
4. Довести narrow request-flow read-presentation fix с operational guards.
   Параллельно определить безопасный partial-context критерий для original-only
   P1.4/Agent Developer и оставшихся V2 facts; исходные вопросы/facts не менять.
5. Продолжить remaining relation47 и другие failure families по первой причине;
   не удалять их только потому, что CI красный. Завершить required/downstream
   и необходимые installed/client acceptance на конечном SHA.

Исторический actual113 сохранён в
[RUNTIME_EVIDENCE_441cdefd.json](pr211-execution/RUNTIME_EVIDENCE_441cdefd.json).
Не принимать прежние статические APPROVE или aggregate job SUCCESS за
доказательство отсутствующих individual runtime operands или полного merge acceptance.

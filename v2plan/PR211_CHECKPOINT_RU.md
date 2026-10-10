# PR #211: checkpoint продолжения

Обновлено: 2026-10-10 05:07 UTC.

**PR пока не готов к merge.** Последний завершённый CI — PR HEAD
`0065ce62cacaa31a41e4567717e3c67d602f578b` (130), merge
`e4084e51b73725990a107e8b8fc930a8edb46f75`, общий tree
`628bb7a2eb16f740ce84384925531040f7ec9f5e`.
Reviewed follow-up131–134 собран на `7b56e7b61ff28024349ae13d8e60a591788b83cf`;
его новый runtime **PENDING**. Старый local checkout не является базой.

## Действующие решения

- Потолки **6144 bytes /800 tokens /3 sources** отменены. Сокращаем полезный
  полный output с сохранением фактов, identity/scope/version/hash/consent.
- Действующие operational input/read/work/call/time bounds остаются. Public
  question не имеет ceiling4000; это внутренняя граница legacy compiler.
  Original сохраняется полностью, explicit lookups остаются максимум5 по500.
- Retrieval входит в порученный план; прежний blanket deferral снят.
- Retirement требует собственного здорового successor, intended mutation proof,
  полного сохранения исходных inputs и проверки helpers/imports/selectors.
- Legacy по ADR0003 требует полные frozen facts минимум12/15 исходных cases.
  Raw original coverage измеряется отдельно; lookup credit не переносится.
- Installed SDK/stdio не доказывает Claude Code/Codex/OpenCode sessions:
  реальные clients **NOT RUN**.
- Локальные runtime/import/pytest/AST/install не выполняются. Используются
  существующие авторизованные PR workflows без новых providers/models.
- Обычные commits и fast-forward двух refs разрешены. Merge/release,
  force-push и внешние comments/messages не выполняются.

[План](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md) ·
[решения](CURRENT_WAVE_DECISIONS_RU.md).

## Фактический CI130

[Main run](https://github.com/Vanilla1999/DocAtlas/actions/runs/38024963940) ·
[Acceptance reader](https://github.com/Vanilla1999/DocAtlas/actions/runs/38024963940/job/114135542071) ·
[Сохранённые records130](pr211-execution/RUNTIME_EVIDENCE_0065ce62.json).

На каждом Python3.11/3.12/3.13:
**7669 = 6067 PASS /1592 FAIL /0 ERROR /10 SKIP**.
По сравнению с126 — пять FAIL меньше при прежней collection. Это не полный PASS.
JUnit integrity issues пусты; три матрицы не складываются в один baseline.

| Python | JUnit SHA-256 |
| --- | --- |
|3.11|`61443a034600c931f6a236f2bea8945e3ca1cf5359b53e4f53d99ecdf1ab77bc`|
|3.12|`b3d0410960b5d627d3f135aaa1afae41b75ac3d92f7358645ba70843b4ff74c9`|
|3.13|`6eb564ee06a52a8185db0a6fd5dff5c506d155343b38402ec54f505aac2fcce2`|

| Gate | Actual130 | Граница результата |
| --- | --- | --- |
|P1.4|**14/14 cases,10/10 discovery,5/5 complete facts**,0errors|Собственный зелёный run38024964052; oracle5/5. Два прежних ordinary original-only gaps закрыты.|
|Recovery|**12/12 healthy и39/39 intended kills**|Все39 individual outcomes совпали с owning case/guard:0P/1F/0E. Шесть ordinary guards имеют собственное доказательство130.|
|Critical|**60 entries,1 observed FAIL**|Единственный FAIL — `critical_project_read_request_work_bound`, fixture label `oversized_original`. 37mutants не выполнялись.|
|Literal historical/compact|Existing step16 SUCCESS|Individual104 child receipts не выведены прежним reader; aggregate не разрешает новое retirement.|
|Lossless projection|**32/32** на каждом Python|Все4 существующих cap killer cases PASS; собственные4 fault kills ещё блокирует critical.|
|Legacy|**8/15** full source facts при floor12|Raw original coverage0; six hard-zero guards сохраняются.|
|V2|Natural **6/15**, paraphrase **2/5**|Paraphrase улучшился с1/5; flow остаётся2/4. Production runnerFAIL.|
|Agent Developer|V1 target-closed8/11,4gaps; adversarial24/28|Нет нового target-green или ошибки исполнения; module/comparison/policy gaps остаются.|
|P1.6|Public6/6,full facts1/1,oracle6/6|Общий jobFAIL из-за Agent Developer; его public-only часть не равна всему acceptance.|
|Installed MCP|**7/7 selftests,1/1 scripted task**|Реальный stdio CI transport; пользовательские client sessions NOT RUN.|
|Retrieval evidence / platforms / P1.5|SUCCESS|Ubuntu, macOS Intel/ARM, current P1.5; output ceilings не возвращаются.|
|Required CI / P1 stack / closure|**FAIL**|Core, advanced, quality и language diagnostics остаются красными.|

Всего18 workflows:11SUCCESS,6FAILURE,1SKIPPED. Hermetic16/16 проверяет
query identity без retrieval и не заменяет live quality.

Reader:642613 UTF-8 bytes, SHA-256
`db7554f76f20570a38c61035d9af43bf85cdb45792f1dd048fe85278b8211a8c`.
367 JSON records,0parse errors; JUnit console omitted0.
Все41 recovery operand records (два12-case reports и39 mutants) доступны.
70 из151 selected artifact rows не вошли в console; priority omissions0.
Receipt хранит121 exact selected records,39 intended outcomes, jobs и short-log
hashes; 450640 bytes, SHA-256 `55b19dd3bbe1814da2079293b56de60964506a519c1e5d18e14af1e92cfe336e`.
Полная независимая пересверка source/import operands всех39 этим receipt
не заявляется. Separate import probe не является same-pytest-process proof.

### Причина critical baseline и retention traces

Focused trace сохраняет helper line321/label `oversized_original`.
Значение `"x" * 4001` прочитано отдельно в exact fixturecb8bb, line317.
Ранний reject не предусмотрен public schema/handler; внутренний parser bound
не ограничивает передачу original в application. Slice134 исправляет именно
ошибочное fixture ожидание и добавляет fault, который обрезает original.

Шесть retention failures теперь названы в сохранённых focused records.
Два случая `test_unacknowledged_query_preserves_noncopyable_requirements`
(omitted/false) ожидают4, получают32; остальные четыре проверяют old bounded
control, completed invocation и число pure reranks. Они остаются открытыми:
изменение ожидаемого числа без contract/source review не выполнено.

## Reviewed follow-up131–134

| Slice | Commit | Изменение |
| --- | --- | --- |
|131|`687b78927cad5493a8483dcae982495f041ca663`|Existing literal104 receipt reader; critical trace tail до6000 без повторного512 cut. Runtime/tests/workflows не добавлены.|
|132|`17e39ddbc0f32b0e951f5b52e87984dcb551221d`|Question-plan полный архив28inputs, crosswalk26retire/2keep, одна метка в existing span assertion и один direct-builder fault. Ничего не удалено.|
|133|`c05056de1790127528f811f5180ac0ae13c2b0d8`|Literal raw-window containment/coordinates и full wire bytes;2native reads,3replays,4faults; relation recipe source hashes перепривязаны без reuse старого runtime.|
|134|`7b56e7b61ff28024349ae13d8e60a591788b83cf`|Тот же4001-character input проверяется на полную передачу до прерывания; реальный lookup limit сохранён. Один directed truncation fault; production не меняется.|

Следующий target **critical61healthy/39intended kills; recovery12healthy/43intended kills**.
Это ещё не результаты. Ноль новых pytest имён не означает ноль внутренней работы.

- [Literal reader](pr211-execution/LITERAL_COMPARISON_RECEIPT_READER_RU.md).
- [Question-plan precheck](pr211-execution/QUESTION_PLAN_V4_PRECHECK_RU.md).
- [Raw window и семь exact files](PR211_LITERAL_RAW_WINDOW_BINDING_RU.md).
- [Original input contract](pr211-execution/PROJECT_READ_ORIGINAL_INPUT_RU.md).
- [Ordinary body: собственный runtime130](PR211_ORDINARY_PARTIAL_BODY_ADMISSION_RU.md).
- [Предыдущее retirement58](pr211-execution/COMPILER_RETIREMENT_58_RU.md).

## Что осталось

**Качество.** V2 flow отдаёт MCP/gateway, но теряет application/selection facts.
Нужный qualified current paragraph уже присутствует на member/Project/Unified
границах. Source review нашёл две novelty проверки по query IDs/words,
способные отвергнуть другое source-bound содержимое того же lookup.
Точный actual first veto для flow ещё не напечатан; он не угадывается.
Следующий узкий slice использует неизменённый native24-window fixture и
независимую полноту исходных фактов, сохраняя provenance/qualification/authority
guards и дедупликацию одинаковых окон. Ceiling по объёму не вводится.

Legacy8/15, V2 architecture/cache-reset и четыре Agent Developer gaps открыты.
Raw span defect133 исправлен в source, но связь с каждым module MISS требует
собственного CI. Comparison не объявлен исправленным этим изменением.
Reported Packs/allowed-source failures в V2 request-flow требуют отдельного
разбора actual source content, без ослабления frozen oracle.

**Сокращение.** Уже удалены58cases с собственным121 proof; с126 новых удалений нет.
DQP37cases, relation47cases пока collected. Старый default3/800 test — до четырёх
собственных cap kills. Question-plan28cases остаются до healthy/direct-builder
proof и индивидуальных reused literal receipts; два literal/code tests сохраняются.
Exact-current consumer audit завершается отдельно. Причина FAIL не разрешает удаление.

**Acceptance.** После ordinary fast-forward131–134 и этого checkpoint проверить
новый merge SHA/tree,61/39critical,12/43recovery, literal child receipts,
P1.4/Agent/V2/core и downstream. Исправить реальные first failures; затем
retire подтверждённые семьи и довести required CI/quality/installed/client gates.

Исторические receipts сохраняются. Static APPROVE, прежний SHA, aggregate SUCCESS
и целевой roster не заменяют собственного исполнения.

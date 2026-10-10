# PR #211: checkpoint продолжения

Обновлено: 2026-10-10 00:44:49 UTC.

**PR пока не готов к merge.** Последний полностью завершённый фактический CI:
PR HEAD `f7b9253c8e477babf276ae8dd2cb18905451cd15`,
tree `cfe816a4e295961b2b529b612bbc63c39ff99ccf`.

Следующий reviewed пакет сохранён до
`820533361152ff3a143d2cf97d0c22a889486d75` (slices90–94).
Его совместный runtime **PENDING**. Изменения тестов не объявляются заранее PASS.

## Действующие решения

- Потолки **6144 bytes / 800 tokens / 3 sources** отменены. Измеряем и сокращаем
  объём, сохраняя факты целиком, source identity, scope/version/hash и consent.
- Операционные input/read/work/call/time ограничения остаются.
- Retrieval включён в позднее утверждённый план; прежний blanket deferral снят.
- Retirement — только после независимого oracle, собственного зелёного baseline,
  intended mutation proof и сохранности helpers/imports/selectors.
- Quality floors и исходные gold facts сохраняются. Original coverage12 — требование
  качества, а не отменённый потолок размера ответа.
- Реальные Claude Code/Codex/OpenCode sessions **NOT RUN**. Scripted installed
  SDK/stdio не подтверждает работу этих клиентов.
- Локальные runtime/import/pytest/AST/install не выполняются. Проверки идут в
  существующих авторизованных PR workflows. Новые providers/models не подключаются.
- Обычные commits и fast-forward двух рабочих refs разрешены; merge/release,
  force-push и внешние comments/messages не выполняются.

План: [PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md).
Решения: [CURRENT_WAVE_DECISIONS_RU.md](CURRENT_WAVE_DECISIONS_RU.md).
Предыдущий подробный checkpoint и вся история80c8 доступны в Git на f7b9253c.
Старый local checkout не является актуальной базой.

## Полный фактический CI: f7b9253c

Actual merge checkout: `011e808a0dcd2ec8104611a2257d17b5f20e327a`.
Проверены родители: main `d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c`
и указанный PR head. Checkout tree совпадает с PR tree.
Main и P1-stack workflow metadata также указывают именно этот PR HEAD.

[Main run38008532239](https://github.com/Vanilla1999/DocAtlas/actions/runs/38008532239).
[JUnit reader114085424570](https://github.com/Vanilla1999/DocAtlas/actions/runs/38008532239/job/114085424570).
[Полный receipt f7b9253c](pr211-execution/RUNTIME_EVIDENCE_f7b9253c.json).

На **каждом** Python3.11/3.12/3.13:
**7747 = 6057 PASS / 1680 FAIL / 0 ERROR / 10 SKIP**.
Integrity issues пусты; omitted_rows=0. Повторы матрицы не суммируются.

| Python | SHA256 JUnit |
| --- | --- |
|3.11|`e698399ef2c11d2b104f194404a0d5576e8696c7c825ac7b224e3378db60cd2d`|
|3.12|`d15d45c3ff1d9c3f86c80775dd46ddbee0e5416f4e8ff718faef615e73feb399`|
|3.13|`d456ba1cd8002db1bc9cce3f6e8d9732d07e3795ea8b874a00a2a2af398ef948`|

Все **215 failing modules** имеют те же counts, что80c8.
Это сравнение counts, не доказательство тождества каждого node.
Полная прежняя карта:
[CORE_FAILURE_MAP_80c8fbbb.jsonl](pr211-execution/CORE_FAILURE_MAP_80c8fbbb.jsonl);
новые actual module records и focused failures находятся в receipt f7.

В частности: member transactions116/116, parent-child21/21,
catalog5/5, dispatch3/3, read-next31/31, SourceMap29/29 — PASS.
Projection boundaries пока14P/6F; Context7 до retirement12P/45F;
docs_service_part03 до fixture migrations6P/18F; completion followup1P/1F.

Docs-contract, docs-impact, static-contract, retrieval-evidence, installer,
installed MCP и три platform smoke jobs SUCCESS. Core/advanced/required-ci FAIL.
P1-stack FAIL; его platform/build/wheel3.11–3.13/sdist/installer jobs SUCCESS.
Это packaging/stdio evidence, не подтверждение реальных клиентских sessions.

## Critical, recovery и downstream

[Advanced job114082885405](https://github.com/Vanilla1999/DocAtlas/actions/runs/38008532239/job/114082885405).

| Gate | Фактический результат f7 | Значение |
| --- | --- | --- |
|Normal critical|53 PASS;20 intended mutations killed|Собственный precheck для Context7 retirement подтверждён. У18 mutations named guards;2 сохранённых legacy targets без named guard.|
|Literal historical/compact|Оба baseline и51 парных mutations PASS|Это отдельное сравнение; его records не прибавляются к normal53/20.|
|Recovery baseline|11 PASS /1 FAIL /0 ERROR|Отказ closed_literal_context: recovery_explain_literal_source_fact.|
|Recovery mutations|Baseline rejected; mutants не исполнены|23 intended kills пока НЕ подтверждены.|
|Advanced pytest|528 PASS /94 FAIL|Не полный PASS.|
|P1.4|12/14; discovery8/10; required full facts5/5|Count-context исправление фактически помогло.|
|P1.5|5/7; verified full facts4/6|Два прежних case IDs остаются FAIL; library fact теперь виден.|
|P1.6 public delivery|6/6; full fact1/1|Собственный public gate PASS; workflow всё ещё падает на adversarial.|
|Legacy/V2/Agent Developer/adversarial|FAIL|Пороги и source obligations сохраняются.|

P1.4 oracle5/5, P1.5 oracle6/6 и P1.6 oracle6/6 — PASS.
Closure по-прежнему имеет четыре failing gates:
p14_quality, p15_quality, adversarial, adversarial_mutation;
его четыре собственных controls PASS.

Остались P1.4: `alias_order_drafts`, `alias_project_retry_rule`.
P1.5: `document_statement_binds_exact_path`,
`two_claims_require_two_allowed_roles`.

### Что фактически известно о P1.5 mixed loss

В mixed Explain-запросе native project reader допускает полный факт
ARCHITECTURE.md как literal context без original-query credit.
Project delivery=True; Unified получает project+library sources.
Финальный docs_answer содержит только библиотечный источник.
Первое доказанное исчезновение проектного факта — переход к final MCP projection.

Library-only canonical selection и library requirements действуют на объединённый
пакет. Исправление готовится через producer-owned resolved request_scope и
композицию уже проверенного project context внутри project_docs_answer.
Существующие global delivery/consent/conflict и library exact-version gates
сохраняются. Project source должен пройти собственные current scope/hash/raw checks.
Ни patch, ни новый успешный runtime этого изменения пока не заявлены.

## Reviewed slices90–94: следующий совместный прогон

| Slice | Commit | Изменение |
| --- | --- | --- |
|90|`c0f54f43a2df4ea872ba3fcd0ac09fe2242c4706`|Три projection fixtures по текущему query contract и пять opt-in read fixtures с конечным catalog/member transaction. Все восемь существующих имён, source facts и проверяемые guards сохранены.|
|91|`f4ad1374f1210fc71e79d3a8a8c435b5d1bbadf4`|Три focused V2 records из уже вычисленного report; полные reports/gold/пороги/exit неизменны.|
|92|`c3b464aa19c2ec36560fef4adb06f06eccf8063e`|Полный фактический receipt f7, включая failing recovery и незапущенные mutations.|
|93|`ece6555be1e68c323c4b09181faf00238d8922a5`|Report-only RECOVERY_FAILURE: exact positive/read index и source/projection hashes из уже имеющегося failed capture.|
|94|`820533361152ff3a143d2cf97d0c22a889486d75`|Удалены только1 Context7 функция/21 obsolete topic-alias case после собственного53/20 proof;18 функций/36 других случаев остаются.|

Все source slices прошли independent review и root review.
Exact Git parent/tree/file/blob verification выполнена; режима100755 у runners
не потеряно. Все записи о post-change runtime остаются PENDING.

Context7: 21 исходный вопрос и historical intent IDs сохранены в exact archive,
один current control проверяет прежние3+эти21 input. Удалённые FAIL не становятся PASS.
Меняется один diagnostic roster hash; imports/helpers/прочие36 cases/70 query-plan
cases/current control/critical runner остаются. Контракты collection требуют
следующего фактического прогона на опубликованном SHA.

Подробности:
[Projection fixtures](pr211-execution/PROJECTION_BOUNDARY_FIXTURE_CONTRACT_RU.md),
[Five read fixtures](PR211_DOCS_SERVICE_READ_FIXTURES_RU.md),
[V2 diagnostics](pr211-execution/V2_SAME_CALL_FOCUSED_DIAGNOSTICS_RU.md),
[Explain failure diagnostics](PR211_EXPLAIN_RECOVERY_FAILURE_OBSERVATION_RU.md),
[Context7 retirement](pr211-execution/CONTEXT7_ALIAS_INPUT_RETIREMENT_RU.md).

## Следующие конкретные действия

1. Совместный CI следующего SHA: проверить collection после retirement,
   восемь migration cases, critical53/20 и фактический RECOVERY_FAILURE.
2. По capture установить конкретный failing Explain positive и первый этап потери;
   сохранить full-fact oracle и все23 intended mutants.
3. Закончить structural filename contract с независимыми non-P15 controls:
   полный naming roster до evidence_path, однозначное целое filename label,
   unresolved target без выдуманной semantic role. Production drafts прошли
   static review; controls и runtime ещё не завершены.
4. Закончить mixed final projection: producer-owned resolved scope, independent
   current request binding, project raw snapshot, atomic validation всего результата.
   Проверить real same-call source delivery и направленные scope/hash/consent mutations.
5. По трём actual V2 stage records адресно исправить cache/reset, architecture,
   request-flow quality. Исходные вопросы и frozen witness facts сохраняются.
   Отдельно выяснить точный смысл Legacy original-query coverage0 при floor12.
6. Продолжать остальные failing families узкими contract slices с честным разделением
   fixture migration, retirement и исправления продукта. Ни1680 FAIL, ни94 advanced
   FAIL не объявлены устаревшими целиком.
7. После этого — полный required CI/downstream и необходимые installed/client
   проверки на одном конечном опубликованном SHA. Merge пока не выполнять.

## Продолжение работы

Оба authorized refs: `implementation/pr211-merge-readiness` и
`integration/stage3-v2-identity-pr1`; обновлять только fast-forward с expected SHA.
Root один создаёт commits/обновляет refs; агенты готовят blobs и independent reviews.
При потере временного состояния читать этот checkpoint и точный Git HEAD,
не возвращаться к старому основному checkout и не повторять завершённую работу.

# PR #211: checkpoint продолжения

Обновлено: 2026-10-10 02:28 UTC.

**PR пока не готов к merge.** Последний завершённый фактический CI:
PR HEAD `321f36577577cb90a0422cee0de0b525b9cd658e`,
merge checkout `217d21017008240cf252e6b99e5c6e810a858a2a`,
общий tree `9ea02d6b3dd7912b46000dc8174939ec0981e5d8`.

После него подготовлен reviewed пакет 108–112. Его совместный runtime **PENDING**.
Ни исправление source carrier, ни добавление diagnostic reader ещё не означают PASS.

## Действующие решения

- Потолки **6144 bytes / 800 tokens / 3 sources** отменены. Измеряем и сокращаем
  полный полезный output с сохранением фактов, source identity, scope/version/hash и consent.
- Операционные input/read/work/call/time ограничения остаются.
- Retrieval включён в утверждённый план; прежний blanket deferral снят.
- Retirement — после независимого oracle, собственного зелёного baseline,
  intended mutation proof и сохранности helpers/imports/selectors/archive.
- Legacy acceptance применяет принятый ADR 0003: полный frozen fact coverage
  исходных cases с floor **12/15**. Raw original-query coverage остаётся отдельной
  метрикой без lookup/parent credit. Изменение метрики явно версионировано.
- Реальные Claude Code/Codex/OpenCode sessions **NOT RUN**. Installed SDK/stdio
  подтверждает CI transport, но не эти клиентские sessions.
- Локальные runtime/import/pytest/AST/install не выполняются. Проверки идут
  в существующих авторизованных PR workflows, без новых providers/models.
- Обычные commits и fast-forward двух refs разрешены. Merge/release, force-push
  и внешние comments/messages не выполняются.

План: [PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md).
Решения: [CURRENT_WAVE_DECISIONS_RU.md](CURRENT_WAVE_DECISIONS_RU.md).
Старый local checkout не является актуальной базой.

## Фактический CI: 107

[Main run 38014539455](https://github.com/Vanilla1999/DocAtlas/actions/runs/38014539455).
[P1-stack 38014539441](https://github.com/Vanilla1999/DocAtlas/actions/runs/38014539441).
[JUnit reader 114103727373](https://github.com/Vanilla1999/DocAtlas/actions/runs/38014539455/job/114103727373).
[Полный runtime receipt107](pr211-execution/RUNTIME_EVIDENCE_321f3657.json).
[Downstream receipt107](pr211-execution/PR211_107_DOWNSTREAM_RECEIPT.json).

На **каждом** Python 3.11/3.12/3.13:
**7727 = 6024 PASS / 1693 FAIL / 0 ERROR / 10 SKIP**.
Integrity issues пусты, 279 reader records разобраны без ошибок, omitted_rows=0.
Матрица не суммируется в один baseline.

| Python | SHA256 JUnit |
| --- | --- |
|3.11|`d1e748582f38dfb857c333e2958354cf4208f965bcee69c9748cf8ea47716c61`|
|3.12|`48715a50a83576a10e40dfad78c82e06a72ecdc98fe5067836217f782921f89f`|
|3.13|`1ac2185fc2322e032258344ad84d86b63867da738ff3401d57e2c92dcf2513c5`|

Сравнение с предыдущим полным 95: **6063P/1653F → 6024P/1693F**,
коллекция +1. В пакете 96–107 тесты не удалялись.

| Изменившееся семейство | Actual107 | Что доказано |
| --- | --- | --- |
|Projection boundaries|17P/3F вместо16P/4F|Один прежний failure устранён; три V2-позитива остаются.|
|Новый mixed contract|1F|После успешной scope-producer проверки public packet содержит только library source.|
|V2 protocol|48P/2F|Оба focused traces падают на optional observer `app.service`.|
|Release gate|14P/38F|Первая причина — тот же observer setup; 38 cases используют общий минимальный fixture. Полные38 traces reader не публикует.|

Legacy acceptance controls **5/5 PASS** на всех трёх Python lanes.
Это не означает, что live Legacy report достиг 12/15 или прошёл downstream.

## Downstream107

| Gate | Наблюдение | Ограничение |
| --- | --- | --- |
|P1.4|12/14; discovery8/10; полные факты5/5; oracle5/5|`alias_order_drafts` и `alias_project_retry_rule` FAIL.|
|P1.5|**6/7**, полные факты5/6; oracle6/6|Filename-reference case теперь PASS; остался mixed source case.|
|P1.6 current delivery|6/6; oracle6/6|Retained adversarial24/28 и его mutation gate остаются FAIL.|
|Current closure|Integrity всех трёх current reports подтверждена; controls4/4|Quality и required outcomes FAIL.|
|Installed MCP|1/1; verifier PASS; controls7/7|Reviewed wheel + scripted planner + настоящий stdio; actual clients NOT RUN.|
|Retrieval evidence|SUCCESS; 31 sufficient в прежней группе48, operational/integrity errors0|Пять causal cells дают31; bounded pool/holdout не показали улучшения.|
|Required CI / P1-stack exact|FAIL|Core и advanced FAIL; platform/build/wheel/sdist успешны.|

P1.5: project return содержит **ARCHITECTURE.md, 37 символов**, а Unified
сохраняет его вместе с exact Tenacity 8.2.3 source, **65 символов**.
Обе стадии разрешают delivery. Финальный public/snapshot packet содержит
только библиотеку. В actual library snapshot class находится в metadata.
Новый независимый mixed fixture воспроизводит тот же loss на других исходных
вопросе, фактах и finite sources.

Main advanced завершён с FAIL. Полный job log трижды вернул `Transport closed`;
повторы прекращены. Quality artifact существует, но его ZIP-содержимое
в этом receipt не прочитано. Поэтому **текущие counts/kills recovery и critical,
а также полные Legacy/V2 результаты NOT OBSERVED**. Их нельзя подменять95.
Отдельный P1-stack advanced сообщает528P/94F; это не измерение main advanced.

Последние успешно прочитанные normal critical результаты относятся к95:
53P/20 intended kills. Отдельный literal comparison95: baselines702/82 и51
парная mutation. Recovery95:11P/1F; baseline отвергнут, mutations не запускались.
[Receipt95](pr211-execution/RUNTIME_EVIDENCE_eb2c4f3b.json) сохраняет историю.

## Reviewed пакет после107: runtime pending

| Slice | Commit | Изменение |
| --- | --- | --- |
|108|`016070138835bf908d83cfe6e6e98420025e4778`|DQP3 precheck: независимые explicit lookup slots и два directed mutants, без retirement.|
|109|`24423beb1c4d4822b3f578586040a7064c36dba5`|Optional observer capabilities: отсутствие внутренних facade methods не ломает основной read/observer contract.|
|110|`8bd34947893fecb02b841ca0c3ad16b374c8a646`|Mixed class carrier: верхнее поле или metadata, все присутствующие значения согласованы; guards сохраняются.|
|111|`17e0b573aeda133671e211cf5f2abd8ae3464ec2`|Полные actual107 runtime/downstream receipts.|
|112|`dbd957356d14dbd081fd5ad89e1c4999fa23291f`|Чтение уже созданных quality/recovery/critical artifacts в существующем CI diagnostic job; без нового выполнения сценариев.|

### DQP3

Все70 старых expanded cases из29 definitions остаются.
Три выбранных input-contract nodes имеют exact archive и независимые expected
rows внутри существующего alias contract control. Проверяются original question,
порядок/повторы lookup slots, независимые public IDs, пятый слот и отсутствие
скрытых semantic aliases/parent credit. Новых test functions нет.
После собственного healthy baseline и двух intended kills можно отдельно
рассматривать удаление ровно этих3 nodes; остальные67 не объявлены устаревшими.

[Crosswalk и review](pr211-execution/EXPLICIT_LOOKUP_SLOT_PRECHECK_RU.md).

### Optional observer

Диагностика оборачивает только существующие callable project/member methods.
При отсутствии используется stdlib nullcontext; fake stages и extra reads
не создаются. Обязательные unified/selection/validation/coverage observers,
один actual dispatch, snapshot checks, counters и cleanup сохранены.
Ожидается фактическое восстановление2+38 controls, а не их ослабление.

[Review](pr211-execution/OPTIONAL_DELIVERY_OBSERVER_CAPABILITIES_RU.md).

### Mixed carrier

Producer явно хранит library class/scope в metadata canonical candidate.
Helper теперь требует exact literal class из объявленных carriers и их согласия;
None, конфликт, отсутствие обоих и malformed metadata запрещают project addition.
Raw source/hash/version и current project/root/module/consent guards не меняются.

В том же independent test исправлены два предположения о расположении class/scope;
literal expected values и full-body/SQL/hash/span checks сохраняются.
Прежние4 native calls,28 request/source replays и collision control остаются;
добавлено15 detached carrier iterations. Это дополнительная работа внутри function,
а не сокращение числа исполнений.

[Review](PR211_MIXED_LIBRARY_CLASS_CARRIER_RU.md).

### Artifact diagnostics

Existing diagnostic job читает уже загруженные artifacts текущего run,
стандартной библиотекой Python, без импорта production/evaluator и без rerun.
Shared V2 focused serializer переносится без изменения acceptance wrapper.
Сохраняются source report hashes, provenance, missing/unreadable records,
независимость reader status от gate acceptance и original complete artifacts.
Console transport ограничен отдельно от product output; сокращённые записи
не объявляются полным evidence.

## Следующие конкретные действия

1. Опубликовать пакет обычным fast-forward обеих refs, проверить actual merge
   parents/tree и собрать полный совместный CI на этом SHA.
2. Проверить восстановление observer cases, mixed positive/negative/full-fact
   controls, P1.5 и **critical54/27**. Recovery target **12/33** остаётся pending.
3. Через новый artifact reader получить actual recovery failure/summary,
   Legacy source-fact report и три V2 focused delivery observations.
   Сначала исправлять первый доказанный operand, сохраняя исходные задачи/guards.
4. Закрыть2 P1.4 discovery failures и4 retained adversarial failures по действующему
   контракту. Имя alias или old tiny_budget само по себе не основание retirement.
5. После своего proof выполнить narrow DQP3 retirement; затем продолжить audit
   остальных семейств с сохранением исходных примеров и независимых successor controls.
6. Закрыть все required CI/P1/downstream на конечном SHA и необходимые installed/client
   проверки. SDK/stdio не заменяет реальные клиентские sessions. Merge не выполнять.

## Как продолжать без потери состояния

Оба authorized refs: `implementation/pr211-merge-readiness` и
`integration/stage3-v2-identity-pr1`; обновлять fast-forward с expected SHA.
Root создаёт commits и refs, агенты готовят blobs и независимые reviews.
Читать точный Git HEAD и этот checkpoint, не возвращаться к старому checkout.
Продолжать конкретное выполнение, давать короткие updates не реже минуты;
не завершать работу ещё одним предложением продолжить.

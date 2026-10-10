# PR #211: checkpoint продолжения

Обновлено: 2026-10-10 03:00 UTC.

**PR пока не готов к merge.** Последний завершённый фактический CI:
PR HEAD `441cdefd2b251d63f716bfa75b053413bbe09c76` (113),
merge checkout `ceea2571e9847a71515feda4e1e1441fafdede44`,
общий tree `f0ad2af2fed811e884cc3d9887d7fb9ecd2812df`.
Пакет reviewed corrections 114–117 описан ниже; его совместный runtime **PENDING**.

## Действующие решения

- Потолки **6144 bytes / 800 tokens / 3 sources** отменены. Измеряем и сокращаем
  полный полезный output с сохранением фактов, source identity, scope/version/hash и consent.
- Операционные input/read/work/call/time ограничения остаются.
- Retrieval включён в утверждённый план; прежний blanket deferral снят.
- Retirement — после независимого oracle, собственного зелёного baseline,
  intended mutation proof и сохранности helpers/imports/selectors/archive.
- Legacy acceptance применяет ADR 0003: полный frozen fact coverage исходных
  cases с floor **12/15**. Raw original-query coverage — отдельная метрика
  без lookup/parent credit. Миграция метрики явно версионирована.
- Реальные Claude Code/Codex/OpenCode sessions **NOT RUN**. Installed SDK/stdio
  подтверждает CI transport, но не эти клиентские sessions.
- Локальные runtime/import/pytest/AST/install не выполняются. Проверки идут
  в существующих авторизованных PR workflows, без новых providers/models.
- Обычные commits и fast-forward двух refs разрешены. Merge/release, force-push
  и внешние comments/messages не выполняются.

План: [PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md).
Решения: [CURRENT_WAVE_DECISIONS_RU.md](CURRENT_WAVE_DECISIONS_RU.md).
Старый local checkout не является актуальной базой.

## Фактический CI: 113

[Main run](https://github.com/Vanilla1999/DocAtlas/actions/runs/38017123447).
[P1-stack](https://github.com/Vanilla1999/DocAtlas/actions/runs/38017123530).
[Acceptance reader](https://github.com/Vanilla1999/DocAtlas/actions/runs/38017123447/job/114111640263).
[Runtime receipt113](pr211-execution/RUNTIME_EVIDENCE_441cdefd.json).

На **каждом** Python 3.11/3.12/3.13:
**7727 = 6064 PASS / 1653 FAIL / 0 ERROR / 10 SKIP**.
Матрица не суммируется в один baseline. Все три JUnit integrity issues пусты.
Reader log: 569005 UTF-8 bytes,
SHA-256 `ad44754505bf41a660a8312924380d8989915f6cf776a0579ae84f45edbf0f59`.
Разобраны305 JSON records без ошибок; JUnit console omitted=0.
В artifact console **29 selected / 28 printed / 1 omitted**; это отдельная
диагностическая граница, не product output ceiling.

| Python | SHA-256 JUnit |
| --- | --- |
|3.11|`26f720a578072519a04ed2ec4f8895f23b9893d13b306fd82fdddeffb7784309`|
|3.12|`58de0178504e2278e4771ace9a8659cdf096429b6197e464be8e1a600127f9d4`|
|3.13|`35928f7dd6aca9d4e521d1fe4c799eec0b4e1d7f5496037f9f4666400790c2de`|

С 107 исправлены **40 observer failures**:2 V2 protocol +38 release controls.
Collection не менялась, старые тесты в пакете108–113 не удалялись.
Новый mixed control теперь проходит4 native reads и28 request/source replays,
после чего падает на первом detached class control `metadata_only`.
Trace показывает `critical_mixed_class_control_healthy`; конкретный
estimate mismatch установлен по исходникам, не напечатан как runtime operand.

| Gate | Actual113 | Что остаётся |
| --- | --- | --- |
|Critical|53P/1F из54|Healthy baseline отклонён; intended kills не засчитываются.|
|Recovery|11P/1F/0E|Единственный guard: `recovery_filename_withheld_real_candidates`; mutations blocked.|
|P1.4|12/14; discovery8/10; facts5/5; oracle5/5|Два original-only discovery failures.|
|P1.5|**7/7; facts6/6; oracle6/6**|Current provenance PASS; raw carrier snapshots этого run отдельно не прочитаны.|
|P1.6 current|6/6; facts1/1; oracle6/6|Retained adversarial24/28 и mutation baseline FAIL.|
|Legacy live|Source-fact acceptance **8/15**, raw original coverage0|Floor12/15 не достигнут; report FAIL.|
|V2 live|Natural facts6/15; paraphrase facts1/5|Report сформирован, REPORT_ONLY; production runner FAIL.|
|Current closure|Reports integrity PASS; oracle4/4|Current quality и required outcomes FAIL.|
|Main installed MCP / retrieval evidence|SUCCESS|Это job status; actual client sessions NOT RUN.|
|Required CI / P1-stack exact|FAIL|Core и advanced красные; platform/build/wheel/sdist успешны.|

Hermetic quality16/16 проверяет literal query identity без выполнения retrieval;
не подменяет live acceptance. Legacy raw report8/16 и positive7/15 отличаются
от отдельного принятого full-source-fact oracle8/15.

В V2 cache-reset и architecture получены20 member windows; project/unified
сохранили соответственно3 и1. Оба stages сообщают delivery eligible.
У unified `required_evidence_missing` относится к answer support и само по себе
не доказывает delivery veto. Полный request-flow record не получен из доступного
console113: reader пропустил ровно эту запись. Новый reader117 отдаёт приоритет
компактным operands всех трёх case IDs.

## Reviewed пакет после113: runtime pending

| Slice | Commit | Изменение |
| --- | --- | --- |
|114|`b25405a7252d029419396d35ed19c55f3a6e944e`|Detached mixed carrier валидируется после пересчёта estimate, как в production helper.|
|115|`d4c15e22e6bdd82d80caef268d8085c9b8745386`|Filename fixture допускает законную title/body dedup; обязательный one-source/full-catalog ambiguity probe сохранён.|
|116|`5ee5e850bee9eac717a5e517225a7d4ecda127eb`|DQP30 precheck:2 representative records,2 intended mutants; без удаления старых cases.|
|117|`207457e339d88dc5c91a5620d1ca93a046b2d2cc`|Приоритетные body-free V2 delivery operands; полные records/artifacts сохраняются.|

Каждый code slice имеет root и независимое peer review.
Ни один статический APPROVE не объявляет новый runtime PASS.

### Mixed и recovery

[Mixed estimate review](PR211_MIXED_CARRIER_ESTIMATE_FIXTURE_RU.md):
same-call capture происходит до финального estimate refresh. Helper валидирует
обновлённую копию, новый detached control теперь делает тот же refresh.
Остальные identity/class/hash/spans/current-generation/authority guards сохранены.

[Recovery filename review](PR211_FILENAME_SINGLE_CANDIDATE_FIXTURE_RU.md):
два catalog members имеют одинаковые title/body, acquisition вправе убрать дубль.
Исправленный observer удерживает один фактически полученный member.
Независимый обязательный probe по-прежнему имеет selected source1,
full naming inventory2 и ambiguous IDs2. При отсутствии native acquisition
`single_candidate_observed=false` не выдаётся за наблюдённый delivery.
Вопросы, bodies, public safety и33 directed mutants сохранены.

### DQP3 + DQP30

Все **29 definitions / 70 expanded cases** старого DQP module пока collected;
actual113:25P/45F. DQP3 precheck опубликован108, DQP30 —116.
Две новые compiler задачи проверяются3 plan calls +2 alias calls, без30-row replay.
Уже существующие guards идут раньше новых; executor и прежние27 mutants сохранены.
Следующий собственный target: **54 baseline PASS /29 intended kills**.

После этого proof допускается точный retirement **33 cases /13 definitions**:
DQP3 nodes3 + compiler positives30. В DQP остаются16 definitions /37 cases,
включая5 точных отрицательных rows выбранной compiler family.
Все остальные bodies/imports/helpers/labels/archive сохраняются.
Условные removal blobs подготовлены отдельно, но до proof не применяются.

[DQP3 crosswalk](pr211-execution/EXPLICIT_LOOKUP_SLOT_PRECHECK_RU.md).
[DQP30 crosswalk/review](pr211-execution/DQP_COMPILER_CONTRACT_PRECHECK_RU.md).

### Открытые product/contract причины

[P1.4 source audit](pr211-execution/P14_ORIGINAL_ONLY_DISCOVERY_AUDIT_107_RU.md)
фиксирует исходные вопросы и bodies двух failing cases.113 сохраняет те же
first causes: literal overlap находится, original qualification не допускает
контекст; host lookups отсутствуют. Не менять исходные вопросы, не добавлять
скрытые aliases, не отключать discovery и не подбирать порог по этим двум строкам.

V2 расследуется по same-call operands: ordinary project context обрезает
набор найденных окон, тогда как patch retention использует отдельный carrier.
Это source-backed направление анализа; product fix ещё не принят.
Четыре retained adversarial failures также остаются открытыми.

Relation witnesses/safety audit различает obsolete generated-need expectations
и живые source/body/condition/scope guards.49F/23P и18F/8P не означают,
что все failing cases можно удалить.

## Следующие конкретные действия

1. Опубликовать пакет114–117 и этот checkpoint обычным fast-forward обеих refs,
   проверить actual merge parents/tree и получить совместный CI.
2. Проверить mixed healthy baseline и **critical54/29**; recovery **12/33**.
   Сохранить actual first failing guard, если любой baseline всё ещё красный.
3. Прочитать все3 новых `V2_DELIVERY_OPERANDS`, найти первый доказанный loss/veto
   и исправить его с сохранением исходных задач, полезных source facts и guards.
4. При собственном DQP proof применить exact33-case retirement, owning label hash
   и runtime receipts crosswalk; отдельно продолжить audit оставшихся семейств.
5. Закрыть P1.4, Legacy/V2 и retained adversarial по действующему контракту.
6. На конечном SHA закрыть required CI/P1/downstream и необходимые installed/client
   проверки. SDK/stdio не заменяет реальные client sessions. Merge не выполнять.

## Как продолжать без потери состояния

Оба authorized refs: `implementation/pr211-merge-readiness` и
`integration/stage3-v2-identity-pr1`; обновлять fast-forward с expected SHA.
Root создаёт commits и refs, агенты готовят blobs и независимые reviews.
Читать точный Git HEAD и этот checkpoint, не возвращаться к старому checkout.
Продолжать конкретное выполнение, давать короткие updates не реже минуты;
не завершать работу ещё одним предложением продолжить.

История: [receipt107](pr211-execution/RUNTIME_EVIDENCE_321f3657.json),
[downstream107](pr211-execution/PR211_107_DOWNSTREAM_RECEIPT.json),
[receipt95](pr211-execution/RUNTIME_EVIDENCE_eb2c4f3b.json).

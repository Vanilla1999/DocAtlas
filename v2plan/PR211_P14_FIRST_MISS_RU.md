# PR #211: P1.4 после read-only accessor

## Фактический CI на 067dd560

SHA: `067dd56044fb1fe292af2d17783154c8a4b7c092`.
[Run 37991321105 / job 114025928063](https://github.com/Vanilla1999/DocAtlas/actions/runs/37991321105/job/114025928063).

- Cases: **7/14 PASS**, discovery **3/10**, complete fact **2/5**, runtime errors **0**.
- Во всех 14 сценариях проходит frozen `read_only` check: семь полностью passed;
  у каждого из остальных семи в логе `state_equal=true`, `differences=[]`,
  а failed checks содержат только required discovery / complete fact.
- Independent oracle self-tests **5/5 PASS**; syntax/format **PASS**.
- Полный report сохранён CI в artifact `11644234956`,
  ZIP SHA256 `2de3d3a016ee5731ac6638d709bc99d961dbdf2dc6f42f0357d1738362bf3319`.
  Binary archive здесь не распаковывался. Вывод выше основан на проверенных логах
  и неизменном scorer; это не утверждение о просмотре каждого поля архива.

Readonly defect устранён в реальном P1.4 runtime. Это не PASS остальных core tests,
retrieval quality или downstream acceptance.

## Первый оставшийся miss

Frozen case: `behavior_orders_store`.

- Original question: `What does OrdersDraftStore do?`
- Единственный authored member: `packages/orders/README.md`.
- Полный authored факт: `OrdersDraftStore stores draft orders as JSON records keyed by order id before upload.`
- Фактический результат CI: нет видимого source; failed checks —
  `required_discovery,required_complete_fact`; source/authority errors пусты.

По текущим исходникам есть конкретная проверяемая причина потери при qualification:
prepared reference path сохраняет все literal query terms
`what, does, ordersdraftstore, do`. В authored body совпадает только identifier;
для этого пути нет hard exact terms, поэтому отношение 1/4 не достигает 0.5.
BareCamelCase reference намеренно остаётся unresolved; текущий fallback принимает
только explicit symbol identity с проверенным body/source binding.

Это source-level inference, пока фактические per-stage наблюдения не выведены из
сохранённого report. Строгий fallback нельзя расширять на любой CamelCase без
контрпримеров: одно имя не покрывает дополнительные отсутствующие условия вопроса.

## Следующий узкий шаг

Runner выводит уже сохранённые `pipeline_diagnostics`, реальные `service_requests`
и finite preparation roster у failed cases. Короткая строка `READ_STATE` для всех
14 cases показывает сам frozen check, equality и названия изменившихся полей.
Ни retrieval, ни fixture, ни scorer, ни исходные вопросы, ни report schema/verdict
не меняются; дополнительных обращений к движку нет.

После следующего обычного CI это отличит отсутствие кандидатов от отказа qualifier
или operational delivery veto. Затем исправляется подтверждённая стадия с
контрпримером для ложного entity-only совпадения. Aliases, переписывание gold,
inferred roles и перенос snapshot не являются исправлением.

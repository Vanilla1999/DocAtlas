# PR #211: checkpoint продолжения

Обновлено: 2026-10-10 01:47 UTC.

**PR пока не готов к merge.** Последний полностью завершённый фактический CI:
PR HEAD `eb2c4f3b3e0065110a1bfe2c855e4a05803fa37a`,
tree `6d75a3b5f019e94c11810364a7214b442b5829fa`.

Следующий reviewed пакет сохранён до
`b1c6586a2f1b25dccf0b0a56232e91c02a4fa8f6` (slices96–106).
Его совместный runtime **PENDING**. Новые целевые числа не считаются PASS.

## Действующие решения

- Потолки **6144 bytes / 800 tokens / 3 sources** отменены. Измеряем и сокращаем
  объём с сохранением полных полезных фактов, source identity, scope/version/hash и consent.
- Операционные input/read/work/call/time ограничения остаются.
- Retrieval включён в позднее утверждённый план; прежний blanket deferral снят.
- Retirement — после независимого oracle, собственного зелёного baseline,
  intended mutation proof и сохранности helpers/imports/selectors/archive.
- Legacy acceptance явно мигрирует по принятому ADR 0003: полный frozen fact
  coverage исходных cases с floor **12/15**. Raw original-query coverage остаётся
  отдельной метрикой без lookup/parent credit. Это смена проверяемого контракта;
  отмена output-cost ceilings не отменяет quality floor.
- Реальные Claude Code/Codex/OpenCode sessions **NOT RUN**. Installed SDK/stdio
  подтверждает CI transport, но не эти клиентские sessions.
- Локальные runtime/import/pytest/AST/install не выполняются. Проверки идут в
  существующих авторизованных PR workflows. Новые providers/models не подключаются.
- Обычные commits и fast-forward двух refs разрешены. Merge/release, force-push
  и внешние comments/messages не выполняются.

План: [PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md).
Решения: [CURRENT_WAVE_DECISIONS_RU.md](CURRENT_WAVE_DECISIONS_RU.md).
Старый local checkout не является актуальной базой.

## Полный фактический CI: eb2c4f3b (95)

Actual merge checkout: `abc3819438a1e2fea452a750f99e01edb3a41438`.
Проверены родители: main `d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c`
и PR head95. Checkout tree совпадает с PR tree.
Main и P1-stack metadata указывают этот PR HEAD.

[Main run38010627863](https://github.com/Vanilla1999/DocAtlas/actions/runs/38010627863).
[P1-stack38010627919](https://github.com/Vanilla1999/DocAtlas/actions/runs/38010627919).
[JUnit reader114091874403](https://github.com/Vanilla1999/DocAtlas/actions/runs/38010627863/job/114091874403).
[Полный receipt95](pr211-execution/RUNTIME_EVIDENCE_eb2c4f3b.json).
[Отдельный downstream receipt95](pr211-execution/PR211_95_DOWNSTREAM_RECEIPT.json).

На **каждом** Python3.11/3.12/3.13:
**7726 = 6063 PASS / 1653 FAIL / 0 ERROR / 10 SKIP**.
Integrity issues пусты; omitted_rows=0. Матрица не суммируется в один baseline.

| Python | SHA256 JUnit |
| --- | --- |
|3.11|`3502ad3ae96a45d9dd809784332983a3245e3eb28ad37559f7186333035c4a8b`|
|3.12|`1810198a915152fed0fd1e57b4ffbe59bd770571c1ac7299c1f36d03139a6cff`|
|3.13|`9d8e715c7467bd07038daa78048383da8f5f2720221006f66cccb60fe587739b`|

Root сопоставил все215 module records с f7. Counts изменились только у трёх:
Context7 **12P/45F → 12P/24F** (21 reviewed retirement),
projection boundaries **14P/6F → 16P/4F**,
docs_service_part03 **6P/18F → 10P/14F**.
Это сравнение module counts. Оно не доказывает PASS каждого из пяти migrated
read fixtures: следующий JUnit reader выводит их отдельные nodes.

Context7: 36 остальных cases собраны; 21 retired input сохранён в exact archive
и проверяется current control вместе с прежними тремя входами.
Удалённые FAIL не объявляются новыми PASS.
Прежняя карта и её история:
[CORE_FAILURE_MAP_80c8fbbb.jsonl](pr211-execution/CORE_FAILURE_MAP_80c8fbbb.jsonl).
Оставшиеся1653 FAIL не объявлены все устаревшими.

Docs-contract, docs-impact, static-contract, retrieval-evidence, installer,
installed MCP и три platform smoke jobs SUCCESS. Core/advanced/required-ci FAIL.
P1-stack FAIL; platform/build/wheel3.11–3.13/sdist/installer SUCCESS.

## Critical, recovery и downstream: фактические результаты95

[Advanced114089537662](https://github.com/Vanilla1999/DocAtlas/actions/runs/38010627863/job/114089537662).

| Gate | Фактический результат95 | Ограничение вывода |
| --- | --- | --- |
|Normal critical|53 PASS;20 intended mutations killed|18 named guards и2 сохранённых legacy targets.|
|Literal historical/compact|Baseline702/82 и51 парная mutation PASS|Отдельный comparison; не прибавляется к normal53/20.|
|Recovery baseline|11 PASS /1 FAIL /0 ERROR|Closed literal positive13/read52 не дошёл до projection.|
|Recovery mutations|Baseline rejected|23 mutants не исполнялись; kills не заявлены.|
|Advanced pytest|528 PASS /94 FAIL|Обязательный набор остаётся красным.|
|Question surface|100 исходных входов и positive/absent-fact/source-removal controls PASS|Нет права объявить остальные quality gates PASS.|
|P1.4|12/14; discovery8/10; полные факты5/5; oracle5/5|Два alias cases FAIL.|
|P1.5|5/7; полные факты4/6; oracle6/6|Два source-role cases FAIL.|
|P1.6 current public delivery|6/6; полный факт1/1; oracle6/6|Workflow FAIL из-за retained adversarial24/28.|
|Legacy/V2/Agent Developer/adversarial|FAIL|Новый Legacy oracle ещё не проверен runtime.|
|Installed CI|1/1; controls7/7; реальный stdio|Actual пользовательские clients NOT RUN.|

Closure имеет четыре failing gates:
p14_quality, p15_quality, adversarial, adversarial_mutation.
Его собственные controls4/4 PASS. P1 downstream steps после advanced skipped;
отсутствующие proof inputs сохраняют FAIL. Retrieval gate SUCCESS, но измерения
стоимости и сохранённые frozen groups не доказывают новый прирост recall.

Остались P1.4: `alias_order_drafts`, `alias_project_retry_rule`.
P1.5: `document_statement_binds_exact_path`,
`two_claims_require_two_allowed_roles`.

## Reviewed пакет96–106: совместный runtime PENDING

| Slice | Commit | Изменение |
| --- | --- | --- |
|96|`3064eb635058af44609ee35181c39154da7d3224`|Producer-owned request_scope и project lane contract для mixed; поля добавлены в конец dataclass.|
|97|`85224cda69355c1a9bd64c148e45452955bc86ae`|Whole filename label из полного allowed catalog до evidence_path; independent scope/collision/body controls и8 mutations.|
|98|`cf973994c0085a991f59d5e20542aeb1b119666a`|Кавычки для всех литеральных FTS operands в primary/fallback; AND/OR/NOT не становятся операторами запроса.|
|99|`3a96a5c0d8a7787023beaf2d0a34cbf9668f98a6`|Negative projection fixture допускает корректный early veto; исходные вопросы/факты/guards сохранены.|
|100|`3b9b155b734778bcca91af9796174d469be409c0`|Pure mixed composition внутри authoritative project_docs_answer; current request/root/module и обе source lanes независимо валидируются.|
|101|`42a481c66dde69d7f3103cd10bfb50c2dd7035c4`|Существующий JUnit reader выводит текущие focused nodes, без нового запуска или изменения exit policy.|
|102|`fe1f3d75bf89276fa355425e152cbe4d73bfe38e`|Полные фактические runtime/downstream receipts95.|
|103|`91275e9f26ed3df3be9e8f747d6cc37e9835ebee`|Один independent mixed public contract test,4 real calls/28 replays/1 collision и5 targeted mutations.|
|104|`34913345f8f6f491fc707a9028c58d7d68319cd5`|Версионированный Legacy source-fact oracle с provenance/body/scope/span counterfactuals в прежних test functions.|
|105|`e7f33e6e121eee81364f2e0ee50cdacd34f7ca47`|Исправлен найденный review collection blocker: exact one-node diagnostic shard mixed-теста.|
|106|`b1c6586a2f1b25dccf0b0a56232e91c02a4fa8f6`|Body-free same-call eligibility observations на member/project/Unified returns; один printer field, без новых reads или изменения результата.|

Code slices прошли root и independent review; exact parent/tree/file/blob
verification выполнена, executable modes runners сохранены.
**Целевые critical54/25 и recovery12/33 PENDING**.
Исходные critical53/20 и recovery12 cases/23 mutants сохранены; новые mutants
получают credit только после собственного зелёного baseline и intended guard failure.

Mixed helper не выполняет новый retrieval/IO. Library contract и global
delivery/consent/conflict gates сохраняются, project source проходит собственный
current request/scope/raw hash check. Canonical absolute request root поддержан;
relative, tilde и symlink aliases пока сохраняют прежний library packet без нового
mixed-PASS claim. Source-root проверка не подменяется новым filesystem resolve.

Legacy: `verified_original_case_fact_count >=12/15` — явно новый versioned metric
по ADR0003; raw `original_query_covered_count` не переназывается и не получает lookup credit.
Исходные16 вопросов, lookups, gold, protocol lock, V2 settings и6 hard-zero gates
сохранены. Source fact в metadata-only heading/link/table header не принимается.
Owner выводится из captured host root, а не candidate source. Проверяются exact
current file spans и actual same-call snapshot. Сохранились5 acceptance definitions
и14 protocol definitions/21 expanded cases. Новые counterfactuals внутри прежнего
теста не объявлены production mutation kills.

Предыдущее полное Legacy fact coverage на f7: **8/15 <12/15**.
Это всё ещё FAIL. Старый report без новых persisted validator receipts не доказывает
работу нового oracle.

Подробности:
[Structural filename](PR211_STRUCTURAL_FILENAME_CONTEXT_RU.md),
[FTS operands](PR211_FTS_LITERAL_OPERANDS_RU.md),
[Early-veto fixture](PR211_EARLY_VETO_FIXTURE_RU.md),
[Mixed producer](PR211_MIXED_PROJECT_SCOPE_PRODUCER_RU.md),
[Mixed projection](PR211_MIXED_PROJECT_CONTEXT_PROJECTION_RU.md),
[Mixed control](PR211_MIXED_CONTEXT_CONTRACT_RU.md),
[Legacy oracle](pr211-execution/LEGACY_SOURCE_FACT_ACCEPTANCE_RU.md).

## Следующая проверяемая граница retrieval

Три actual V2 focused records95 сохранены в полном receipt.
Cache/reset отдаёт0/2 полных фактов; architecture3/4; request-flow0/4.
У cache/reset полезное intro window rejected по qualification; порог не снижен
под этот corpus. У architecture недостающий infrastructure witness не доказан.

У request-flow имеются qualified lookup windows, но MCP возвращает ранний
delivery veto до project_docs_context. `required_evidence_missing` — скопированная
support reason, она сама не доказывает, какой read eligibility operand был false.
Project-reader ranking мог уже исполняться: projection trace `not_reached`
не означает отсутствие всякого раннего ranking. Без этих operands менять
retention/ranker/gates или обещать найденную product-причину нельзя.

В106 сохранена [диагностика delivery operands](PR211_V2_DELIVERY_OPERANDS_RU.md).
Она читает только выбранные поля уже возвращённых объектов, включая реальные
identity/span metadata у RetrievedChunk, и явно отмечает unknown/omitted.
Новый runtime остаётся PENDING.

## Следующие конкретные действия

1. На совместном новом SHA проверить collection, отдельные migrated read nodes,
   mixed baseline/mutations54/25, recovery12/33 и существующие Legacy controls.
2. Получить actual P1.4/P1.5/adversarial, полный Legacy source-fact report и
   три V2 focused observations. Сначала устранить первый доказанный дефект.
3. Прочитать добавленные в106 body-free eligibility operands из тех же
   реальных calls и локализовать потерю member read → project context → Unified.
   Исходный вопрос, facts, read guards и честная original coverage сохраняются.
4. Продолжать narrow contract audits остальных семей, начиная с query-plan IDs,
   explicit lookup lineage и retired alias expectations. Сокращение только после
   независимого successor и фактического mutation proof.
5. Затем полный required CI/P1/downstream и необходимые installed/client checks
   на одном конечном опубликованном SHA. Merge пока не выполнять.

## Продолжение работы

Оба authorized refs: `implementation/pr211-merge-readiness` и
`integration/stage3-v2-identity-pr1`; обновлять fast-forward с expected SHA.
Root создаёт commits/обновляет refs, агенты готовят blobs и independent reviews.
При потере временного состояния читать этот checkpoint и точный Git HEAD;
не возвращаться к старому checkout и не повторять завершённые slices.

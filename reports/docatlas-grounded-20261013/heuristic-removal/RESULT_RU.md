# Итог: эксперимент остановлен, production не готов

2026-10-13. После общего1800s потолка и запроса владельца остановить работу **новых запусков/агентов/вопросов не будет**. Код, измерения и независимое предварительное review сохранены; полный пяти-вариантный эксперимент НЕ завершён. Commit/push/merge/deploy не выполнялись.

## Что реализовано

В отдельной ветке `experiment/heuristic-removal-20261013`, база91dd2b4e:
- **Q:** SQLite FTS5 BM25 без ручных boosts/penalties и связанных с final budget ранних отсечек; фиксированный bounded acquisition.
- **A:** проверенный raw source без lexical ratio и whole-question name/number obligations; qualifiedfalse/relevanceunassessed, не answer proof.
- **S:** native acquisition order, exact occurrence dedupe, whole-row packing; обход qualification-first/top2/parent/query-block rescue.

Default/control legacy сохранён, ALL default-off. Остаточные intent/lifecycle/locator/support/routing policies существуют: **«все эвристики удалены» не утверждается**. Метод — прозрачный BM25-based baseline, не точное воспроизведение BEIR/Anthropic/SetR/RAPTOR. [Соответствие исследованиям](METHOD_CONFORMANCE.md), [интеграция](COORDINATOR_INTEGRATION.md).

## Реальные результаты

**175 сравнительных вызовов начаты,173 ответа сохранены**;27 preparations. Дополнительно guards/stdio:4contexts,6prepares,1resource. Unit0, генерация0, Grounded0.

| Набор/вариант | Получено | Positive facts | Documented partial | Strict-empty negatives |
|---|---:|---:|---:|---:|
| Открытый V40, baseline |40/40|23/24|4/8|5/8|
| Открытый V40, Q |40/40|22/24|4/8|5/8|
| Открытый V40, A: только34 полученных случая |34/40|22/22 наблюдаемых|6/6 наблюдаемых|0/6 наблюдаемых|
| Старый открытый H20, baseline |20/20|6/8|5/6|0/6|
| Старый открытый H20, Q |19/20|6/8|5/6|0/5 наблюдаемых;1NOT_RETURNED|
| Новый NEW20, только baseline |20/20|5/8|3/6|2/6|

A не запускался на старомH20/NEW20; S не запускался из-за исчерпания wall budget. ALL остановлен до comparative. NOT_RETURNED/NOT_RUN не считаются пустыми результатами илиPASS/FAIL. Новый holdout не доказывает candidate gain: candidate outputs на нём отсутствуют.

Paired на одинаковых полученных случаях:
- Q: **нет gains, lossV40-E02** — нужный факт отсутствует и в native, и в packed; причинная граница по сохранённым данным не установлена.
- A,34 совпадающих случая: positives baseline21/22→22/22 (gainT03); partial3/6→6/6 (P06,T07,V06); negatives5/6→0/6 (lossB08,P07,T08,V07,V08). Это доставка frozen facts, **не качество ответов и не доказанная переносимость**.
- Из173 returned records: наблюдаемые runtime source-integrity errors0, DB/files mutations0. Невыполненные guard ветки этим не доказаны.

## Стоимость и остановки

На matched returned cases: Q context time sum175.515→467.500s (59cases); A108.215→871.630s (34cases), median1.192→29.831s. A timing включает неизменённую legacy assembly: не приписывать всю цену одной admission функции. Общий original1800s wall достигнут; interruptedQ-H20-R05 и timed-outA-V40-E03 не replayed. Preparation/idle/setup/две незавершённые calls не входят в эти суммы returned durations.

Saved pretty-JSON tokens / packed source tokens: baseline80=237620/212865; Q59=237360/216667; A34=371982/353523. Разные количества и типы случаев — **не equal-spend сравнение**. Common packed ceiling12000, observed maxima11824/11826/11802. Это не protocol/billing/full model-prompt costs.

## Защитные проверки и независимое review

Installed stdio действительно доставил OAuth факт иfalse answer/edit authority; затем supplied project version99.0.0 вернул тот же unversioned context. GuardFAIL, ALLHALTED. F статически подтвердил потерю project-version уже в baseline: **новая removal regression не доказана**, но exact-version preservation не подтверждено. [Safety stop](SAFETY_STOP.md).

Integration сценарии не сталиPASS: absolute-path matcher и multiroot snapshot setup были ошибочны. Исправления измерения не меняли facts/question/product; после halt сценарии не повторялись. Module/foreign/trace/stale/sync branches не доказаны. F нашёл также недостигнутый duplicate `scope` keyword в harness — оставлен как известный blocker для будущей отдельной работы, не скрыт удалением теста.

[Независимое AI review](INDEPENDENT_REVIEW_RU.md) завершило label-hidden NEW20 baseline judgment и static audit; preliminary verdictNOT PRODUCT READY. Phase1 immutable, facts19/26. **Comparative addendum не выполнено**: новые173-returned aggregate/paired материалы не объявляются независимо проверенными F. Human verification/generated answer quality/refusal correctness/client sessions/production smokeNOT MEASURED.

## Где всё найти

- [Навигация](README_RU.md), [инвентарь](HEURISTIC_INVENTORY.md), [контракт](CONTRACT_DECISIONS.md), [протокол](PROTOCOL.md).
- `PARTIAL_SUMMARY.json`, `PAIRED_RESULTS.json`, `offline-assessment/CASE_RESULTS.json`: конечные offline counts и все340 planned records с явными missing statuses.
- `comparison-receipts/`, `stdio-receipts/`, `guards*.log`, `restrictions.log`, `recovery.log`: lossless реальные receipts/failures.
- `CODE_FREEZE.json`, `FROZEN_RUN*.json`, `PRODUCT_IMMUTABILITY.json`: исходные freezes и measurement-only amendments; frozen product420 files, mismatches0.
- `SOURCE_PATCH_FINAL.patch` + manifest; `wheels/`; `HOLDOUT_DATA.tar.xz`; `OPEN_REGRESSION_INPUTS.tar.xz`: portable код/пакеты/данные/первоисточники.

Итог: **часть заданных эвристик реально обойдена в candidate, но выигрыш от общего удаления не доказан; Q имеет loss, A — gains, negative losses и большой расход, S/ALL не измерены. Остановиться без promotion.** Следующие контрактные/продуктовые правки и runtime — только по новому запросу владельца.

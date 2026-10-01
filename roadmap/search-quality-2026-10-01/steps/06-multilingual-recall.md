# 06 — P1: один эксперимент с bilingual recall

**Результат:** установить, восстанавливает ли same-need lookup недостающие факты до qualification и packing.

**Опора:** D4, RU/EN разрыв и [translation10](../audit/manual_translation_review.json) в [анализе](../audit/ANALYSIS_RU.md). Общие правила — в [README](../README.md).

## TDD

1. **Red:** зафиксировать installed-main baseline и одинаковые corpus bytes. Для Q29/Q30 определить, где впервые исчезает конкретный policy/isolation fact: retrieval, cap, qualification или packet; одного совпадения заголовка недостаточно.
2. Добавить experiment tests: original question сохраняется; lookup передаёт тот же need на языке docs, без предполагаемого ответа. Versions, negation, comparison sides, exact identifiers и scopes не теряются.
3. **Green:** сравнить только две lanes: question-only lexical и bilingual same-need lookup. Допустим существующий public `lookup_queries`; не вводить новый автоматический pipeline/default.
4. Прогнать Q07/Q14/Q29/Q30/Typer05 и distractors: unrelated paragraph с exact identifier, wrong version, stale/superseded source, unsafe сосед, private config, unsupported guarantee. Guards одинаковы в обеих lanes.
5. **Проверка:** сохранить stdio requests/responses и first-loss traces; сравнить fact recall до/после и конечную useful evidence/noise. Saved-pool packing replay считать отдельно, не выдавать его за retrieval improvement.

**Не менять:** qualification, caps, packing, scorer, budgets, corpus между lanes. Не добавлять aliases под frozen Q01–Q80.

**Стоп:** если факты уже найдены, но теряются позже, не расширять retrieval — передать диагноз соответствующему шагу. Если gain отсутствует или noise/unsafe admissions растут — не активировать.

Dense/hybrid и reranker — возможные **отдельные** эксперименты при подтверждённом recall bottleneck, не дополнительные lanes в этом diff. Новые зависимости и production rollout требуют отдельного согласования.

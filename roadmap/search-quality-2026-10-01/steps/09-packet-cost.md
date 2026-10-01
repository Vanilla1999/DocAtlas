# 09 — P1: full/lean packet на одном candidate pool

**Результат:** измерить, можно ли доставить больше полезных фактов без разрушения цитат и честных gaps.

**Опора:** раздел 4 в [анализе](../audit/ANALYSIS_RU.md). Общие правила — в [README](../README.md).

## TDD

1. **Red:** на saved eligible pool зафиксировать, какие requested facts теряются при packing текущего full DTO. Отдельно посчитать whole serialized input и snippet text; не записывать qualification/retrieval miss как packet loss.
2. Добавить tests experimental packer: whole JSON вместе с metadata помещается в выбранный budget; source identity, evidence IDs, exact text/spans и snapshot validation сохранены; missing facts остаются конкретными.
3. **Green:** только в experiment сравнить full/lean retrieval-only DTO при 800/1 600/2 400 tokens на одном pool и scorer. Introductory duplicates не должны занимать slots вместо найденного requested fact.
4. Controls: wrong source/version и unsafe сосед отвергаются; условия/negation не обрезаются до нового смысла. Continuation reads — только выбранный relevant source для named missing fact, с явным лимитом attempts и total retained input, без бесконечного retry.
5. **Проверка:** saved-pool replay, semantic useful facts и citation entailment на всём input. Публиковать bytes и whole-packet tokens отдельно; без live task run не заявлять экономию provider/task bill.

**Не менять:** production DTO/default budget, retrieval, qualification, scorer, citation binding. Не «экономить», исключая metadata из подсчёта.

**Стоп:** если facts не растут, gaps скрываются или растут unsafe admissions — не активировать. Публичная schema/rollout любого победившего варианта — отдельная задача; текущий результат только сравнительный отчёт.

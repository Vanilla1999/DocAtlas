# 08 — P1: Typer-факт не исчезает на раннем cap

**Результат:** rule о preceding space перед slash в negative boolean option name доходит до public evidence.

**Опора:** D5 в [анализе](../audit/ANALYSIS_RU.md), `audit/raw/traces/external48/typer-05.json.gz`. Общие правила — в [README](../README.md).

## TDD

1. **Red:** replay Typer05: нужный child `bool.md:214–231` есть до cap на позиции 9, но отсутствует после `_limit_sections_per_source`; общие boolean examples остаются.
2. Добавить regression выбора children из одного source: при существующем лимите retained candidates содержат запрошенный rule, а final snippet сохраняет negative name и значимый пробел в `" /-S"`.
3. Controls: общие examples не считаются поддержкой slash rule; unrelated exact identifier не выигрывает; source/version/snapshot guards остаются. Другие запросы к тому же source не теряют свои нужные facts.
4. **Green:** минимально исправить порядок/удержание relevant children перед cap, без case-ID aliases и полного отключения cap.
5. **Проверка:** regression + frozen external positives и панель Q07/Q14/Q29/Q30; installed stdio доставляет exact rule. Сохранить pre/post-cap IDs и final цитату при неизменном budget/scorer.

**Где начать:** `docmancer/retrieval/_dispatch_part02.py` (`_limit_sections_per_source`), существующие retrieval/ranking tests и `tests/evidence_quality_v2/`.

**Не менять:** qualification, multilingual pipeline, scorer, global caps/thresholds/budgets, dependencies.

**Стоп:** если требуется другой численный cap или изменение ranking вне этого участка, предложить отдельный bounded эксперимент. Готово после восстановления запрошенного факта без потери controls.

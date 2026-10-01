# 05 — P1: исправить измерение до настройки поиска

**Результат:** evaluator оценивает запрошенные факты, а не случайные contiguous witnesses; прежние raw scores сохраняются.

**Опора:** M1–M4 в [анализе](../audit/ANALYSIS_RU.md), [сравнения](../audit/COMPARATORS_RU.md). Общие правила — в [README](../README.md).

## TDD

1. **Red:** replay сохранённых MkDocs06, uv06 и rendered-list responses текущим scorer. Зафиксировать необоснованный `needs_review`/missing witness без нового retrieval.
2. Добавить tests: один fact может поддерживаться несколькими отдельно проверенными citations, но из них нельзя выдумывать новый contiguous quote; formatting-only списки/разметка эквивалентны. Для uv06 не требовать biopython command, которого нет в вопросе.
3. Mutation controls: неправильные числа, identifiers, polarity, conditions, version и значимый пробел в `" /-S"` отвергаются. `needs_review` учитывается отдельно, не автоматически как pass или regression.
4. Отдельно проверить quote/source identity: verbatim spans и snapshot binding. `content_sha256` — digest evidence material, не всего файла; неодинаковые типы digest нельзя сравнивать как одинаковые.
5. **Green:** минимально исправить eval logic и только подтверждённо избыточный gold uv06. Не менять исходные вопросы, runtime или официальные MCP wires; записать revised scores отдельно от original.
6. **Проверка:** eval tests + replay frozen outputs. Положительные controls распознаются, mutation controls по-прежнему отклоняются; изменения gold/scorer перечислены явно.

**Где начать:** `eval/evidence_quality_v2/semantic.py`, `observer.py`, `audit.py`; `tests/evidence_quality_v2/test_measurement.py`.

**Не менять:** production retrieval, budgets, thresholds, исходные raw artifacts. Не обобщать formatting equivalence на изменение смысла или цитируемого текста.

**Готово:** объяснимая разница old/revised evaluation на тех же responses. Это исправление измерения, не улучшение поиска. Затем остановиться.

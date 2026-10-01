# 07 — P1: сохранить найденный полезный кандидат

**Результат:** прямой whole-JSON budget fact из Q14 не проигрывает нерелевантной CLI-таблице на qualification.

**Опора:** D3 в [анализе](../audit/ANALYSIS_RU.md), `audit/raw/traces/project28/projectB-Q14.json.gz`, [исходная выдача](../audit/raw/project80/all/projectB-Q14.json). Общие правила — в [README](../README.md).

## TDD

1. **Red:** воспроизвести Q14 на сохранённом corpus: нужный child из `docs/retrieval-boundaries.md` находится в query window, отвергается с `insufficient_visible_match`, final packet содержит CLI distractor.
2. Добавить regression на эту границу: нужный fact допускается и виден в public packet. Проверить смысл вопроса, а не просто присутствие filename/слова budget.
3. Controls: exact identifier в unrelated paragraph не делает его ответом; wrong version, stale/superseded и unsafe sources не допускаются. Поддержанная часть не превращается в full answer certification или edit permission.
4. **Green:** минимально исправить question-specific qualification/отбор. Не отключать ratio checks глобально и не смешивать hard source eligibility с soft relevance.
5. **Проверка:** qualification tests, Q14 и контрольная панель Q07/Q29/Q30/Typer05; installed stdio показывает нужную verbatim цитату при прежнем budget. Trace фиксирует первое изменённое решение.

**Где начать:** `tests/docs/test_evidence_qualification.py`, `tests/docs/test_context_loss_boundaries.py`, `docmancer/docs/domain/evidence_qualification.py`.

**Не менять:** retrieval/lookup generation, per-source cap, DTO, scorer, budgets и source guards.

**Стоп:** Q07 чинить здесь только если подтверждена такая же qualification-потеря уже разрешённого нужного факта; иначе сохранить диагноз, не расширять задачу. Готово при восстановлении Q14 без unsafe admissions.

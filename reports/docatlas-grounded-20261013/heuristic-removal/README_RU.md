# Удаление локальных эвристик — новый цикл2026-10-13

**Работа остановлена. [Итог](RESULT_RU.md):175 comparative starts/173returns, общий wall исчерпан; S не запускался, ALL halted. Никакого promotion.** Новых запусков/агентов/вопросов после запроса владельца не будет. Продуктовый patch в основной ветке не применён.

- [Ownership](OWNERSHIP.md), [checkpoint](CHECKPOINT.md).
- [Контракт и полномочия](CONTRACT_DECISIONS.md), [инвентарь](HEURISTIC_INVENTORY.md).
- [Протокол](PROTOCOL.md): перед product execution требуется окончательный freeze.
- [A: acquisition](A_ACQUISITION.md): BM25 equal fields OR, fixed bounded pool; не воспроизведение Anthropic reranker.
- [B: source-only admission](B_ADMISSION_CONTRACT.md): unassessed context, не answer proof; negative oracle неизменен.
- [C: native selection/assembly](C_SELECTION_ASSEMBLY.md), [интеграция координатора](COORDINATOR_INTEGRATION.md).
- [Первичные исследования и deviations](METHOD_CONFORMANCE.md), [независимый NEW20](D_RESEARCH_AND_EVALUATION.md).
- [Публичные проверки и команды](E_EXECUTION_PROTOCOL.md).
- [Safety stop](SAFETY_STOP.md), [прерывание и recovery](INTERRUPTION_RECOVERY.md).
- `comparison-receipts/`, `stdio-receipts/`, `guards*.log`: реальные сохранённые ответы/ошибки. Ни один red guard не удалён и не превращён вPASS.
- `SOURCE_PATCH.patch` и `SOURCE_PATCH_MANIFEST.json`: portable code; `HOLDOUT_DATA.tar.xz`/`OPEN_REGRESSION_INPUTS.tar.xz`: исходные данные и первоисточники.

Основной проект: /home/viadmin/StudioProjects/hermes/docmancer.
Рабочая копия: /tmp/opencode/docatlas-heuristic-removal-20261013.
Base91dd2b4e; default-off env DOCATLAS_EXPERIMENT_HEURISTIC_REMOVAL=Q|A|S|ALL.
Ранее опубликованные V0/R/A/S результаты не являются результатами этой новой реализации.

Все новые тесты/целевые проверки — integration и выше. Unit/model calls0. Нет commit/push/merge/deploy. [Независимое предварительное review](INDEPENDENT_REVIEW_RU.md) завершено; comparative addendumNOT DONE. Полные эффекты ALL/new20 не измерены; положительная stdio выдача не означает успешный весь smoke. Последующий runtime только по новому запросу.

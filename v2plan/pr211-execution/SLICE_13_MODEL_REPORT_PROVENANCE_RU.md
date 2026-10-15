# PR211: исторический model report не заменяет новый запуск

Текущие model reports сохранены byte-for-byte. eval/results/HISTORICAL_LIVE_REPORTS.md фиксирует их реальные recording commits, SHA256 и более поздний fingerprint-only reseal Agent report. Тот reseal не заявляется новым запуском.

Archive test признаёт ровно два исторических набора bytes и проверяет, что строгий текущий Agent validator отвергает stale oracle. Изменённые reports должны удовлетворять текущему контракту. Agent validator не ослабляется, source facts/trajectories/usage старых reports не переписываются.

Task21 reuse теперь требует SHA полного текущего контракта: schemas, installed guidance, все scenario inputs/expectations, repeats, thresholds и evaluator source; также точные scenario/repeat roster и expected tools. После independent-review finding проверяется фактический `row.tool` против first-tool/legacy/unnecessary flags, обязательные action-copy/retry booleans, заново рассчитанные пять metrics и исходные quality thresholds. Одного `passed=true` недостаточно: отсутствие metrics, выдуманная accuracy, legacy decisions и даже согласованные, но ниже порога, retry results отвергаются. Детерминированный adapter positive и контрпримеры входят в существующий test, без дополнительных test IDs; они не выдаются за live model execution.

Независимый review root: source diff, исходные Git blobs и exact archive SHA сверены; APPROVE. Агент выполнил статические AST/compile без исполнения, inventory и diff checks. Live provider не вызывался. Текущие реальные client/model sessions остаются NOT RUN и не становятся PASS вследствие этой миграции.

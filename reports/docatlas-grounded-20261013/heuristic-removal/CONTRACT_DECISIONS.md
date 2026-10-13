# Контракт и границы полномочий

## До runtime

- Владелец 2026-10-13 явно поручил реализацию/измерения по NEXT_MULTIAGENT_PROMPT_RU.md. Это новый ограниченный цикл, не продолжение завершённых старых workloads и не бессрочное разрешение на расход моделей.
- Старое ограничение PR211 на локальные проверки относится к соответствующему историческому PR/checkpoint; новый цикл выполняется по его отдельному bounded protocol. Если обнаружится актуальный более строгий запрет для этой работы, runtime блокируется.
- Baseline: actual HEAD91dd2b4e, не прежняя RAS экспериментальная baseline. Исторические численные результаты служат контекстом, не автоматически baseline нового сравнения.
- Candidate opt-in DOCATLAS_EXPERIMENT_HEURISTIC_REMOVAL=Q|A|S|ALL. Default неизменен. Флаг нужен для изолированных абляций, а не для выдачи старой эвристики за удалённую в новой реализации.
- Scope/access/version/freshness/raw text/hash/span и answer/edit authority остаются обязательными. Source-valid не означает релевантность/достаточность; отсутствующие факты не доказаны соседними совпавшими словами.
- Strict-empty negative oracle не меняется. Возможно, source-only retrieval вернёт legitimate нерелевантный текст: это фиксируется как старый strict-empty FAIL, не как новый PASS. В production такое изменение контракта не одобрено.
- Обход semantic heuristics только на candidate path рассматривается как эксперимент удаления, не завершённое физическое удаление всех legacy ветвей. Итог обязан показать остаток и не обещать полного удаления из репозитория.
- Никаких unit (ни новых, ни целевых запусков), mocks проверяемого retrieval/selection/storage/validation, rewriting frozen gold/questions или hidden repair loops.
- Production promotion, deployment, merge, commit и push не выполняются. Обычные пользовательские индексы не трогаются.
- Новые модели/генератор требуют конкретного транспорта/revision/денежного потолка: здесь не одобрены. Answer quality при отсутствии такого разрешения NOT MEASURED.

## Учет расходов

Comparative предел:340 DocAtlas context calls и20 Grounded searches. Guards отдельно<=20 contexts,240s. Одно выполнение каждого frozen arm/case; timeout60s DocAtlas/90s Grounded, overall1800s на движок. Setup/prepare/resource вызовы считаются отдельно, interruption не скрывается. Недоступный comparator/client —BLOCKED, неPASS.

Единственный coordinator запускает workload последовательно. До code/data/config freeze product runtime0. Семантическое review выполняет свежий AI reviewer; это не человеческая проверка и не измерение сгенерированного ответа.

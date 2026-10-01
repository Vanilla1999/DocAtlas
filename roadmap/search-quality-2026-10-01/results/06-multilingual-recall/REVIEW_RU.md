# Саморевью частичной диагностики шага 06

Не независимый gate. Замечание исправлено в отчёте: downstream-loss stop ограничивает retrieval expansion для найденного факта, но не означает завершение остальных controls. Typer05, adversarial matrix и bilingual version/comparison preservation не выполнены и остаются открытыми. Q30 duplicate-English lookup не проверяет полноценную альтернативу recall. Не делать вывода о безопасности или готовности rollout.

Проверены original questions, lookup-only request difference, corpus hashes, installed-main production hashes и соответствие final source signatures между stdio и отдельными diagnostic calls. Q29 потеря локализована только до границы qualified fragments; отдельный predicate не объявлен виновным. Q30 остаётся pre-cap miss. Перепроверка: [2 tests passed](review-tests.log). Ни runtime, ни корпус между lanes не менялись. Partial diagnostic пригоден для передачи в шаг 07, но не закрывает весь шаг 06.

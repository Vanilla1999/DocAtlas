# Slice 19: механическое выделение retrieval diagnostics

База: `0049c6dd3643a8c214c7c899a08201495ab61d51`.
На этой версии static и federated gates остановлены из-за 1011 строк в
`docmancer/docs/application/_project_docs_service_part03.py`.
[Static log](https://github.com/Vanilla1999/DocAtlas/actions/runs/37971052890/job/113957464246).

Функции `_diagnostic_candidate_id` и `_retrieval_stage_diagnostics` вместе
с существующей константой 32 вынесены в `_project_docs_diagnostics.py`.
Тела функций перенесены буквально; поведение, query qualification, receipts,
лимиты диагностики и mutation anchors не меняются. Модули имеют 962 и 57 строк.
Предел размера модулей не повышается.

Независимый review agent_fixtures_impl: APPROVE. Через GitHub прочитаны исходный
blob `1ba6e74bba77cb4679ec8926ff9d6b510fc46ff6`, новый service
`4a8b21b05f5e6bac6e0a94cfd8d2f9128ed5ca1c` и helper
`bd4beaca068f84ca94e0b8290774fe2ca6c509ba`. Полная обратная реконструкция
совпала; imports замкнуты без service cycle. Root повторно сверил bodies.

После потери local exec transport работа продолжена exact-file GitHub API.
Local AST/compile/runtime для этого slice **NOT RUN**; ordinary CI после публикации
обязан подтвердить синтаксис и устранение static failure. Новые tests не добавлены.

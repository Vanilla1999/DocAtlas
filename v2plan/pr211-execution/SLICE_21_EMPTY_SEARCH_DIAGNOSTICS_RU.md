# Slice 21: сохранить наблюдение завершённого пустого поиска

На `118e5d1` existing two-way observer control различал rejected candidates,
но truly-empty case падал: `unclassified` вместо `observed`.
Question_recovery_impl нашёл точную потерю в `get_project_docs`: после реального
`query_project_docs` уже собран `same_call_pipeline` с planned query IDs,
пустыми retrieved candidates и qualification outcomes. Успешный return передаёт
`preflight_diagnostics`, последний `no_results` return их терял.

Исправление — передать тот же application-owned diagnostics объект в этот
`ProjectDocsResult`. Публичный DTO, no-results статус, delivery veto, источники
и readiness не меняются. Неисполненный этап не объявляется наблюдавшимся.
Существующие два pytest controls остаются без изменения.

Root подтвердил finding по точному source и checked one-line diff после
mechanical extraction: blob `1d1a3450cfa9f7d612ab12fc3e42f83eb71f990d`,
963 строки. Independent source analysis и root review согласованы.
Local AST/runtime **NOT RUN** из-за exec transport outage; CI ожидается.

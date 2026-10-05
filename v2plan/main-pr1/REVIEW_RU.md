# PR-1: целостность результата, без нового read-пути

Дата: 2026-10-05. База main: `d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c`.
Источник исследовательского решения: `b97206806e899f515b437e0aea4231ee56763bf5`.
Ветка: `fix/next07-pr1-output-integrity`, создана от main.
Это авторское ревью ДО CI, не независимое одобрение и не разрешение merge.

## Закрытый состав

- `docmancer/docs/application/_docs_context_payload.py`: только _payload([]), через существующий project_insufficient.
- `docmancer/docs/interfaces/mcp/output_contract.py`: только indivisible canonical envelope в compact_mcp_payload.
- `eval/evidence_quality_v2/run.py`: только физическая проверка audit_payload, LF/CRLF и конец файла.
- `tests/docs/test_empty_docs_context_payload.py`: constructor regression.
- `tests/docs/test_finalized_mcp_output_integrity.py`: terminal/dispatcher/SDK regression.
- `tests/docs/test_source_range_audit_integrity.py`: source/range/hash regression.
- `v2plan/main-pr1/*`: review, inventory и evidence; не импортируется production.

Три ответственности — отдельными коммитами. Нет нового query/admission/owner path,
read_delivery_limits, отмены default 800/3, runtime LLM, MCP метода/поля или миграции.
Default transport остаётся 32000 bytes; explicit max_bytes — прежний Python-параметр.
Переключение новой read-policy остаётся PR-2. Нет imports из v2plan/eval в runtime.
Semantic evaluator, corpus/gold, SDK, scopes, guards и workflows не меняются.

## Проверено до CI

Git blob SHA локальных исходников сверены с pinned main:
_payload module = 3564f5585a6d26267443bc882bff3ef3e117f743;
output_contract = 381325c8b8527d9a72d4509829e4bf7fa8abb2d0;
eval run = 17ce089fbc0185058e938a3bff36eca3ca961c6e;
model_visible_projection = 457fb02ed358d01a5f3361eb18a9554b3133aae3.
Empty module из research отличается от main только ранним возвратом.
Main-only изменения сохраняются базой дерева, не переносом всей research ветки.
AST diff меняет только _payload, compact_mcp_payload, audit_payload.

Изолированно воспроизведены: ok с пустыми sources; изменение snippet после
финализации с сохранёнными claims; ложный отказ LF/CRLF audit; допуск end за EOF.
Кандидат устраняет эти дефекты в изолированных probes. Это НЕ native evidence:
bookkeeping/token counting и upstream validator заменены стендом. Полный проект,
настоящий tokenizer/SDK/stdio в локальной среде не установлены. CI-тесты
используют штатные функции без этих замен.

Large transport fixtures — controlled producer, не прохождение retrieval guards.
Dispatcher/SDK тест имеет явную producer seam. Отдельный штатный installed/stdio
smoke должен подтвердить пакет. Нельзя называть эти fixtures native recovery.

## Риски и границы

Oversized canonical packet теперь даёт явный transport_size_limit без прежних
claims, а не частично успешный испорченный ответ. Generic compaction неизменён.
Empty не доказывает отсутствие факта во всём corpus и не запускает recovery.
Audit сравнивает original bytes: нормализованный вместо исходного текст может
честно получить отказ. EOF проверяется строже. Gold ради этого не меняется.

## Оставшиеся допуски

Focused command:
`DOCATLAS_OFFLINE=1 python -m pytest -q tests/docs/test_empty_docs_context_payload.py tests/docs/test_finalized_mcp_output_integrity.py tests/docs/test_source_range_audit_integrity.py`

Затем действующий CI, installed wheel/stdio, platform/security checks, внешний
reviewer, фактически required checks и одобрение конкретного PR.
Полный локальный main↔research diff NOT_RUN из-за DNS. Unpaginated Git tree API
прочитан; paginated compare не объявляется полным inventory. PR строится на точном
main tree из закрытого allowlist, не merge/cherry-pick 75 коммитов. Полный небольшой
main↔PR diff должен подтвердить GitHub compare/PR; лишние файлы запрещены.
Необязательный Actions inventory workflow был заблокирован инструментом;
обходная запись не выполнялась. Используется существующий CI.

До зелёного CI и внешнего ревью main не изменять. N10, 80/49/54 replay, reader
pilot, release и PR-2 не запускать. Исторические отказы не переписывать.
При содержательном FAIL сохранить результат без увеличения limits или allowlist.

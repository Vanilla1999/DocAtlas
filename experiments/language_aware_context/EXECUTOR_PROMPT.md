# Coding-agent: отдельный language-aware context experiment

Работай в Vanilla1999/DocAtlas, ветка `experiment/language-aware-context`,
PR base `main`. Начальный main: `58c7f37c2a5ef686bcd6562abbade91ba94e347a`.
Не переносить и не сливать `task-44-cross-lingual-retrieval`.
Прочитай README.md, PLAN.md, STATUS.json в этом каталоге и roadmap/README.md.

Цель: проверить H1 (языковой hint сверх существующих host lookups), H2
(сборка контекста при тех же queries), H3 (реальный ответ основной модели).
Прежние симуляции 11/11 и Grounded-like 6/7 не результаты продукта.

Первое действие — продолжить T0/T1: полный checkout, зависимости, реальный
baseline handler. Уже существующие reference/probe unit tests не являются
подтверждением T0/T1. При блокере записать точную причину, не заменить BM25,
qualification, projection или ответы провайдера собственной симуляцией.

На каждом этапе: тест, inventory, первый запуск, поведенческий RED,
минимальное исправление, повтор, регрессии, отчёт. Import/collection error —
BLOCKED, не RED; уже работающее поведение — BASELINE_GREEN.
Не менять эталоны после просмотра evaluation. Ручные lookups — dev, не live.

A/C воспроизводят один сохранённый реальный ответ планировщика без профиля.
B/D — другой, с профилем. E — тот же агент с обычной RU/EN-инструкцией.
A тоже использует lookup_queries. Иначе пользу профиля не изолировать.
Бюджет один, candidate limits общие, профиль не становится фильтром документов.

Исходный question и литералы неизменны. Нельзя подсказывать в lookup ожидаемый
ответ/API value, которого не было во входе. Placeholders защищают bytes, но не
доказывают правильность перевода, отрицания и условий. Это отдельная оценка.

Сосед разрешён для рассмотрения лишь после фактически допущенного seed.
Проверить scope/version/snapshot/source/parent, source policy и новое целое
окно. Не давать ему coverage/support/edit-ready через соседство или high score.
reference_core не производственный policy и не Markdown parser.

P0, frozen v3/digests, MPNet 0.7453, default_mode, публичный MCP и lockfile
не менять. Новые модели не устанавливать. Sidecar и C/D только изолированно.
На main нет старых crosslingual_relevance helpers: не добавлять такие imports.
Историю можно читать по ref старой ветки, но не тащить её commits в этот PR.

Разрешение пользователя распространяется на эту ветку и отдельный draft PR
к main. Не merge, не активировать продукт, не запускать платные jobs и не
публиковать raw runs/личные данные. Каждое изменение в рамках этого PR должно
быть проверяемым; не отмечать PR ready по количеству unit tests.

В конце: выполнено и измерено / написано, но не запущено / blockers / H1-H3.
Если профиль не даёт пользы сверх A или E — так и написать, не усложнять продукт.

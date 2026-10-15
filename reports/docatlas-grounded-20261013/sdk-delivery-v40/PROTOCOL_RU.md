# Повторная проверка открытых40 вопросов

Разрешение: текущий запрос владельца «коммит и пуш а потом проверь на40 вопросах».
Коммит продукта8605cbdb запушен до начала выполнения.

Одна серия на текущем default без selector/admission experiment arms:40
get_docs_context,5 confirmed prepare по исходным source families. Installed wheel,
Python -I, настоящие public in-process MCP handlers и member SQLite, не stdio.
Исходные вопросы/корпус/gold/evaluator не меняются и oracle не передаётся продукту.
Набор открытый, повторно использованный, НЕ новый blind holdout.

Лимиты:40 context attempts,<=5 preparations, context60s, prepare180s,
общая worker wall1800s и outer timeout1800s. Без автоматических повторов.
Source-integrity violation останавливает серию; read-only mutation — весь запуск.
Relevance/coverage FAIL не остановка и не повод менять вопросы/oracle/продукт.
Trace включена для диагностики; ошибки/пробелы trace не считаются фактами.

Конечный host cap12000; полный public DTO сохраняется отдельно от дополнительной
исторической whole-source packing policy12000 o200k. Это не provider bill/full
answer prompt. Tokenizer asset локально pinning/hash; без download и model calls.

Используется существующий eval/heuristic_removal/run.py в --worker режиме.
Историческая метка V0 здесь обозначает ТЕКУЩИЙ default8605cbdb, а не старый91dd2b4e
baseline. baseline_python/baseline_wheel в manifest указывают текущий installed
artifact только ради совместимости runner; historical comparative orchestrator
и его freeze340-call design НЕ запускаются. Новый reduced manifest явно фиксирует
дизайн40x1; никаких новых product/runner/oracle изменений.

Оценка офлайн существующим assess.py/evaluate.py: fixed positive fact coverage,
documented partial, strict-negative empty sources, source/span/hash/scope/version,
read-only, native versus packed, время/actual calls/bytes/tokens. Answer quality
и неподтверждённые сгенерированные утверждения НЕ измеряются (generation0).

Все файлы продукта/runner/dataset/oracle/tokenizer/config/worker и wheel
hash-фиксируются до первого product call. После проверяются без изменений.
Выводы исторического сравнения — только диагностический контекст; improvement
не выводится из сравнения разных коммитов/конфигураций по одному aggregate.

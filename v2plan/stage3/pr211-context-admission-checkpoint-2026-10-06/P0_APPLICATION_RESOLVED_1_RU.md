# P0: application, раздел 1 — завершённый аудит

Разобраны **83 из 83** строк `archives/p0-application-open-1.json`.
Результат: `archives/p0-application-resolved-1.json`.

| Решение | Строк |
|---|---:|
| REMOVE | 25 |
| SPLIT | 36 |
| TECHNICAL-RETAIN-CANDIDATE | 22 |
| OPEN | 0 |

## Смысл решений

- **REMOVE**: убрать выявленную интерпретацию из авторитетного admission-контура, а не автоматически удалить всю функцию. Например, генерация behavioral obligations из совпадения токенов путей, превращение guidance в invariants по нормативной лексике, эвристические запреты generated-файлов и переформулирование вопроса не являются технической проверкой.
- **SPLIT**: отделить конкретный семантический producer от транспорта и защит. В JSON для каждой строки названы inline-механизм или зависимости: например, `qualify_evidence`, `best_local_proof`, `compile_need_contracts`, `assess_documentation_evidence`. Оркестрация не получает исключение только потому, что делегирует решение.
- **TECHNICAL-RETAIN-CANDIDATE**: кандидат на сохранение только в указанной технической границе: схема DTO, точное разрешение module identity, lease/transaction, capability range, storage containment, проверка manifest/content hashes, диагностическое отображение уже типизированных состояний. Это не подтверждение семантической полноты ответа.

## Доказательства и сохранённые границы

Каждая строка сохраняет исходные поля и исторические `limitations`, зависимости, consumers и static reachability. Исходные решение и причина сохранены в `input_decision` / `input_reason`; актуальная классификация находится в `decision`, `reason`, `evidence.mechanism_review`.

Добавлены фактический полный текст owner, проверенные хеши, source-level сведения о зависимостях, конкретная граница миграции и эффект для consumers. Исходные `preserve` дополнены, но не удалены. Историческое `mechanism_review: OPEN` внутри исходных limitations не является актуальным решением.

Особенно сохраняются: отрицательные support flags, запрет превращать derived attribution в публичное покрытие, exact byte/hash/range binding, project/module/lifecycle scope, подтверждение сетевого/latest fallback, бюджет, continuation authorization, cancellation/revocation и rollback предыдущего corpus. Диагностическое слово `official` не даёт полномочий источнику; manifest hash доказывает идентичность хранения, а не содержание ответа.

## Проверки

- Точное совпадение состава и порядка всех 83 `(path, owner)`; пропусков, дополнительных строк и дублей нет.
- Проверены **83/83 file SHA-256** и **83/83 owner SHA-256** против входных pins.
- Owner hash: строки `source_span`, соединённые `\n`, затем `lstrip()`, без завершающего перевода строки.
- Зафиксированы хеши 89 файлов owners/зависимостей; хеш входного checkpoint записан в `audit`.
- Неизменность остальных исходных полей проверена программно.
- `AGENTS.md` не найден в репозитории и родительских `/`, `/tmp`, `/tmp/opencode`.

## Ограничения

Это P0-классификация, не реализация и не разрешение на удаление. Static references, wildcard facades, self/cls edges, hooks и runtime callbacks не доказывают исполнение. Неустановленные binding явно отмечены. Отсутствие consumer в исходной карте не доказывает dead code. Продукт и тесты не изменялись и не запускались.

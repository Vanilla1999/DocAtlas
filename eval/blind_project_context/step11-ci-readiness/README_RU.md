# Готовность PR #246: снимок перед шагами 3/4

Дата: 7 ноября 2026. Проверенный удалённый head:
`2d667913f279ba72104f158ee6500d75d5ace81f`; main:
`ae81aaae82794bfcbf6c0ee777bfc2f76e0e0def`.

## GitHub и CI

PR открыт как Draft, `mergeable=true`, `mergeable_state=unstable`.
Публичный branch endpoint сообщает `protected=false`, status enforcement `off`,
пустые required contexts/checks. Repository rulesets также пусты. Подробный
administrative protection endpoint вернул 403 для integration; административные
изменения или обход правил не выполнялись. Наличие технической возможности
merge не означает, что качество проекта подтверждено.

Все 22 workflow этого head завершены: **13 success / 8 failure / 1 skipped**.
В частности, static-contract и P2 federated теперь прошли после исправления
лимита строк. Blind project-context gate и MiniLM installed MCP тоже прошли;
для blind gate прочитан только статус.

Основной CI остаётся красным. В Python 3.12 core:
**88 failed, 1450 passed, 13 skipped, 136 deselected**, 197,20 секунды.
Эти 88 failures нельзя называть прежними 63 без сопоставимого baseline.
Compact MCP повторяет несогласованность сравнения global/project registrations
в `context_instruction_measurements.py:158`. Source-native, main-flow, P1,
retrieval-evidence и installed stdio failures остаются видимыми. Предыдущие
установленные причины и ограничения описаны в
[CI_TRIAGE_20261107.md](../../../reviews/CI_TRIAGE_20261107.md).

Снимок статусов и точные URL:
[ci-snapshot-2d667913.json](ci-snapshot-2d667913.json).
Это не проверка будущих изменений лёгкого клиента или presentation v2.

## Точечное исправление Unicode guard

Первый installer smoke останавливался на четырёх U+202F в двух сохранённых
Markdown-отчётах. В `scripts/test-install.sh` диапазон `0x202A..0x202F` включал
U+202F NARROW NO-BREAK SPACE. Его Unicode category — `Zs`, bidi class — `CS`.
Настоящие embedding/override controls этого диапазона — U+202A..U+202E (`Cf`).

Исправлена только верхняя граница Python range с `0x2030` на `0x202F`.
Все embedding/override/isolate controls и общая проверка `category == Cf`
сохранены. Исключений файлов или директорий не добавлено.
Сохранённые `candidate.md` и `candidate-partial.md` побайтно не изменены;
их hashes записаны в receipt.

Один запуск существующего `sh scripts/test-install.sh`: **PASS**, 5,668 секунды.
Это installer smoke с реальным `install.sh` и уже существующими stub внешних
`uv`/agent CLI. Это не реальная установка и не модельный тест.
Временные данные размещены в изолированном workspace TMPDIR.

- [installer-smoke.log](installer-smoke.log)
- [installer-smoke.receipt.json](installer-smoke.receipt.json)

Новые unit tests не добавлены, старые tests/gold не удалены и не изменены.
Открытый HREF finding относится к явно включаемому, ранее заблокированному
reference-closure v3. Эта правка не включает его и не закрывает finding.

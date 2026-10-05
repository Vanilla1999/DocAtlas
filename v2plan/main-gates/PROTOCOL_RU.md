# Контроль исходной базы перед исправлением gates

Дата: 2026-10-05. Продолжение плана миграции, этап 3. Это отдельная диагностическая ветка, не PR-1 и не новый read-путь.

## Неизменные входы

- Base main: `d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c`.
- PR-1 #206: `596eeb36b66a474b2b5d246fd6bd834b6dcbb5c6`, draft, без merge.
- В начальной revision этой ветки изменён только этот документ. Runtime, tests, labels, workflows, корпус и ожидания совпадают с main.
- Выполняется существующий CI. Новых workflows, skip/xfail, override ожидаемых результатов и отключения guards нет.

## Почему нужен контроль

В прежних CI-логах заявлены failures из `tests/docs/test_compositional_task_matrix.py` и `tests/docs/test_unified_context_service_pipeline_surface.py`. При текущем чтении Contents API этих файлов по закреплённым main и PR-1 SHA не получено (404). Доступный service использует module/module_path и объектные DTO; часть прежних excerpt использует file_path и словарный result. Само несовпадение ещё не доказывает причину: необходимо проверить действительные tests, checkout SHA и новый запуск на неизменном коде. Не исправлять guards по названию из потенциально несогласованного evidence.

## Последовательность

1. Проверить complete main-to-branch diff: только этот документ. Зафиксировать head SHA и run IDs.
2. Прочитать checkout revision, collection, реальные failures и успешные проверки нового CI. Не подменять весь suite отдельным PASS.
3. Для каждого воспроизведённого failure связать test path/fixture и исполняемый callable с исходником этой revision. Ошибка привязки evidence — технический BLOCKED, не причина ослаблять product contract.
4. После воспроизведения каждую ответственность исправлять отдельно: selector validation, scope delivery, answer applicability. PR-1 transport не менять. Сначала определить текущий владеющий функцией слой и неизменные positives/negatives; затем patch, review и существующий CI.
5. Merge только после обязательных gates и отдельного review. Main и research-read не изменять этой диагностикой.

## Заранее заданный verdict

- `BASELINE_REPRODUCED`: фактический checkout и исходники связаны, failures воспроизводятся и описаны точными assertions.
- `BASELINE_CHANGED_OBSERVATION`: новый CI даёт другой набор исходов; сохранить оба, не объявлять прежние failures исправленными.
- `BLOCKED_EVIDENCE_IDENTITY`: нельзя согласовать исходники, revision и failures; никакого speculative runtime fix.
- `BLOCKED_EXECUTION`: CI не исполнен или среда не подготовлена; NOT_RUN не становится PASS.

Даже зелёный baseline не заменяет CI PR-1. Ни один статус этой контрольной ветки не разрешает rollout. N10, parser/ranking и модельные эксперименты вне области.

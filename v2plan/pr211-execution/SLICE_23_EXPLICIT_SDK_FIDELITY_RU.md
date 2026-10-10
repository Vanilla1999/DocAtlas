# Slice 23: семь current SDK / source fidelity migrations

Продолжение slice20 в `tests/docs/test_action_packet.py`. Сохранены все
20 function names, исходные вопросы и source facts; общий модуль имеет 933 строки.
Удалённые output-cost параметры v3 не переносятся в новый контракт.

| Existing case | Действующий oracle |
|---|---|
| Four permission targets | Явные четыре fixture members + SDK symbol DTO; no-grant не читает; все четыре actual resolved paths и source windows должны пережить форматирование. |
| MissingPermissionGate | Явное target-declaration requirement остаётся missing при единственном OtherGate; invalid-display причина не подменяет selector miss. |
| NativeVoiceCapturePlugin | Сохранены docs sentence и code declaration; SDK modify задаётся явно. Create требует независимые parent context и collision receipt; parent без collision не готов. |
| MCP / fetch-index | Полный исходный текст и оба явных literal facts сохранены. Подмена fetch/index на fetch отклоняется binding validator. |
| ActionPacket path alias | Уникальный filename может дать navigation resolution, но не доказать отсутствующее в source объявление. Honest unresolved packet остаётся partial; forged resolved alias отклоняется конкретным mutation-binding guard. |
| Canonical display child | AGENTS sentence и code child сохраняют hashes/whole windows, остаются untrusted data; prose не создаёт mutation intent. |
| Python imports / prose | Полный блок import и исходное retries statement сохранены; требование задаёт caller. Import names не создают inferred normative instructions. |

Новый контракт не выдаёт `edit_ready=true` даже при доступном полном evidence.
Тесты не требуют старых implementation_guidance / required_invariants / status v3.
Операционные source work/file/item budgets сохранены.

Независимый question_recovery_impl review нашёл ошибку первого draft: alias-only
resolution ошибочно ожидался validator-valid. Исправлен именно oracle: original
source не получил выдуманных symbols; добавлен адресный rejection control.
Исправленный blob `3f3de127db49fc7d097984444861a2635afcf227` APPROVE для CI.
Шесть остальных cases одобрены отдельно. Local AST/runtime **NOT RUN** из-за
exec transport outage. Остальные public delivery tests и Task33 worker migrations
ещё открыты; весь Task33C gate не объявляется зелёным.

# PR211: явный ActionPacket контракт вместо разрешений из текста

Узкая миграция 16 старых failure cases в tests/docs/test_action_packet.py. Production код не меняется; остальные ActionPacket failures остаются отдельной работой.

- Десять прежних EN/RU просьб изменить файлы больше не создают mutation intent и не маршрутизируют patch автоматически. Исходные формулировки сохранены.
- Constraints-only prose также не создаёт targets, acceptance conditions или readiness. Три общие просьбы остаются unsupported_patch_surface.
- Исходный positive с BrowserPermissionGate, ScanPermissionGate, OfflineSyncGate, PermissionService и сохранением permission_result.freezed.dart использует независимо авторованный SDK DTO. Точный source span даёт provenance user_request; operation и план переданы явно. Это не возрождение NL inference.
- Реальные source-map evidence, разрешение целей, readiness, canonical packet validation и привязка ко всем mutate/preserve файлам сохранены. Validator получает тот же исходный resolved contract; публичный packet не разрешает edits.
- Missing preserve negative сохраняет исходный вопрос, точные spans и требование недостающего preserve_declaration. Unique/ambiguous symbol resolution получает явный RequestedTarget, а не разрешение из prose.

20 test functions сохранены. Один node ID переименован по действующему смыслу; соответствующий diagnostic inventory hash обновлён. Независимый review question_recovery_impl обнаружил и помог исправить provenance mismatch до публикации, затем APPROVE. Статический AST/compile без исполнения и diff check PASS; новый CI ещё должен подтвердить фактическое исполнение.

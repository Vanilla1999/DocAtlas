# PR211: явная source boundary положительного mutation fixture

На fdbdc58 Task33C выполнил 64 cases: 46 PASS / 18 FAIL. Пятнадцать из шестнадцати мигрированных ActionPacket cases прошли. Оставшийся positive сохранил FAIL уже на mutation_target_not_resolved/preserve_target_not_resolved: исходный source-map вызов не имел конечного code_files grant и корректно возвращал пусто.

Тест теперь передаёт независимый список пяти исходных fixture paths: BrowserPermissionGate, ScanPermissionGate, OfflineSyncGate, PermissionService и permission_result.freezed.dart. Явные requirements берутся из авторованного SDK DTO. include_generated=True нужен только для явно перечисленного preserve-файла; произвольное перечисление каталогов не разрешается. Default вызов без boundary обязательно остаётся пустым.

Исходный вопрос, bytes всех source fixtures, operation, requested/preserve targets и негатив missing preserve не изменены. Readiness, точное множество реально полученных paths, canonical packet validation с исходным resolved DTO, visible mutate/preserve bindings и edit_ready=False остаются обязательными. Production не меняется.

Независимый review agent_fixtures_impl APPROVE: существуют все пять файлов и четыре декларации; остальные 19 test functions AST-identical. Имена/parametrize и diagnostic node hash прежние. AST/compile без исполнения PASS. Нужен новый реальный CI; положительный результат пока не заявляется.

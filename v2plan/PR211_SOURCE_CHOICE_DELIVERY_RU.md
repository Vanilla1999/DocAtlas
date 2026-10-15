# PR #211: source-choice delivery и текущий public/SDK контракт

## Исправляемая ошибка

При `confirmation_required` ранний delivery veto удалял не только evidence, но и
подготовленный сервисом вопрос о выборе источника документации. Текущий producer
`_UnifiedDocsContextServicePart02._ensure_library_safe` при `needs_docs_url`
создаёт `ask_user_for_library_docs_source`; варианты создаёт
`library_docs_source_options`. Это вопрос пользователю, не разрешение на выполнение
`prepare_docs`, поиск, сеть или изменение файлов.

## Контракт

Сохраняется только top-level `next_action` с текущими reason/confirmation полями,
точным `requires_confirmation is True`, `tool is None` и непустым текстовым вопросом.
Наличие hard stop, конфликта или отдельного delivery veto подавляет действие.
Вопрос из цитируемого source не становится действием.

Валидированные варианты и предупреждение о качестве доходят без изменения значений,
включая допустимые `null` в typed arguments, confidence и why.
Текущие discovery-варианты producer имеют `quality_guarantee=False`; значение True
не принимается. Неизвестные команды/arguments не передаются.
`auto_execute` всегда False. Evidence, read-next и edit/answer grants отсутствуют.

## Существующие тесты

Изменения продолжают ранее подготовленную миграцию трёх ActionPacket-тестов:
публичный read-only DTO отделён от явного SDK `context_format=patch_context`;
цитаты сохраняются целиком и остаются untrusted; prose не предоставляет mutation grant.
Все 20 имён тестов модуля сохраняются; основной файл остаётся меньше 1000 строк.

В существующий большой тест добавлен один вызов общей helper-проверки.
Исходные Kotlin question/id/docs_url сохранены. Положительная проверка использует
действующие функции producer и требует точной доставки options/quality_warning через
`handle_context_tool`, `_mcp_tool_result` и JSON text fallback.
Вторая положительная проверка требует удаления подставленных tool/auto-execution/network полей.

32 отрицательных варианта проверяют строгие bool, malformed options/arguments/action,
пустой вопрос, неверные reason, hard stop, top-level и вложенный сериализованный конфликт,
delivery veto и embedded-only action. Они требуют отсутствия действия и evidence,
а не исключения TypeError. Это проверки поведения, не отчёт об уже выполненном mutation gate.

## Review и доказательства

Проверены producer и early-return путь в текущих исходниках:
`library_source_options.py` blob `d9245a740b501e42ab7c1c9041cbfa9452b1582b`,
`_unified_context_service_part02.py` blob `fa19322da543e92253d548d8934e82a12fee9acf`,
`context_tools.py` blob `7a3cb4f113603c27accf3feb44f27f546ff595fd`.
Production projection базируется на `57ff660cc869aa6a3c04d36c7e8932658d988df3`,
helpers — на `f3c21c98d368ba1bcea2a87e87b1557ccb41a6da`.
Миграция теста базируется на `aba7c39d44593cfaf02b33e53f21d7d2450ca297`,
общий helper — на `d2bbb36996121a5e2b2e8b8b37f3c753a382b327`.

Локальный runtime/импорты/pytest не запускались. Эти изменения требуют CI на общем SHA.
Fake MCP types проверяют реальные функции сериализации; это не stdio-проверка и
не installed/client acceptance.

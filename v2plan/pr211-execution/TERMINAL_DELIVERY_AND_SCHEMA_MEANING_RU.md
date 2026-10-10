# PR #211: terminal delivery и смысл schema guards

## Основание

На `2acfaa4fdac8cc599d84ae1c48836335e9cd29a7` [same-run JUnit](https://github.com/Vanilla1999/DocAtlas/actions/runs/37994136625/job/114038915258) показывает 13 FAIL / 12 PASS в `test_finalized_mcp_output_integrity.py`, 2 FAIL / 17 PASS в `test_dictionary_exit_public_request.py`, 2 FAIL / 38 PASS в `test_action_packet_v4_workflow_surface.py`. Это не объявляется общим результатом PR.

Владелец отменил внутренние output ceilings. Действующий `compact_mcp_payload` сохраняет finalized `docs_context`/`docs_answer` целиком; проверенный v4 patch имеет отдельную ветвь. Не прошедший v4 validation patch не получает освобождения от конечного административного ограничения. `validate_model_visible_projection` по-прежнему сверяет snapshot, source identity, hashes, координаты и запрет authorization независимо от отсутствующего token ceiling.

## Изменение

- Сохранены все test definitions и параметры трёх модулей; их исторические node IDs не изменены. Это миграция 17 ожиданий, не сокращение числа запусков.
- Крупные finalized Docs DTO проверяются побайтно после serializer, включая UTF-8/CRLF, полный хвост с условием/отрицанием, source hash и координаты. Проверяются обе настоящие MCP формы: `structuredContent` и JSON `TextContent`; fixture использует явную producer seam и не утверждает реальную retrieval/stdio/client проверку.
- Сохранены invalid-patch refusal, невозможность выбрать exemption forged полями, tiny-limit failure, pagination isolation и административная compaction. Старый numerical constant относится к этой административной ветви; нового Docs ceiling нет.
- Recovery validator вызывается с отсутствующим token ceiling и тем же реальным snapshot. Дополнительная подмена snippet обязана вызвать именно source/snapshot mismatch после пересчёта estimate, а не упасть на устаревшем estimate.
- Краткие schema descriptions проверяются по сохранённым propositions: omitted/null не дают записи; null generation допускает только absent store; POSIX no-follow либо fail closed; caller/project не перенаправляют private storage. Строгая JSON Schema и все существующие consent/path/hash/generation/unknown-field negatives, а также полный security handoff в guide сохранены.

## Проверка

Текстовый review и связь с опубликованным контрактом выполнены до CI. Локальный runtime не запускался. Результат нового CI должен быть записан отдельно; ожидаемый PASS не считается фактическим.

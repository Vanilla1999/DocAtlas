# Terminal transport integrity — протокол до native исполнения

База: 3f82cae4c31de69e4c4df920a1d211e2f37bb6e2, ветка next07-feasibility-audit.
Пользователь разрешил анализ и исправление транспорта, затем обсуждение N10.
N10 не меняется и не запускается этой правкой. Его прежний результат не удаляется.

## Заменяемая ответственность

Общий compact_mcp_payload не должен рекурсивно сокращать canonical projections
(docs_context/docs_answer/patch_context) после handler validator. Он обслуживает
обе существующие границы: call_docs_tool_payload и _mcp_tool_result.
Уже собранная projection — неделимый контракт: либо весь payload неизменен,
либо самостоятельный transport_size_limit без источников/прежнего proof credit.
Сокращение administrative/rich debug DTO вне этих типов сохраняется.

32 000 bytes — найденный внутренний default compactor, не доказанный предел MCP.
Не повышать цифру ради PASS. Caller-owned ReadDeliveryLimits получает явное
max_transport_bytes: legacy/custom default 32000, COMPACT_READ_LIMITS — None.
Это внутренний контракт, не поле public schema. Явный max_bytes аргумент
transport-функции имеет приоритет даже над unlimited policy. Документ/payload
не может выбрать unlimited. None аргумент выбирает trusted/default policy.
Если даже минимальный error не помещается в явно переданный абсурдно малый
предел, функция бросает ValueError, а не возвращает превышающий предел JSON.

Политику следует держать активной до SDK serialization. Если caller её утратил,
большая projection явно отклоняется, а не повреждается. Проверить to_thread и
оба SDK формата. Не использовать payload flag как перенос доверия.

## Allowed files

- docmancer/docs/interfaces/mcp/output_contract.py: atomic projection branch.
- docmancer/docs/domain/read_delivery_limits.py: internal transport-byte policy.
- v2plan/test_next07_compact_delivery.py: только новое поле внутренней dataclass
  в shape/invalid-parameter tests, прежние semantic expectations неизменны.
- v2plan/test_next07_transport_integrity.py: transport и native regression.
- .github/workflows/next07-transport-integrity.yml: isolated non-release запуск.
- v2plan docs и новые append-only artifacts этого этапа.

Не менять retrieval, parser/owner helper, read_decision, first_fit, source guards,
evaluator, корпус/labels, release gates, production activation и main.
Не удалять точные ограничения из цитаты и не подменять их пересказом/continuation.

## Порядок и приёмка

1. Проверка кода и воспроизведение старого clipping на фиксированном пакете.
2. Код; авторское review с hashes и проверкой неизменных обязанностей до push/run.
3. Полный project environment: existing 173 regression checks, новые transport
   controls, старые output_contract tests, реальные >32KB owner через handler
   и mcp.types SDK (text_fallback False/True), LeaseClient P1/P2/P3.
4. Неизменённый native 80 N/C corpus. N10 standalone не вызывается.
5. Дополнительная терминальная SDK сериализация каждого сохранённого final
   packet с той же caller policy, сравнение точного payload и повторный audit.

TRANSPORT_VALIDATED: tests/target PASS; 80/80 валидные пары; оба source audit
чисты; SDK не меняет возвращённые payload; конечный byte limit выдаёт отказ
без ложного credit; legacy/default и proof/edit limits не отключены; frozen
inputs не менялись. Fresh/historical ID retention отчёт отдельно от завершения
transport. Кандидат в целом не повышается автоматически до accepted.
REJECTED: valid case повреждает/теряет цитату на transport, изменяет источники,
flags/хэши/координаты или неожиданно снимает finite/proof лимит.
PARTIAL/BLOCKED: невозможно валидное измерение; сохранить конкретные raw errors.
Не менять selection/ranking или ожидания после содержательного failure.

Local tests не заменяют native, SDK roundtrip не называется live stdio session.
После native результата обновить NEXT_07_VERIFIED_STATE_RU.md и SUMMARY_RU.md.

# Один read-admission контракт: scope до реализации

2026-10-03. Research-only. Production route не переключается.

## Обязательное правило: мы уже переусложнили

Каждое изменение должно **заменять конкурирующее решение**, не добавлять fallback,
relation/library-specific rescue, словарь или настройку thresholds. Если требуется
новое исключение под failed case — остановиться и отклонить этот вариант.

## Граница этого шага

Первый минимальный вариант отделяет read decision от результата proof qualification:

1. Existing `source_window_eligibility` и `prepare_source_probe`: exact current
   source/request/span, metadata/security/version/scope/freshness guards.
2. Prepared literal identities в видимых bytes; subject в body или verified owner.
3. Existing native compiler/applicability: обязательные conditions не ослабляются.
4. **Один** existing substantive locality predicate `local_topic_witness` с
   неизменными 3 terms + adjacent pair. Никаких двухсловных/typed rescue веток.
5. Return только `allowed/reason`; никаких qualification IDs, coverage/permissions.

Candidate не вызывает `qualify_evidence` и не трактует его reason strings как
read permission/refusal. Не подключает typed research compiler: сравнение меняет
только read admission. Unknown applicability остаётся закрытой.

Это проверка упрощения **владения решением**, не исследовательски доказанная
семантическая relevance policy. Lexical locality пока сохраняется как контрольная
политика без threshold tuning; её известные recall ограничения не скрываются.
Заменить её новым общим predicate в этом шаге не обещаем.

## Что заменяем / что не меняем

- В isolated read arm заменяем весь `read_context_admission` одним решением.
- Не используем qualification reason whitelist, typed-context fallback или
  relation-specific read preference как альтернативный admission.
- Retrieval/order, source snapshots, clipping, budgets и serializer одинаковы.
- Existing proof pipeline не меняем: research renderer всегда оставляет
  `answer_supported=false`, `edit_ready=false`.
- Permanent prefit/disposition/projector consumers пока не мигрируют. Это не
  доказательство, что production orchestration уже упрощён.

## Paired проверка

Использовать **native retrieved candidate captures** archived baseline 80 cases,
не passage/owner inventory API 01–04. Rebind original exact source spans к verified
archived snapshots; не запускать поиск или hydration с другими caps.

Оба arms: identical deduplicated native order, native compiler, whole-DTO 1500,
existing selector/serializer/final checks. Baseline arm — current native read
function, candidate arm — unified read. Исторические 49 baseline claims остаются
reference result, но не выдаются за freshly measured baseline этого эксперимента.

Acceptance: никакой потери supported baseline-arm claims; no new negative packets
или source/permission failures. Отдельно измерить review queue и differences in
admission. Synthetic controls не заменяют held-out и полный regression.

**Stop:** если result не улучшает retention, не продолжать новым набором exceptions.
Сохранить ограниченный результат и явно назвать ещё открытый relevance blocker.

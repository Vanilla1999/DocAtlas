# Review до исполнения внешнего reader pilot

Review авторский, не независимый аудит. Base3195ff26, protocol33d47fec,
implementation9c8057e. До этого review выполнена только Python syntax/AST
проверка в локальном контейнере; полноценный native/LLM запуск не заявлен.

## Проверено по коду

- Первый packet приходит от capture_arm(C) через настоящий public handler.
  После этого audit_payload обязан пройти; замены ответов на заранее написанные нет.
- initial_context не меняется между A и B. Навигация — явное дополнение host,
  не исправление старых section labels и не новое поле production DTO.
- Модель получает question, первую выдачу, tool schemas и последовательные результаты.
  Private Case/category/rubric/frozen_case не сериализуются в модельный запрос.
- Test reader расположен только в v2plan. Никакой production module его не импортирует.
  Использует существующие source bindings и current gateway, не arbitrary file paths.
- Навигация по parser headings в исходном порядке; никаких query-dependent
  selection/regex/словников/отдельных правил под FastAPI в host.
- Чтение — явное действие модели, не автоматическое восстановление after veto.
  Exact guard первого packet неизменён. Результат явного чтения не проходит
  semantic qualification и НЕ называется ответом: это отдельный source-read contract.
- Две попытки на сессию, opacity/expiry/replay, authorization до и после IO,
  snapshot digest и exact section bytes. Нет clipping и повторного подбора диапазона.
- Legacy reader caps600/40/2 и gateway1MiB не расширены; слишком большой раздел
  честно недоступен. Initial800/3 не применяется новым host повторно.
- API credentials не передаются модели, не сохраняются в artifacts, удаляются
  из ambient env до конструктора DocAtlas service. Нет provider fallback/retries.
- Unit scripted oracle обозначен NOT_MODEL. Авто-assessor оценивает наличие
  visible evidence, не смысл ответа. Общий quality PASS не выставляется кодом.
- GitHub Actions должен проверить exact hashes и отсутствие diff в закрытых слоях.

## Ограничения, которые не скрыты

Это тест нового исследовательского host интерфейса, а не уже доступного tool
в произвольном MCP клиенте. Первый tool call делает host; модель тестируется
начиная с ответа на него. A/B отличаются не только metadata, но и доступным
чтением/числом model turns, поэтому нельзя приписать эффект одним заголовкам.

Reader видит только документы из initial selected sources. Если initial пуст,
никакого скрытого обхода retrieval нет. Длинные sections/MDX/revoked sources
могут быть недоступны. Возможность навигации и качество её выбора разные свойства.
Авторские fixtures содержат искусственные имена/числа; они не unseen benchmark.
Один повтор не доказывает воспроизводимость качества. Нужна проверка именно
будущего model/host профиля, прежде чем обещать такое поведение пользователям.

Unit capability tests используют fake gateway (контроль границы/no IO), native
pilot — настоящий gateway и index/catalog. Эти уровни нельзя складывать в
один счётчик «модель прошла». Реальный live provider при отсутствии ключа
должен дать BLOCKED_PROVIDER, а не заменить модель scripted исполнителем.

N10 вне этой правки. 48/49 first-call и54 C facts не объявляются новым PASS.
Native и model raw outputs должны остаться раздельными; независимый review
финальных ответов требуется после actual model completion. Rollout запрещён.

# Первый пакет исполнения: question/recovery и карта baseline

База: `11489239ae0a5ff85c1f817f0650bea661e88ba1`. Дата: 2026-10-09.
Статус при подготовке: код проверен статически; новые runtime результаты ожидаются
от обычного PR CI. Этот документ не объявляет весь план или acceptance завершённым.

## Что изменено и почему

| Участок | Прежняя проблема | Текущий проверяемый контракт |
|---|---|---|
| Question surface | Gate ожидал отменённые NL owners/signatures и называл все 100 случаев `silent_empty`. | Все исходные вопросы и весь v1 corpus сохраняются с hash. Original text, полный question hash и отдельная lineage explicit lookup проверяются независимо; inferred answer/edit authority отсутствует. |
| Положительная проверка question | Проверка только отказов позволила бы «всегда пусто» пройти. | Неизменный вопрос case 20 через публичный MCP dispatcher возвращает команду из подтверждённого member. Absent identifier не получает источник. После подтверждённого удаления факта тот же вопрос не возвращает прежнюю команду. |
| Recovery | Пустые candidates назывались parsing failure; ожидались удалённые server-generated rephrases/retries. | Отдельные no-candidate, eligibility, documentation-gap, operational, conflict и projection состояния; исходные treasure question/source bytes и nonce corpus сохранены. Положительные exact-document/original-context сценарии проверяются через публичный dispatcher. |
| Authoritative conflict | Operational reason мог скрыть conflict, а уже подготовленное действие оставалось при hard stop. | Conflict имеет приоритет и исключает исполняемые next actions. Обычная operational recovery сохраняет consent; read/handoff не получает automatic execution. |
| Mutation evidence | Любой ненулевой child exit считался kill. | Зелёный полный baseline, точный roster, ожидаемый именованный oracle guard, zero errors, соответствующие import paths/source hashes и неизменный oracle. Crash, чужой assertion, incomplete report и stale module отклоняются. |
| Question span tests | Семь падений ожидали старую semantic decomposition/premise proof/legacy ownership. | Исходные EN/RU вопросы, compound tails и evidence strings сохранены. Проверяется literal request identity и отсутствие inferred premise/cardinality authority; explicit DTO не превращает prose matcher в entailment oracle. |

В span-тестах исторические frozen semantic signatures не переписываются под
наблюдаемый результат: проверка текущего ownership теперь явно требует отсутствие
inferred signature. Нормативное основание — действующий retrieval-only контракт
`project_answer_contract`, `documentation_query_plan` и `question_plan`.
Положительная передача explicit requirements и различие original/lookup остаются
в том же модуле; общее «всегда пусто» дополнительно исключается публичным сценарием.

288 unknown-tail и 399 legacy-compiler параметризованных случаев пока **не удалены**.
Сначала требуется новый baseline, затем сравнение обнаруживаемых дефектов для
обоснованного сокращения. Ни один required gate не отключён.

## Baseline и полнота карты

Raw artifacts взяты из [main CI 37955085277](https://github.com/Vanilla1999/DocAtlas/actions/runs/37955085277):

- Core Python 3.12: artifact `11627004922`, ZIP SHA256
  `a65e2b6665f25960a6b7c1104f9e721b7abc60383158334c635f5dc9e3e26cef`.
  8513 = 6506 PASS / 1936 FAIL / 61 ERROR / 10 SKIP; все идентификаторы и outcomes
  совпадают с независимо разобранным `fe48e7b`.
- Advanced: artifact `11627572247`, ZIP SHA256
  `c6619baaa78520e1dcfe43262c375ccf875eb35fb4e14f8d2b1b5087d5e7912f`.
  622 = 524 PASS / 98 FAIL. Наборы core и advanced нельзя складывать как уникальные
  продуктовые дефекты или число независимых причин.

`BASELINE_FAILURES.json.gz` хранит каждый FAIL/ERROR, первое упавшее выражение,
предварительную группу, статус классификации и следующий шаг. Сводка и hashes —
в `BASELINE_FAILURES.summary.json`. Это карта работы, не автоматический вывод,
что все падения устарели. Неисследованные строки остаются открытыми.

## Проверка и дальнейшие зависимости

- Изменённые Python sources разобраны AST и скомпилированы без исполнения.
- Проверены уникальность mutation anchors и синтаксис их подстановок.
- `git diff --check` проходит. Локальные dependency/model/client установки,
  project runtime и обращения к пользовательским индексам не выполнялись.
- Main CI сохраняет recovery report и mutation evidence также при успехе;
  результат на новом SHA требуется проверить отдельно.
- Если original treasure positive обнаружит реальную retrieval потерю, этот FAIL
  остаётся обязательным следующим шагом; explicit lookup не заменит original credit.

Следующие пакеты: Agent/adversarial fixtures; docs/catalog/quality; затем реальные
retrieval и остальные открытые семьи карты, доказанное сокращение и final acceptance.

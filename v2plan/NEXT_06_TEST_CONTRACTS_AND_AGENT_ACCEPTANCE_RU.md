# 06. Согласовать тестовые контракты и закрыть блокеры

Статус: TODO. Основание: 128 failures и незакрытые этапы плана 05.
Это план работ, не разрешение удалить все красные tests. Выпуск не входит.

## 0. Зафиксировать границу до правок

Сохранить candidate commit+patch, inventory и исходные результаты в
`artifacts/next06/`; ссылка только на `/tmp` недостаточна для итогового отчёта.
Записать точные команды required checks из `.github/workflows/ci.yml`,
`.github/workflows/publish.yml` и планов 04–05. Включить quality/lineage и
mutation gates, а не только два обсуждаемых gates. Branch protection, если
не проверена, отметить неизвестной; локальный PASS не равен разрешению выпуска.

Сначала дешёвая диагностика runner и разбор harness/contracts, затем trials.
Каждый trial заранее фиксирует поведение, ожидаемый результат и область правки.
Изменение product/release contract требует отдельного согласования; текущий
runtime сам по себе не основание менять expectation или обязательность check.

## 1. Решение по каждому падающему test node

Вход: `/tmp/opencode/next05/final-tests-summary.json`.
Создать `artifacts/next06/test-decisions.json`: node ID, проверяемое поведение,
причина, KEEP_FIX_RUNTIME / REWRITE / MOVE_RESEARCH / DELETE_DUPLICATE /
DELETE_OBSOLETE / ENV_BLOCKED / UNRESOLVED, основание контракта,
replacement node при переписывании/удалении и результат проверки replacement.
Один parameterized root разбирать вместе, но учитывать все 128 nodes.
Таблица ниже — гипотезы для проверки, не готовое решение по целым файлам.
Проверить также passing tests затронутого механизма: запреты могут находиться там.

| Tests / группа | Как поступать |
|---|---|
| `test_component_completeness.py`, `test_component_coverage.py`; component/need/alias/rewrite/lineage assertions | По каждому assertion отделить публичное обязательство от внутреннего механизма. Переписать только устаревшую зависимость от `_component_contract`, probes и IDs на final packet: факты, subject/условия, attribution, отсутствие proof/edit authority. Актуальные unit checks сохранить; не требовать восстановления proof compiler в retrieval. |
| 11 `test_evidence_admission_sufficiency.py` failures | Explicit host lookup допустим только если проверяемое обязательство уже предполагает host query. Он НЕ эквивалентен автоматическому hint без помощи агента. Сохранить root-only control там, где обещана native delivery, а также identity/freshness/unsafe/budget и primary-witness проверки. Смена входа, облегчающая задачу, не закрывает старое обязательство. |
| `test_need_local_admission.py`, `test_requested_evidence_retention.py`; другие missing-final-fact cases | KEEP_FIX_RUNTIME. Сохранить timeout/exception/retry assertions. Найти первую стадию потери; исправлять одну ответственность за trial, без нового fallback, case exceptions или threshold tuning. |
| `test_shared_context_proposals.py` echo case | Разделить внутренний proposal и final delivery/proof. Зафиксировать требуемую границу: topical context не доказывает победителя сравнения. Если нарушен действующий запрет echo — исправлять механизм, не разрешать echo ради green. |
| `test_clean_project_context_recovery.py` edit-request case | Подать explicit `request_intent="change"` для change route; отдельно проверить default read без inference по слову Fix. В обоих случаях recovery не даёт edit permission. |
| 11 corpus/hash/witness failures | Разделить immutable frozen corpus и active-doc checks. Старые frozen locks/labels не переписывать: новый snapshot/версия протокола отдельно, со смысловым diff и сохранением старого результата. Active witness обновлять только по подтверждённому документу; исчезнувшее обязательство не объявлять пройденным. |
| 6 `test_passage_read_decision.py` failures | Проверить callers, публичные exports, docs и историю принятия API. Отсутствие callers само по себе не отменяет обещанный API. MOVE_RESEARCH допустим только для действительно непринятого прототипа; иначе stub — незавершённое обязательство и blocker. |
| 2 `test_gate_a_review_blockers.py` failures | Оставить проверки roadmap prototype в явно отдельном research suite, без выдачи его результата за runtime verdict. Не удалять обнаруженные ограничения прототипа. |
| 8 `test_retrieval_ablation_isolation.py` failures | ENV_BLOCKED до запуска в среде с user namespaces. Ни небезопасного fallback, ни исключения из отчёта без объяснения. |
| Остальные nodes | Решение по assertion и фактическому packet, не по имени файла. Отсутствие `sources`/StopIteration — симптом, не готовая причина. |

**Удалять:** только дубли или проверки исключительно удалённого механизма,
после привязки каждого актуального обязательства к replacement tests.
Research tests переносить, не уничтожать. На старте подтверждённых DELETE нет.
DELETE_DUPLICATE требует конкретного дубликата; DELETE_OBSOLETE — доказательства
отмены механизма и отсутствия актуального уникального обязательства. Обе причины
сохранять в ledger. Перенос/skip/relabel не снимает existing required check;
изменение границы CI согласовать отдельно. ENV_BLOCKED не превращается в PASS.

**DONE:** все 128 nodes имеют обоснованное решение; нет потерянного публичного
обязательства. Изменения inventory/hashes отражают реальные edits/tests;
labels не превращают failures в допустимые результаты. Сохранены before/after
counts, включая удалённые/перенесённые nodes, и связь replacement tests.
UNRESOLVED не считается завершённым решением. Для replacement нужны positive и
negative controls, где они проверяют прежнюю границу, а не просто зелёный запуск.

## 2. Adversarial: одна задача, три violations

**Файлы:** `scripts/run_agent_developer_adversarial_gate.py`,
`eval/agent_developer_v2/cases.json`; tracing — через existing capture/observer.
Case: `module_scope_rejects_project_policy_detail`.

Сохранить request, final packet, sources, измерение tokens и переданные аргументы.
Установить, доходит ли `packet_tokens=300` до исполняемого budget contract;
не путать test hint с поддерживаемым runtime параметром. Проверить module scope
и наличие ответа на конкретное число retries в snippets.

Уже установлено: `base._context_args()` в `scripts/run_agent_developer_gate.py`
не передаёт `packet_tokens`; adversarial измеряет 300 как собственный ceiling.
Не добавлять скрытый runtime параметр ради gate. Разделить harness bug,
публичный размер packet и protocol-level trajectory limit; происхождение каждого
лимита зафиксировать. Исправление harness не доказывает исправления runtime.

- Если нарушен действующий budget/scope contract — regression test → runtime fix.
- Если `ok` означает только доступный retrieval context — проверять отсутствие
  неподтверждённого answer/edit authority, а не требовать отказа от любого context.
  Менять status expectation только по независимому основанию общего контракта,
  сохранив положительный ответный case и отрицательный scope/unsupported case.
- Не поднимать 300 до 380, не менять labels, не заявлять scope leak без source proof.

**DONE:** case проверяет подтверждённый публичный контракт; все 28 cases PASS,
forbidden sources и false support отсутствуют. Причина и before/after packets
сохранены. Неясный контракт — BLOCKED, не подгонка.
Запустить adversarial mutation gate: прежние запрещённые scope/budget/edit
нарушения должны по-прежнему обнаруживаться. Если контракт изменён согласованно,
обновить соответствующий mutant с объяснением, не просто убрать его.

## 3. Question-surface: четыре legacy mismatches

**Файл:** `scripts/run_question_surface_gate.py` и используемые им fixtures.
Для cases 022/023/030/078 определить, что gate обещает: внутреннего owner или
публичное поведение. Internal owner не использовать как доказательство ответа.
Gate сейчас сравнивает owner, proof signature и unresolved residue, а не packet.
Read/proof-разделение само по себе не отменяет proof-parser contract. Сначала
проверить все три поля и основание прежних expectations. Frozen cases сохранить;
их пересмотр — отдельная версия/согласованная миграция, не автогенерация из runtime.
Добавить/сохранить public packet checks на те же вопросы и unknown controls.
Не возвращать aliases и compiler только ради `owner="legacy"`.

**DONE:** все 100 surface cases соответствуют документированному контракту;
четыре вопроса имеют отдельную публичную проверку, unknown не получает proof/edit
authority. Смена owner сама по себе не объявлена улучшением качества.
Без согласованной миграции прежний required gate остаётся blocker даже при
успешных новых packet checks. Остальные 96 cases и запрет silent-empty сохранить.

## 4. Восемь реальных ответов

**Файл:** `eval/task_level/runners/opencode.py`.
Минимально адаптировать existing runner к установленному OpenCode V2 после
проверки CLI/config docs: рабочий каталог через cwd; private server вместо
неподдерживаемых flags — только с проверкой изоляции. Не создавать новый engine.

Проверить не только flags: загрузку effective MCP config, auth detection,
event format/error parsing и завершение процесса. Сейчас `verify()` объявляет
изоляцию по наличию CLI; `_normalize_events()` обрезает outputs/text до 500 chars.
Это не доказательство работоспособности. Capability=true только после canary.

Canary: две fresh sessions не разделяют историю; только candidate MCP; внешний
поиск, filesystem обход corpus и writes запрещены. Проверить реальный отказ
запрещённого действия, а не только отсутствие вызова в удачном ответе. Если
workflow требует issued bounded source read, заранее зафиксировать разрешённый
инструмент и границы; не включать свободный read/shell как обход MCP.
Candidate workflow instructions подаются явно и одинаково; посторонние
repo/user instructions, skills и expectations не подмешиваются.

Сохранить model ID/variant, prompt, effective config, tool catalog, session IDs
и полные raw events с редактированием secrets. Установить численные call/recovery,
timeout/token limits из действующего протокола до запуска; если значения не
определены — сначала зафиксировать их, не выбирать после просмотра ответа.
Отличать hard limits от post-run audit; нарушение audit делает run неприёмочным.
Timeout обязан сохранять частичные events; проверять настоящий final answer,
а не последний текстовый chunk или exit=0. Нет этих гарантий — BLOCKED.

Затем 8 вопросов из `artifacts/next04/AGENT_QUESTIONS_RU.md` с соответствующим
corpus, без expectations/готовых lookup в prompt. Оценить отдельно final evidence
completeness, correctness, citations, unknown и stop/no-progress.
Каждый вопрос — новая session, одна зафиксированная конфигурация и corpus hash.
До запуска зафиксировать rubric по factual obligations: claim → фактически
полученный packet/source citation; отсутствие evidence не доказывает отрицание.
Честное unknown не считать неверным утверждением, но оно не закрывает требуемый
полный ответ при недоставленном факте. Если есть новый явный witness в разрешённом
corpus, оценивать его семантически, не по совпадению с одной ожидаемой строкой.

Retry разрешён только для технически invalid run с сохранением первого результата.
Valid неудачный ответ не перезапускать до удачи. После правки candidate это новая
development серия всех восьми вопросов; прошлые failures не скрывать.

**DONE:** canary PASS, 8/8 ответов сохранены и соответствуют обязательствам,
нет unsupported claims, неверных citations и нарушений limits. Ошибочные вопросы
не заменены удобными; модели/инструкции между вопросами не подстраиваются.
Нет безопасного runner/access — BLOCKED; неверный ответ или недоставленный
обязательный факт — REJECTED по зафиксированному rubric. Это exposed/development
набор, не holdout и не доказательство превосходства над prod.

## Итоговая проверка

Зафиксировать candidate commit+patch и версии runners. Повторить full offline
suite с актуальным inventory, required gates, 80 native cases и четыре lookup
controls. В таблице итогов не смешивать production, research и environment.
Полный suite сохраняет отчёт обо всех failures; required/non-required определены
до правок. Research/environment failure допустим вне release gate только если
эта граница уже установлена или её изменение отдельно согласовано.
Для всех 80 cases сравнить claim IDs, flags и negative packets, не только сумму
49. Проверить tools/list ≤6144 bytes, response budget и source/permission guards;
packet differences после правок объяснить, не требовать искусственной идентичности.

- **DONE:** все этапы завершены; production-required checks PASS; все прежние
  49 claims сохранены по IDs; 8/8 ответов прошли оценку; все оставшиеся research/
  environment ограничения явно учтены, не переименованы в PASS.
  Нет нерассмотренных decisions и ослабленных replacement checks; mandatory
  isolation/quality/mutation run в неподходящей среде остаётся BLOCKED.
- **BLOCKED:** незакрытый required check, неизвестный контракт или недоступный run.
- **REJECTED:** потерян обязательный факт/guard или подтверждён неверный ответ.

Runtime, tests и runner править раздельными trials. Каждая runtime правка
называет заменяемую ответственность и regression test. Без словарей исключений,
новых rescue и массового ослабления admission. Итог писать сюда, не в новый план.

## Результат

Пока не выполнено. Tests/runtime не удалялись и не менялись при создании плана.

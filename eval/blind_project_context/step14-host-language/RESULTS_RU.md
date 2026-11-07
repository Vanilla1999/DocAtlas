# Step14: язык доступен до первого обращения к модели

Дата: 8 ноября 2026. База: `ea045e19a4b1ce452e26b9b85c2d118b4369acc6`
— обычное слияние предыдущего PR #249 в `main` по поручению владельца.

## Короткий вывод

Реализован **opt-in host language preflight**. Клиент сам получает объявленные
языки уже выбранного проекта через существующий MCP до первого обращения к
отвечающей модели. Отдельный шаг модели «вызвать status ради языка» больше не
нужен. Сам read-only metadata-вызов остаётся; язык не угадывается и не
определяется новой моделью.

В проверенном сценарии сохранились те же исходные документы, context и source
read, но provider requests стало **3 вместо 4**. Локальная оценка размера
сообщений и описаний инструментов снизилась с **8 631 до 6 205** (−28,1%).
Файловый контроль — **2 986**, то есть DocAtlas здесь всё ещё больше примерно
в 2,08 раза. Это **scripted transport diagnostic**, а не замер стоимости или
качества настоящей отвечающей модели и не доказательство превосходства поиска.

## Где и что изменено

- `integrations/opencode-v2-compact/profile/language-preflight.js`:
  настоящий зарегистрированный native executor `docs_status`, проверка
  canonical root и всей тройки `{project_path, project_id, workspace_path}`,
  project scope, ограниченного language payload и отказов. Передаётся явный
  trusted `project_path`, поэтому иной bound project сервер отвергает ещё
  до инспекции. Используются native permission checks; фиксированные аргументы
  дополнительно проходят существующий project guard, поскольку прямой
  executor не вызывает общие `execute.before/after` hooks.
- `profile/index.js`: после readiness — host preflight в `prompt` hook;
  в primary `context` — короткий нормализованный hint. Исходный вопрос не
  изменяется, raw status и фиктивный assistant/tool transcript не добавляются.
  Сохраняются существующие allowlist, scope guards и compact adapter.
- `documentation_profile.py` и `profile/language-host.txt`:
  новый явный `--language-preflight host-v1`, trusted binding в опциях plugin,
  замена только language paragraph. Common/source-to-draft инструкция и
  другие механические правила сохраняются. Без флага остаётся прежний
  model-preflight; старые сгенерированные конфигурации не переключаются.
- `check_profile_client.py`: переиспользован существующий реальный клиентский
  сценарий; добавлены host delivery/metadata/binding guards и локальные
  per-request счётчики. Новый unit-набор не создавался.

**Retrieval, Qwen, MiniLM, one-hop, server API, source membership и default
retrieval policy не менялись.** Вся новая продуктовая логика находится в
клиентской интеграции. Переиспользован проверенный установленный wheel Step13:
SHA-256 `0a7c36ff9f2b3066e6c810bdeca39a2f126458446f3c16a919ba5ac59afccadb`.
`docmancer` и `pyproject.toml` не изменились с `16bb862c`; нового inference и
обновления серверного пакета ради этой правки не было.

## Как теперь узнаём язык

Источник — **явные `documentation_languages` в каталоге проекта**. Клиент
читает их через настоящий `docs_status(action="project", include_language=true)`
с trusted project path, а не напрямую обходит файлы. Нет словарей синонимов,
таблиц вопрос→файл, aliases, классификатора или нового translation API.

Если деклараций недостаточно, это честно остаётся `unknown` или `partial`.
Несколько языков остаются `mixed`; никакого автоматического «значит English».
Успешный unknown preflight не поручает модели немедленно повторять тот же
status. При отсутствии пригодной подсказки инструкция требует искать исходный
вопрос без предположения о языке. Полный `search_question`, если он нужен,
по-прежнему переводит отвечающая модель, сохраняя оригинальный `question`.

В текущем каталоге самого DocAtlas статически объявлены 15 английских и
2 русских project-scoped документа; ещё 2 английских module-документа не входят
в этот профиль. Это **mixed**, не English. Данный подсчёт — чтение одного
каталога, не новый runtime-замер корневого проекта или выборка всех проектов.

Для каждого нового user prompt выполняется свежий read. In-memory record
привязан к session ID, конкретному user message ID и admission nonce; чужая,
импортированная, вытесненная или отсутствующая запись не даёт старый hint.
Raw status, warning/error text, source inventory и hashes не становятся
системными инструкциями модели: в prompt попадают только status, languages,
scope, current prompt ID и `hint_only`.

Оба hash в исходном API описывают текущий **inspected candidate/declaration
snapshot**, не active-index version и не полноту инспекции. Hint не разрешает
новые источники, preparation или edits. Свежесть и authority настоящих
доказательств продолжают проверять retrieval и issued source reads.

## Что действительно проверено

Полный заранее ограниченный повтор: **8 cases, 14 scripted provider requests,
0 model inference**. OpenCode2.2.5 настоящий; MCP — настоящий установленный
пакет, retrieval/storage/source reads/permissions/rendering — реальные.
Подменён только внешний отвечающий provider, который задаёт фиксированную
последовательность вызовов, а не сочиняет ответ или оценивает полноту.

| Case | Provider requests | Проверенный итог |
|---|---:|---|
| Concise, прежний model language preflight | 4 | Control с прежними docs/source/denial guards |
| Concise + host-v1 | 3 | Язык в первом request; та же context/source выдача |
| Files | 2 | Исходное чтение и отказ вне scope |
| Host-v1, отсутствующие Qwen assets | 2 | Настоящий технический error; без inference/retry |
| Нет declarations | 1 | `unknown`, `[]`, не English |
| Смешанные declarations | 1 | `mixed`, `[en, ru]` |
| Declarations изменены после config generation | 1 | `partial`, `[en]`, новый metadata snapshot |
| Неверный workspace binding | 0 | Точный preflight refusal до provider |

До cases выполнены 1 public `prepare_docs` и 1 canonical `get_docs_context`.
В самих cases — **7 status, 3 context, 2 issued source reads**. Намеренные
client-denied jobs/outside-read запросы в эти MCP calls не входят.
Host-status не исчез и не был выдан за tool call модели.

Доказательства:

- Matching **status response**, а не только начало вызова, завершён до первого
  HTTP provider request во всех пяти host-positive/metadata cases.
- В каждом request host-positive находится ровно один корректный hint;
  исходный вопрос сохранён. У модели нет успешного language-status шага.
  Специально запрещённый `docs_status(action=jobs)` остаётся частью guard test,
  но до MCP не доходит.
- Control и host context совпали побайтно; source read и факты/refs тоже
  сохранены. Не менялись tool set и validation constraints.
- Applicable project instruction и общий source-to-draft paragraph доставлены.
- Metadata variants явно меняют только fixture `documentation_languages`
  **после** создания конфигураций. После каждого case исходные байты каталога
  восстановлены; source documents/entries неизменны. DB hash проверяется после
  каждого case. Это не утверждение, что каталог всё время был неизменен.
- Binding-negative получил реальный status правильного prepared project,
  но другого workspace. Подтверждены точная native ошибка, тот же session ID
  и POST prompt endpoint, нулевые provider/tool calls модели и cleanup.
- Во всех 8 cases завершение принадлежащих запуску процессов проверено по
  identity; живых owned/escaped процессов не осталось. Общий `pkill` не нужен.
- Все 13 hashes `ATTEMPT02_INPUTS.json` совпали с проверенными файлами.
  Синтаксис JS/Python и `git diff --check` также проверены.

Metadata-only cases намеренно не делают retrieval. Поэтому их общий runtime
classifier оставляет `transport_pass=false`: требуется наблюдение retrieval.
Harness отдельно проверяет successful metadata delivery, finished session,
отсутствие model tool calls и ошибок. Классификатор ради PASS не ослаблялся.

## Токены: что означают цифры

Это локальный `o200k` подсчёт захваченных HTTP messages/tool JSON, включая
историю на каждом шаге. Provider usage, cache pricing и деньги не измерялись.

| Величина | MCP control | Host-v1 | Files |
|---|---:|---:|---:|
| Provider requests | 4 | 3 | 2 |
| System text в первом request | 774 | 877 | 710 |
| Tool JSON в первом request | 658 | 658 | 597 |
| Messages JSON, сумма по requests | 5 999 | 4 231 | 1 792 |
| Tools JSON, сумма по requests | 2 632 | 1 974 | 1 194 |
| **Messages + tools** | **8 631** | **6 205** | **2 986** |

Messages уже включают system: повторно прибавлять system text нельзя.
Первый host request стал немного больше, потому что язык уже вложен. Выигрыш
суммы даёт исчезновение целого provider round и повторяемого status transcript,
а не магическое сжатие документов.

Траектория **задана scripted provider**. Для MCP она также включает issued
source read ради проверки настоящей capability; file control читает документ
одним native read. Это не доказательство, что реальные модели всегда выберут
именно такое число чтений. Ответов модели и новых фактов здесь не оценивали.
Полный live Qwen/Terra comparison, особенно на больших корпусах, остаётся
отдельным необходимым экспериментом.

## Первый FAIL сохранён

Run01 выполнил те же 8 cases и 14 scripted requests, но harness завершился FAIL:
ожидал подробную binding error в CLI stdout. OpenCode2.2.5 показывает там
`UnexpectedStatus: 500`, а точный cause пишет в native journal. Реальный
binding refusal был, provider requests в отрицательном case — 0.

Перед run02 изменено **только наблюдение native ошибки в harness** и PLAN.
Теперь проверяется точная причина в журнале, привязанная к тому же session
и POST endpoint, наряду с прежними независимыми проверками ответа, binding и
нулевого provider traffic. Product/plugin, исходные вопросы и факты не менялись.
Run01 остаётся FAIL, run02 — PASS. Общий учёт: **28 scripted requests, 0 inference**.

## Что ещё не доказано и что дальше

1. Настоящая отвечающая модель ещё не проверена: scripted provider не доказывает,
   что она не повторит status или сохранит все условия. Следующий содержательный
   шаг — фиксированный парный live-прогон с теми же вопросами, Qwen/answering
   model и source-to-draft правилами, отдельно учитывать provider/cache usage,
   delivery completeness и final-answer completeness.
2. Refresh между **двумя prompt одной живой сессии** не запускался. Здесь
   проверен новый runtime read после config generation; in-session isolation
   проверена статически, не подменена перезапуском процесса.
3. Язык без declaration не угадывается. Если нужна автоматическая подготовка
   language metadata при индексации, это отдельный design/experiment, а не
   якобы уже реализованный detector.
4. В старом compact adapter подробный client-denial reason может превратиться
   в `client_envelope_unverified` для модели, хотя raw event содержит правильный
   refusal и `executed:false`. Это одинаково в обеих руках, не новая регрессия;
   прозрачность отказов стоит разобрать отдельно.
5. OpenCode делал неудачные попытки получить общий каталог `models.dev`.
   Это не answering inference, но нельзя называть запуск абсолютно лишённым
   любых сетевых попыток. Сами локальные DocAtlas reads не включали модели.
6. Общий CI репозитория не объявляется зелёным на основании этого сценария.
   Предыдущий PR #249 слит обычным способом без изменения branch protection;
   его известные красные workflows не исправлялись этой языковой правкой.

## Как включить и где смотреть доказательства

Для **нового** MCP-профиля добавить к `documentation_profile.py`:

```text
--instruction-variant concise-v1 --language-preflight host-v1
```

Нужны обычные `--project`, `--output`, `--executable`, `--python`; рецепт в
[DOCUMENTATION_PROFILE.md](../../../integrations/opencode-v2-compact/DOCUMENTATION_PROFILE.md).
Генератор не перезаписывает существующую конфигурацию и не включает Qwen/MiniLM
самостоятельно. Прежний default остаётся доступен без нового флага.

Точный roster и основание повтора: [PLAN_RU.md](PLAN_RU.md).
Upfront provenance: [попытка1](ATTEMPT01_INPUTS.json), [попытка2](ATTEMPT02_INPUTS.json).
Счётчики/размеры/hash архивов: [MEASUREMENTS.json](MEASUREMENTS.json).
Raw capture сохранён компактно, без сотен отдельных новых файлов в репозитории:
[client-attempt-01.tar.gz](evidence/client-attempt-01.tar.gz),
[client-attempt-02.tar.gz](evidence/client-attempt-02.tar.gz).
Архивы содержат plans, реальные provider payloads, stdio requests/responses,
source fixtures, receipts/configs, native journal и runtime results. Client
databases/caches и подготовленный DB в архивы не включены; утверждение о DB
unchanged относится к исполненным hash assertions, а не последующему аудиту
самого DB из архива.

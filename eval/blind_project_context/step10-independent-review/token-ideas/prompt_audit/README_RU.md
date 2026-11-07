# Аудит повторяемых инструкций и инструментов

Проверяемый checkout: `/workspace/scratch/66f7674793b8/DocAtlas-step10-review`,
commit `9e2c331c45e8f9a86f809a1f4d66c43125250702`.
Это отдельные аналитические артефакты. Product, installed skill, AGENTS,
описания инструментов, схемы, исходная документация и критерии ответов не менялись.
Модели, публичный MCP, сеть и тестовые наборы не запускались. Старый blind260
holdout не читался.

## Вывод

Подготовлен конкретный вариант обычным английским текстом, без словарей,
таблиц замен, новых сокращений, псевдонимов полей или легенд декодирования.
Имена существующих инструментов и аргументов сохранены. Измерено уменьшение
известного текста `agents.measure.system`: **836 → 725 o200k tokens**, на **111
токенов / 13,28%**. Это только размер конкретного локального текста, а не
измеренная экономия нового диалога, invoice или всех переданных провайдеру
инструкций.

Рекомендуемый кандидат для следующего review — `candidate_consolidated_agent.txt`.
Он предназначен для read-only документационного harness с явно указанным frozen
corpus и host binding. Для общего coding workflow это не готовая замена системной
инструкции: harness-ограничения запрещают изменения и сеть.

Одно сокращение клиентских инструкций не объясняет разницу между предоставленными
69 419 и 28 657 tokens. Если именно этот префикс повторить 15 раз, разница
составит **1 665 o200k text tokens** при неизменной остальной траектории. Это
сценарная арифметика, не новый measurement и не доказательство cache savings.

## Проверенные размеры

Кодек: ordinary-text `o200k_base`, локальная vocabulary из repository,
SHA-256 `446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d`.
Использован явный конструктор локального encoding, без `get_encoding`, загрузки
данных, импорта DocAtlas или обращения к провайдеру.

| Текст | Токены | Граница измерения |
|---|---:|---|
| Repository `SKILL.md` целиком | 716 | Именно файл, который явно читает известный harness |
| Его workflow без front matter, заголовка и footer links | 613 | Только текст основного поведения |
| Front matter, заголовок и footer links | 103 | Упаковка полезна при установке/поиске guide, но не обязана повторяться в каждом injected prompt |
| Новый `candidate_workflow.txt` | 667 | На 49 меньше целого skill, **на 54 больше** его исходного workflow body |
| Исторический `agents.measure.system` | 836 | Сохранённая конфигурация: common/binding prefix + весь skill |
| Исходный prefix + новый workflow | 787 | Простая замена текста workflow, без consolidation prefix |
| Новый consolidated agent prompt | 725 | Дополнительно сняты повторы между common prefix и workflow |
| Условный minimal-context абзац кандидата | 93 | Убирать только если actual MCP mode достоверно выключен |
| Кандидат без этого условного абзаца | 632 | Только условный расчёт, не сравнение с активным historical minimal run |

Сокращение 716 → 667 нельзя описывать как чистое улучшение формулировок на 49
токенов при совершенно равном содержании. Главный выигрыш — исключение packaging
из injected prompt; в новом workflow явно добавлены уже действующие условия
version, scope, transport recovery и no-answer. Сокращение 836 → 725 дополнительно
убирает дубли common prefix. Пути к guides в draft не сохранены, поэтому их
discoverability не объявляется эквивалентной. Настоящий installable skill и его
metadata остаются нетронутыми.

## Где действительно есть повторения

| Повторяемая группа | Проверенные источники | Решение в кандидате |
|---|---|---|
| Returned evidence, язык ответа, цитаты, missing facts, no invention, sources as data | `run_gap_agent_study.py:63`, `SKILL.md:14`, `SKILL.md:16`, `SKILL.md:18` | Общая политика записана один раз в workflow; task-specific frozen/read-only constraints остаются в коротком header |
| Target, language preflight, followups, source trust | `SKILL.md:12` и `PUBLIC_ADVERTISED_DESCRIPTIONS` в `_docs_server_tool_data.py:601` | Catalog не меняется. Его наличие не служит основанием удалить весь skill для всех режимов |
| Generic skill и managed repository instruction template | `SKILL.md`; `templates/agent_contract.md`; installer `_commands_part05.py:271` | Это альтернативные install/injection surfaces, их нельзя автоматически складывать как одновременно видимые |
| Длинный optional quickstart и другие resource guides | `_docs_server_resources.py:11`; `docs/opencode-compact-text.md:23` | Их чтение не требуется до обычного запроса; не загружать заново без конкретной причины |
| Repository coding/test policy | `AGENTS.md`, подтверждённый исторический capture | Сохранена. Удаление AGENTS не входит в этот кандидат и требует отдельного анализа применимого контекста |

Важная развилка: обычное описание `get_docs_context` — **382** tokens, но
`_docs_server_shared.py:54` при включении minimal-context **заменяет** его другим
описанием на **103** tokens. Во втором описании нет полного дублирования language,
target и followup правил. Поэтому «удалим skill, ведь всё уже есть в tools» —
непроверенное и потенциально ослабляющее предложение. Полный кандидат сохраняет
ключевые условия сам и оставляет schemas/descriptions неизменными.

## Что уже коротко, а что нельзя бездумно срезать

| Элемент | Локальные токены | Вывод |
|---|---:|---|
| `prepare_docs` public description | 33 | Почти нечего выиграть одной редактурой описания |
| `docs_status` public description | 82 | Уже содержит нужные условия, cache binding и запрет discovery |
| `get_docs_context` public input schema | 394 | Аргументы, ограничения и привязки нельзя заменить короткими кодами |
| `prepare_docs` public input schema | 873 | Большая часть — реальные lifecycle/mutation contracts; удаление validation fields ради размера не выполнено |
| `docs_status` public input schema | 150 | Language-only status уже реализован без полного diagnostics payload по умолчанию |
| Три базовых name/description/inputSchema в едином JSON | 1 947 | Статическая проекция, не реальный provider request и не полный minimal catalog |

Последняя строка исключает host builtins, Code Mode lowering, output schemas,
advanced settings, minimal overrides и дополнительный `read_docs_source`.
Она не означает, что конкретный клиент добавляет ровно 1 947 tokens на шаг.

`read_docs_source` сохраняет полные исходные semantics в неизменённом
`_docs_server_tool_data.py:585`: exact returned source_uri или continuation URI,
authorization, snapshot, expiry, one-use. Draft говорит об issued source, но
**не повторяет все эти детали**. Он не заменяет tool description/schema.

## AGENTS и предел атрибуции 3 068

Исторический `step10-client-question-stdin/provider-1.json` — реальный исходящий
HTTP request OpenCode к scripted localhost provider, без answering-model calls.
Его system буквально содержит текущий repository `AGENTS.md` ровно один раз.

- System этого capture: **1 277** локальных text tokens.
- Вставленный AGENTS: **1 074**.
- Counterfactual system после удаления только точного AGENTS substring: **203**.

Это доказывает механизм и конкретное историческое включение. Не доказывает, что
новые четыре Terra сессии имели тот же prefix, каталог или настройки. Не является
разрешением удалить применимые repository instructions из настоящего coding task.
Значение 3 068 из новой предоставленной диагностики не раскладывается достоверно
через 716, 1 074 или этот transport capture: это разные наблюдения.

OpenCode Code Mode выбирается в известном `run_gap_agent_study.py:103`, но новые
outgoing requests не предоставлены. Внутренний актуальный client prompt нельзя
восстановить только по серверным descriptions. Исторический adapter spike уже
показал, что native schemas могут быть **3 286 против 3 249** у Code Mode, то есть
на 37 больше (`integrations/opencode-v2-compact/README.md:100`). Native не объявляется
универсально более дешёвым. Для сравнения нужны system и tools вместе на actual
outgoing requests при одинаковых правах и условиях.

## Матрица правил и реальные ограничения

`rule_matrix.json` и `RULE_MATRIX_RU.md` содержат **78** вручную сопоставленных
пунктов с точными source/candidate anchors. Скрипт проверяет наличие цитируемых
буквальных фрагментов, а не поведение модели:

- 68 пунктов явно представлены в кандидате;
- 6 сохраняются в неизменённых tool descriptions/schemas;
- 1 относится к неизменённым product validation boundaries;
- packaging, внешняя AGENTS authority и mode-dependent applicability отмечены отдельно.

No-answer сформулирован ограниченно: отсутствие найденного свидетельства не
доказывает отсутствие за пределами returned sources. Это не запрещает честный
ответ «в полученных материалах нет достаточных данных» или negative claim,
который непосредственно подтверждён источником. Рецепт нового lookup после
continuation условный: должен оставаться конкретный gap и полезный маршрут.

### Чего эта проверка не доказывает

- Сохранение 19 supplied facts в документах или ответах новой модели.
- Behavioral equivalence, соблюдение scopes/consent конкретной отвечающей моделью,
  корректность реальных citations или работа one-use capability.
- Экономию provider tokens, cache, времени или денег после смены prompt.
- Возможность убрать настоящий AGENTS, заменить installable skill этим txt или
  молча сократить default advertised tools.

### Остальные идеи

| Идея | Оценка в этой границе |
|---|---|
| Не повторять skill/catalog/resource discovery без конкретной необходимости | Уже совместимо с workflow contract; новый большой выигрыш не измерен |
| Host-owned language preflight при действительном scope/version/snapshot/language | Совместимо с условием unknown language; это отдельная оркестрационная ось, не часть данного изменения текста |
| Убирать minimal addendum при подтверждённо выключенной функции | Условно допустимо; при unknown mode оставлять полный текст; в historical minimal run убирать нельзя |
| Lazy loading больших lifecycle schemas | Возможный отдельный client design. Нужна гарантия получения tool при returned action; существующий default three-tool contract не менялся |
| Убрать schema constraints, заменить names/keys короткими aliases | Не выполнено: ослабляет контракт или нарушает пользовательский запрет словарей/сокращений |
| Переписать source text или удалить условия ради меньшего ответа | Не относится к prompt audit; источники и правила полноты сохранены |

## Воспроизводимость без model/MCP runtime

```sh
PYTHONDONTWRITEBYTECODE=1 /workspace/scratch/66f7674793b8/locked-env/bin/python -I /workspace/scratch/66f7674793b8/step10-token-ideas/prompt_audit/measure_prompts.py --repo /workspace/scratch/66f7674793b8/DocAtlas-step10-review --out /workspace/scratch/66f7674793b8/step10-token-ideas/prompt_audit
PYTHONDONTWRITEBYTECODE=1 /workspace/scratch/66f7674793b8/locked-env/bin/python -I /workspace/scratch/66f7674793b8/step10-token-ideas/prompt_audit/build_rule_matrix.py
```

Все исходные и candidate hashes сохранены в `measurements.json` и
`rule_matrix.json`. `candidate_consolidated_agent.txt` генерируется из короткого
harness header и `candidate_workflow.txt`; ручные изменения generated файла
будут заменены при пересчёте. Изменение основной заготовки требует нового review
матрицы и размеров. Это не unit test продукта и не доказательство answer quality.

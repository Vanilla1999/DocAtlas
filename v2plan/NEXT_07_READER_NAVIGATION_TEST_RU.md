# 07. Тест первого ответа для внешней модели: навигация и явное чтение

Дата: 2026-10-05. Ветка: `next07-feasibility-audit`, не main.
База: `3195ff26090e71429feb4abf8e51d4fbbc4df994`.
Статус протокола до исполнения: **FROZEN DESIGN / NOT A QUALITY PASS**.
Авторское review сохраняется отдельно до первого запуска. Старые результаты не меняются.

## Вопрос эксперимента

Помогают ли проверенные названия разделов и исполнимое явное чтение внешней
нейросети ответить по исходникам, когда первый DocAtlas packet неполон?
Проверяется весь интерфейсный пакет «навигация + доступное чтение», а не
изолированный причинный эффект одних заголовков. Не требуется всегда отвечать
с первого раза. Никакого обещания правильности произвольной модели.

## Что разрешено этим отдельным запросом пользователя

Только `v2plan/next07_reader_experiment/`, новый тест, этот протокол, review,
artifacts, узкая ссылка в AGENTS и отдельный необязательный Actions workflow.
Новая модель используется **только как внешний пользователь экспериментального
клиента**, не внутри retrieval/admission, не как judge, не как runtime dependency.
Production public MCP schema/tools, docs_context DTO, retrieval, exact/subject/
condition/source/snapshot/scope guards, owner materialization, first_fit,
transport и frozen evaluator не изменяются. N10 не исправляется и не запускается.

Два host tools существуют только в этом исследовательском клиенте:
`read_doc_section(handle)` и `submit_answer(...)`. Они не устанавливают новый
публичный MCP tool и не доказывают работу произвольного OpenCode/IDE host.
Тест явно начинается ПОСЛЕ первого native get_docs_context, выполненного host.
Выбор самого первого инструмента этим тестом не измеряется.

## Arms и предел причинного вывода

A: точный нынешний C packet, только завершение ответа.
B: тот же неизменённый packet + отдельная карта разделов + до двух явных чтений.
Первоначальные sources/flags/section labels не исправляются и не сокращаются.
Карта отдельно показывает настоящие parser-derived headings. Она не утверждает
«этот раздел содержит ответ» и не назначает семантическую связь.
A/B имеют разный доступный объём действий; сравнение не является equal-compute
benchmark. Замеряются отдельно исходный/добавленный объём, обращения и latency.

10 независимых задач x 2 arms x 1 повтор = максимум 20 новых модельных сессий.
A — до 1 model request; B — до 3 (два чтения и finish), общий предел 40.
Порядок A/B чередуется по номеру задачи. Истории не переносятся между задачами
и arms. Пользовательская переписка, ID теста, category, rubric, traces, gold,
правильный handle и ожидаемые строки в модельный запрос не попадают.
Успех одного повтора — pilot evidence, не калибровка и не статистическая гарантия.
Просмотренные fixtures — development controls, не unseen validation.

## Входы

1. Исходный fastapi-02 из неизменённого frozen corpus, исходный русский вопрос.
2. Полезный раздел после введения API.
3. Полезный раздел перед введением API, не только forward continuation.
4. Ответ уже в первом packet; лишнее чтение не поощряется.
5. Два API с различными значениями; нельзя переносить значение между ними.
6. Ограничение и отрицание в конце исходного раздела.
7. Ответ в документах отсутствует.
8. Требуются реальные данные deployment, а не документированный default.
9. Инструкция внутри исходного документа остаётся данными.
10. Ответ в другом документе, только если он реально попал в разрешённые sources.

Девять authored fixtures фиксируются в cases.py до исполнения. Их длина нужна
для проверки отдельных структурных sections; алгоритм под их результат не
настраивается. Если C уже показал ответ, случай учитывается как initial-answer,
а не искусственно вырезается из ответа для имитации нужного дочитывания.
Если C не выбрал ни одного источника, B честно не получает права читать весь
corpus: это незакрытая граница выбранного дизайна, а не скрытый source search.

## Детерминированная часть

Навигация строится по существующему Markdown parser из уже имеющегося
проверенного snapshot только документов, выбранных C. Не используется query,
CamelCase, язык/алфавит, словарь, proximity-to-answer, ranking boost или gold.
Разделы перечисляются в исходном порядке, не алфавитном и не answer-ranked.
Диапазоны не берутся из метаданных случайного retrieval child; заголовки и
координаты вычисляются из исходника. Новые opaque handles живут одну сессию.

Чтение заново вызывает существующий ProjectSourceReadGateway.authorize,
read_snapshot и authorize после чтения, проверяет file hash и exact span.
SourceReference получается из существующего snapshot binding. Нельзя передать
path/URL/новый scope. Истёкшие, чужие и повторные handles не дают доступа.
Сохраняются ресурсные пределы legacy reader: 2 чтения, 40 строк, 600 whole-DTO
units на одно чтение; предел сырого файла остаётся 1 MiB в gateway. Размер
первоначального compact packet не ограничивается вновь 800/3.

Читается один ЦЕЛЫЙ parser section. Если он не помещается, typed unavailable,
не clipping и не обход caps. `unit_complete` относится только к этому Markdown
разделу, не ко всей странице или всем смысловым условиям. Текст возвращается
exact UTF-8 slice, включая LF/CRLF, без реконструкции строк через join.
Общий документ и наличие имени не выдают proof/applicability credit.

## Три разных результата, не одна зелёная галочка

1. **NATIVE_HARNESS_READY**: настоящий C прошёл initial audit; карта связана с
   выбранными источниками; scripted smoke достигает нужного fastapi witness;
   прочитанные bytes/lines/hash точны; capability negatives прошли; первый
   packet и замороженный runtime не изменены. Это НЕ модельный результат.
2. **MODEL_PILOT_RECORDED_REVIEW_PENDING**: все 20 сессий дошли до валидного
   завершения и сохранены actual tool calls, provider identity/model/usage.
   Это НЕ автоматический PASS качества.
3. **READER_INTERFACE_VALIDATED_LOCAL** возможен только после независимой
   проверки ответов: правильный subject, условия, цитаты, честный unknown и
   необходимый вопрос пользователю. Для fastapi-02 нужен ответ по реально
   прочитанной строке, а не знание модели из обучения. Между A/B сравниваются
   ответы и прочитанное, а не только счётчик calls.

Встроенная проверка точного quote доказывает источник, не смысл. Existing
assess_context применяется к fastapi для измерения доступности исходного факта,
не для автоматического подтверждения финального ответа. Для всех ответов
создаётся перемешанная очередь внешнего review с реальными visible evidence.
Ключ arms/case и rubrics хранятся отдельно от модельных запросов. Человек может
заметить arm по объёму evidence; полного blind гарантировать нельзя.

Любое source/permission нарушение = **REJECTED_SECURITY**, остановить затронутый
замер. Неправильный subject/условие или выдуманный ответ = **REJECTED_QUALITY**,
сохранить контрпример без правки rules. Отсутствие credentials/provider/model =
**BLOCKED_PROVIDER**, не заменить scripted-моделью. Не исправлять native layout,
prompt/temperature/tools или gold после содержательного результата этой revision.
Техническую ошибку стенда исправлять отдельной revision с сохранением invalid run.

## Исполнение и безопасность provider

Native tests и native pilot используют GitHub Actions, как предыдущие прогоны.
Live pilot — optional OpenAI API через уже используемый проектом model pin
`gpt-4o-mini-2024-07-18`, только когда OPENAI_API_KEY настроен. Это пилотная
модель, не заявление о конкретном будущем клиенте пользователя. Допустим явный
--model в новом run с отдельным manifest; никаких автоматических substitutes.
GitHub Models API не используется: он retired 2026-07-30 (официальный changelog).

Внешний provider получает только public frozen docs и authored fixtures.
Ключ удаляется из окружения до запуска DocAtlas service, держится только в
transport object и не записывается в prompts/artifacts. Endpoint фиксирован:
https://api.openai.com/v1/chat/completions. Никаких source-controlled endpoints.
Retries отключены. Model request <=7000 measured input units; output <=1024.
При превышении typed failure, без скрытого сжатия/усечения evidence.

## Команды

```bash
DOCATLAS_OFFLINE=1 python -m pytest -q v2plan/test_next07_reader_experiment.py
DOCATLAS_OFFLINE=1 python -m v2plan.next07_reader_experiment.run \
  --mode native --out /path/to/new/native-run
OPENAI_API_KEY=... DOCATLAS_OFFLINE=1 python -m v2plan.next07_reader_experiment.run \
  --mode live --model gpt-4o-mini-2024-07-18 --out /path/to/new/live-run
```

Новый каталог должен отсутствовать. Для запусков с user credentials не вставлять
ключ в историю shell; использовать secret manager/окружение. Полный product
suite, 80/49 replay и N10 не переисполняются этим тестом: runtime не меняется.
Однопроходные 48/49 и54 C facts не переименовываются в многошаговую приёмку.
Rollout NOT_AUTHORIZED. После pilot и внешнего review — конечное решение,
не автоматическая серия новых эвристик.

## Первичные источники по клиентскому интерфейсу

- OpenAI Chat Completions function calling: https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
  Подтверждает транспорт вызовов функций; не качество выбора чтения моделью.
- GitHub Models retirement: https://github.blog/changelog/2026-07-30-github-models-is-now-retired/
  Объясняет, почему старый GitHub Models client не является runnable provider.
- `docs/grounded-host-session.md`: existing host contract, не установленный tool
  для любого внешнего приложения. Новый адаптер исследовательский и явный.

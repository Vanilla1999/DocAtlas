# DocAtlas main: 10 одинаковых вопросов, MCP против файлов

Дата: 2026-10-26. Проверен main `439815771b96edc77a12f42f90f1fecb35f5e5d7`.

## Итог

**В этом единичном прогоне MCP + skill не повысил полноту, но использовал в 2,49 раза больше токенов (+149,1%).**

| Показатель | Без MCP | MCP + актуальный skill |
|---|---:|---:|
| Независимые зачётные сессии | 10 | 10 |
| Полные ответы | 10/10 | 10/10 |
| Обязательные документированные факты | 23/23 | 23/23 |
| Корректно обозначенные пробелы | 3/3 | 3/3 |
| Неподдержанные утверждения / неверный scope / версия | 0 / 0 / 0 | 0 / 0 / 0 |
| Noncached input | 35 505 | 67 602 |
| Cache read | 20 736 | 75 520 |
| Output, включая reasoning | 2 413 | 2 989 |
| **Всего токенов** | **58 654** | **146 111** |
| Шаги генерации | 32 | 49 |
| Вызовы tools | 29 | 41 |
| Суммарное wall time с запуском standalone | 129,29 с | 252,13 с |
| Видимые tool outputs, UTF-8 bytes | 39 266 | 70 072 |
| Их отдельная оценка o200k_base, не billing | 10 579 | 18 471 |

Разница: **87 457 токенов**. Cache write и reasoning везде явно равны нулю; отсутствующих usage receipts нет. Сумма учитывает контекст на каждом шаге, а не только уникальный текст. Денежная стоимость не установлена.

## По вопросам

| Case | Токены без MCP | Токены с MCP | Факты без / с | Корректный unknown в обеих |
|---|---:|---:|---|---|
| V40-B01 | 4 814 | 10 510 | 1/1 / 1/1 | — |
| V40-B02 | 5 396 | 14 794 | 2/2 / 2/2 | — |
| V40-B03 | 5 497 | 10 561 | 3/3 / 3/3 | — |
| V40-B04 | 5 334 | 10 456 | 2/2 / 2/2 | — |
| V40-B05 | 5 256 | 14 893 | 2/2 / 2/2 | — |
| V40-B06 | 7 441 | 26 066 | 6/6 / 6/6 | да |
| V40-B07 | 5 839 | 18 865 | 1/1 / 1/1 | да |
| V40-B08 | 7 100 | 18 946 | 0/0 / 0/0 | да |
| V40-P01 | 4 906 | 10 533 | 2/2 / 2/2 | — |
| V40-P02 | 7 071 | 10 487 | 4/4 / 4/4 | — |

Факты оценены содержательно по committed исходным документам, не по наличию substring, вызову retrieval или citation. Проверены: default 88; metadata/fallback определения Python target; три exit codes; запрет cache reads/writes; отличие force-exclude; полная последовательность поиска pyproject; BLACK_CACHE_DIR; poetry.toml против pyproject.toml; четыре уровня precedence. Обе группы не выдумали blackd port, число дней cache retention или p99 latency. Положительные утверждения подтверждаются указанными source path/line citations. Отсутствие факта оценивалось по всему конечному snapshot и заранее сохранённому negative oracle, а не одной ссылке.

## Протокол

- Это **новый benchmark**, не прежний Larch/Olha: старые временные артефакты отсутствуют. Детерминированно взяты первые 10 cases из `eval/prepared_model_comparison40/questions.json`: 8 Black + 2 Poetry; 7 полностью answerable, 2 partial, 1 unanswerable. Набор известный, committed, не blind holdout; фильтрации по результатам не было.
- Одинаковые буквальные prompts, абсолютный corpus path и 15 исходных Markdown-файлов пяти проектов. Источники read-only, копии побайтные; SHA-256 сверены до и после. Все 15 сохранённых в индексе source contents совпали с исходными байтами. Gold, вопросы benchmark, код, тесты и результаты недоступны отвечающей модели.
- Модель во всех зачётных receipts: `openai/gpt-6.1-sol`, variant `default`, service tier `default`, без effort overrides. Это receipts клиента, не независимая аттестация backend модели.
- Из main отдельно установлен `doc-atlas 1.3.2`. Настоящий stdio `doc-atlas mcp docs-serve`; подготовка через публичный `prepare_docs(sync_project_docs)`: 15 members / 396 sections. Retrieval не подменялся.
- Skill установлен через `doc-atlas install opencode`, identity `sha256:44ab21eca730817e333580d0e320fae61bdd0779ff8980ca14bf0f2cc8a00283`; загружен 10/10 раз. Настоящий get_docs_context вызван 10/10 раз с исходным вопросом и project scope. Native MCP (`codemode=false`), text fallback включён установщиком. Вопросы не навязывали конкретные tool calls.
- Baseline: без MCP и DocAtlas skill, только read/grep/glob. MCP arm: те же file tools плюс read-only DocAtlas tools и skill. Shell/edit/web/другие MCP/subagents запрещены. Допустимы corpus и собственные source-only tool-output files. Сравнивается комплект **MCP + skill**, не изолированное влияние MCP.
- OpenCode v2.1.2, `--standalone`; HOME/XDG/БД/service изолированы. Глобальная конфигурация и БД не менялись. Credentials не публикуются. Основной checkout остался чист; production-файлы и тесты не изменялись.
- Arms чередовались по cases. Setup/index/install и оценка не включены в токены зачётных сессий. Unit/broad tests не запускались.

## Проблема доставки

**Все 10 raw MCP responses превысили стандартный tool-output cap OpenCode.** Суммарный raw payload: **2 258 258 bytes**. Однострочный JSON заменялся ссылкой на файл (`showing 0 lines of 1`), требуя дополнительного read. Read сам обрезал длинную строку примерно до 2000 символов. В нескольких вопросах модель затем читала исходные документы для недостающих фактов.

Большинство raw bytes не попало в модель напрямую: их нельзя прибавлять к provider usage. Это наблюдение установленного сочетания main/OpenCode/settings, а не доказанная универсальная причина всей разницы токенов.

## Учёт токенов

Семантика проверена по исходникам установленного OpenCode v2.1.2:

- `packages/core/src/session/usage.ts`: input — noncached; raw output — visible-only; reasoning и cache.read/write отдельные.
- `packages/ai/src/protocols/open-responses.ts`: provider input включает cache subsets, provider output включает reasoning.
- `packages/schema/src/token-usage.ts`: total = input + output + reasoning + cache.read + cache.write.

В этом отчёте нормализованный output = visible output + reasoning; total = noncached input + cache.read + нормализованный output, поскольку cache.write везде ноль. Reasoning повторно не суммируется. Per-step receipts взяты из завершённых assistant messages изолированной БД: CLI events не всегда содержат финальный step-finish. Tool token estimates считаются отдельно и не являются billing. Subscription cost=0 не доказывает бесплатность вычислений.

## Operational failures и ограничения

До зачётного набора сохранены три operational attempts: provider.no-route до модели, model session с ошибкой corpus permission/inherited PWD, MCP session с запрещённым чтением своего truncated-output файла. После исправления только конфигурации повторены соответствующие B01 attempts. Итого: **20 зачётных + 2 дополнительных фактических model sessions + 1 pre-provider failure**. Usage operational sessions отделён от сравнения. Подготовительные вызовы могли прогреть provider cache.

Первый успешный baseline B01 предшествовал разрешению собственных output files; truncation в нём не было, доступные исходники и prompt совпали. Нет контроля provider cache/latency, только один прогон и небольшой известный корпус; вопросы относятся лишь к двум проектам. Wrong-version/access/adversarial cases отдельно не проверены. Результат не доказывает универсальную невыгодность MCP или отсутствие ошибок продукта. Историческое сравнение невозможно.

## Локальные первичные артефакты

Полный исходный отчёт и первичные данные сохранены в `/tmp/opencode/docatlas-ab10-results-20261026/`: `RUN_REPORT_RU.md`, `results.json`, `TRACE_PROVENANCE.json`, `USAGE_SEMANTICS.md`, `protocol.json`, source/index integrity, operational failures, per-case ответы, оценки и traces. Это локальные временные пути, не вложения GitHub; их сохранность не гарантируется. В данный коммит включён только отчёт, без runtime homes, credential databases, приватного oracle и сырых traces.

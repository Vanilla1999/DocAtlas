# DocAtlas: подробный аудит поиска через установленный MCP

**Дата:** 1 октября 2026. **Вердикт:** основная проблема сейчас — не испорченная БД и не полная несостоятельность поиска. Это плохая доставка полезных фактов из большого, неоднородного корпуса проекта: языковой recall, непрозрачная qualification, ранние caps, противоречащие друг другу документы и маленький бюджет, значительную часть которого занимает обвязка. Дополнительно найдены два воспроизводимых lifecycle/recovery дефекта.

На маленьких pinned-корпусах внешних библиотек установленный `main` уже работает значительно лучше, чем можно заключить по старым отчётам. **Но этот успех нельзя переносить на произвольный репозиторий или на весь dependency pipeline.**

## Как читать результат

- Этот файл — выводы, причины, ограничения и порядок исправлений.
- [Все 80 вопросов по самому проекту](PROJECT_80_REVIEW_RU.md): каждый вопрос, original/guided оценки, причины и IDs цитат.
- [Все frozen 80 по библиотекам](EXTERNAL_80_REVIEW_RU.md): вопросы, answerability, автоматическая и ручная оценки, размеры packets.
- [Сравнение с Grounded и Context7](COMPARATORS_RU.md): отдельные условия, несовпадения scorer, конкретные примеры.
- [План исправлений с критериями завершения](ACTION_PLAN_RU.md).
- `raw/` — исходные MCP wires, запросы, timings, индексные snapshots и дополнительные диагностики; `backup/` — резервная копия исходного локального индекса и конфигов.

## 1. Главные числа

### 1.1 По документации самого DocAtlas

Использованы прежние `questions.json` и `followup_questions.json` из `experiments/grounded-partial/`: 40 + 40. Основные вопросы не переписывались. Каждому заданы три отдельные lanes:

1. default scope, без lookups;
2. `scope="all"`, без lookups;
3. `scope="all"` с прежними, уже существовавшими `host_lookups`.

| Показатель | Default | All без lookups | All с lookups |
|---|---:|---:|---:|
| Вопросов | 80 | 80 | 80 |
| Непустой evidence packet | 59 | 59 | 77 |
| `insufficient_evidence` | 21 | 21 | 3 |
| Полный полезный evidence, ручная оценка положительных вопросов | не размечался отдельно | **22/72** | **41/72** |
| Частично полезный evidence | — | 19/72 | 19/72 |
| Нет полезного evidence для запрошенных фактов | — | **31/72** | **12/72** |
| p50 / p95 токенов, весь packet | 722 / 799 | 722 / 799 | 744 / 799 |
| p50 / p95 задержки, секунды | 0.77 / 3.87 | 0.79 / 4.01 | 1.06 / 4.46 |

Знаменатель 72, а не 80: в каждом наборе четыре вопроса с недоказуемой предпосылкой — шифрование, универсальные гарантии, приватный пароль, retention и т. п. Они разобраны отдельно. Не получить их выдуманный ответ — не ошибка поиска.

Ручная оценка — один reviewer после просмотра выдачи. Это не независимый blind benchmark и не оценка ответов coding model. Спорные частичные случаи допускают другую adjudication; очевидные пустые/нерелевантные случаи от этого не исчезнут.

**Непустая выдача маскирует проблему.** Среди 72 положительных вопросов original lane: 18 пустых и ещё **13 непустых, но без полезной поддержки нужных фактов**. Поэтому `59/80 ok` — плохая замена показателю качества.

Default и all в этих 80 вызовах дали одинаковые payloads после удаления session-local `source_uri`. Следовательно, совет «просто добавьте scope=all» не исправляет наблюдаемый провал на этой панели. Это не доказательство эквивалентности scopes на других корпусах.

### 1.2 Языковой разрыв

| Показатель | RU без lookups | EN без lookups | RU с lookups | EN с lookups |
|---|---:|---:|---:|---:|
| Непустая выдача, включая controls | **21/40** | **38/40** | 37/40 | 40/40 |
| Full на положительных вопросах | **5/36** | **17/36** | **22/36** | **19/36** |
| Partial | 10/36 | 9/36 | 10/36 | 9/36 |
| None | **21/36** | **10/36** | 4/36 | 8/36 |

Это не рандомизированные пары RU/EN: темы/формулировки тоже различаются. Но сочетание языковой асимметрии, сильного эффекта документационных lookups и traces с русскими generic search keys — достаточное основание сделать multilingual recall приоритетной проверкой, а не продолжать лечить БД.

Lookups дали 27 улучшений ручной категории, четыре ухудшения и 41 ничью. В частности, `projectB-Q20` был полезным без lookups, но потерял partial-answer guidance с ними. Подсказки — **не монотонное расширение** выдачи: они меняют отбор и packing.

Дополнительная проверка десяти исходных RU needs, переведённых на EN **без lookups**, усиливает оговорку: непустая выдача выросла 5/10 → 9/10, но full — только 2/10 → 3/10, full-or-partial — 3/10 → 5/10. Q09 восстановил точный sync/retry contract; Q29/B03/B23 остались плохими. **Перевод — recall lever, не достаточное решение.** Протокол frozen до этих calls, не blind holdout; raw в `raw/translation10/`, разметка в `manual_translation_review.json`.

### 1.3 Frozen 80 по внешним библиотекам

Набор `eval/evidence_quality_v2/cases.json`: восемь библиотек, по десять случаев; **48 within-budget положительных** и 32 partial/unanswerable/ambiguous/over-budget controls.

| Результат | DocAtlas main | Grounded 3.2.1, limit=3 | Grounded 3.2.1, limit=5 |
|---|---:|---:|---:|
| Recognized sufficient старым scorer | **45/48** | 32/48 | 32/48 |
| Полные requested facts после отдельного семантического review | **47/48** | **47/48** | **48/48** |
| p50 / p95 токенов native packet | **765 / 797** | 1,234 / 3,087 | 1,873 / 4,709 |
| p50 / p95 задержки, секунды | 0.28 / 0.74 | 0.0023 / 0.0028 | 0.0027 / 0.0032 |

**Это local-project retrieval по импортированным upstream Markdown snapshots.** Это не 45/48 успешных calls в dependency/library resolver: lockfile resolution, source discovery, network fetching и version certification здесь не проверялись. Runtime цитаты имеют `version_binding="unversioned"`; pinned version известна эксперименту из внешнего source registry, а не доказана MCP resolver.

Корпуса tiny: только выбранные исходные страницы библиотеки, без сотни локальных архитектурных/research/history distractors. Хороший результат на них совместим с плохим результатом на 134 документах DocAtlas. Старое сопоставление «31/48 когда-то → 45/48 теперь» не является чистым A/B эффектом последней правки: отличаются runtime, доставка, roots и протоколы. Исторический отчёт не использован как причинный baseline.

## 2. Что реально было запущено

### Runtime и corpus — разные вещи

- MCP executable: `/home/viadmin/.local/bin/doc-atlas mcp docs-serve`.
- Installed package: `doc-atlas 1.3.2`.
- Установлен из main commit **`d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c`**.
- Проверена byte parity всех **383 production Python файлов** установленного пакета и `/tmp/opencode/delivery-main/docmancer`: различий нет.
- Корпус проекта: `/tmp/opencode/docatlas-ablation`, checkout **`2847799264685baa4773f3af5452f6b3716dc74a`**, экспериментальная ветка. Это не утверждение, что corpus checkout сам является веткой main.
- Основные 320 calls идут по **настоящему MCP stdio**, не прямому Python handler: 240 project calls + 80 external calls.
- Ещё 76 calls с same-call instrumentation: 48 external positives и 28 project diagnostics. Это отдельные handler-observer calls, не часть stdio timing statistics и не новые независимые вопросы.
- Grounded: отдельно установлен `@arabold/docs-mcp-server@3.2.1`; 160 внешних calls с limits 3/5 и 20 project calls. Embedding columns проверены: ноль non-null embeddings.
- Context7: десять реальных hosted `query-docs` запросов с сохранёнными responses и library resolution. Источники/версии **не совпадают** с frozen snapshots.
- Дополнительные десять DocAtlas stdio calls проверяют same-meaning question-only RU→EN translations отдельно от основных 320.
- Выполнены отдельные clean-preflight, clear/rebuild и immediate-resource-read probes; поздние reads разобраны отдельно от свежих.

Production файлы, defaults, thresholds, lockfiles и глобальная MCP-конфигурация в этой задаче не менялись. Незакоммиченный исходный checkout `/home/viadmin/StudioProjects/hermes/docmancer` не трогался. Push/merge не выполнялись.

`DOCATLAS_OFFLINE=1`, `DOCATLAS_AUTO_VECTORS=0`, `with_vectors=false` использованы для локального DocAtlas прогона. Это lexical-mode диагностика; hybrid/dense и cloud embedding providers здесь не сравнивались. Флаги не заменяют OS-enforced network isolation. Context7 и установка Grounded требовали сеть.

### Переиндексация

Перед очисткой:

- SQLite structurally целая, но **0 sources, 0 retrieval_children**;
- discovery видел **134 документа**, indexed count был нулевой;
- сохранён SQLite backup через `sqlite3.backup`, конфиги и extracted directory.

Удалены через подтверждённый `prepare_docs(action="clear_index", scope="project-local")` только:

```text
/tmp/opencode/docatlas-ablation/.docatlas/docatlas.db
/tmp/opencode/docatlas-ablation/.docatlas/extracted
```

Shared local Qdrant намеренно **не удалён**; это явно сохранено как incomplete state. Глобальная БД не очищалась. Для lexical прогона этот retained vector state не является используемым retrieval lane.

Свежий MCP-процесс успешно выполнил sync за 2.13 секунды: **134 current/new документов**, `sections_indexed=1441`, warnings отсутствуют. Index snapshot содержит 134 sources, 2,779 retrieval-child rows и 1,433 retrieval-parent rows. Это разные таблицы/метрики; число legacy sections нельзя выдавать за число structured children. Corpus bytes: 866,399. SQLite integrity check — `ok`.

**Вывод:** база восстановлена и наполнена; качество обычных project вопросов всё равно низкое. Повторять полное удаление теперь — не лечение выявленных причин.

## 3. Подтверждённые дефекты и места потери

### D1. Неиндексированный чистый проект не получает правильную recovery action

**Класс:** воспроизводимый control-plane defect. **Приоритет:** P0.

Первый запрос текущего проекта получил `insufficient_evidence → code_search`, хотя `docs_status` видел 134 неиндексированных документа и рекомендовал sync.

Проверено дополнительно на отдельном маленьком **Git-репозитории с committed README, чистым worktree и локальным config**:

```text
docs_status: project_docs_found_not_indexed
get_docs_context: no_candidates → search_local_source
```

Это не dirty-worktree refusal, не отсутствие документации и не cache прежнего сервера. По документированному workflow нужна typed `prepare_docs(action="sync_project_docs")` action, с правильными preflight/confirmation guards. Нынешний результат заставляет агента искать код вместо подготовки уже существующих docs.

Raw: `raw/lifecycle/clean-fixture-state.json`, `clean-fixture-status.json`, `clean-fixture-query.json`.

В коде lower project service уже различает `project_docs_found_not_indexed` и формирует sync action: `docmancer/docs/application/_project_docs_service_part03.py:617–650`. Далее публичная context projection/recovery заменяет этот смысл generic retrieval failure. **Точное место исправления надо локализовать отдельным regression test; один симптом не оправдывает изменение всех recovery branches.**

Приёмка: clean + dirty + no-docs + stale fixtures должны получать разные корректные actions. Dirty проект не должен получить no-confirmation mutation. Original question/scope сохраняются.

### D2. clear_index оставляет cached service/store в сломанном состоянии

**Класс:** воспроизводимый lifecycle defect. **Приоритет:** P0.

Последовательность в одном установленном MCP-процессе:

```text
sync success → clear preview → clear confirm/applied → sync OperationalError
```

Новый процесс затем успешно синхронизирует тот же проект. После первого наблюдаемого failure файл SQLite был создан заново, но не имел таблиц.

Механизм подтверждается кодом:

1. `_service_for_project_path()` cache зависит от root/config identity; `clear_index` сразу возвращает base service и не инвалидирует project cache (`mcp/_docs_server_part01.py:37–79`).
2. Clear handler удаляет файлы, но не reset/invalidates cached project agents (`docs/interfaces/mcp/prefetch_tools.py:483–505`).
3. `AgentIndexGateway` кэширует agent instance (`docs/infrastructure/agent_index_gateway.py:89–100`).
4. `SQLiteStore` делает `_ensure_schema()` при создании; дальнейший `_connect()` просто открывает путь (`core/_sqlite_store_part01.py:8–21`). Старый объект открывает уже новый пустой файл.

Raw: `raw/lifecycle/probe-first-sync.json`, `probe-clear-apply.json`, `probe-after-clear-sync.json`, `probe-restart-sync.json`. Ошибка в public wire редактируется; не выдаю redacted traceback за точное имя отсутствующей таблицы.

Приёмка: **sync → clear → sync → query в одном процессе**; плюс другой storage root и чужие service instances остаются нетронутыми. Не обойти writer leases и stale-plan guards.

### D3. Полезный кандидат уже найден, но qualification отбрасывает его

**Класс:** подтверждённая потеря полезного контекста. **Приоритет:** P1.

`projectB-Q14`: «Does the output budget include citation metadata as well as document text?»

- В `docs/retrieval-boundaries.md:23–30` есть прямой ответ: whole canonical JSON, including metadata and optional locators, within 800 tokens/3 sources.
- Same-call trace показывает этот child **в retrieved candidates и в query window**.
- Он отвергается для `query-original` и `query-intent-1` с `insufficient_visible_match`.
- В final packet остаются таблицы CLI `--budget`/`--include` из `SKILL.md`, не отвечающие на metadata question.
- Projection rejections в этой trace пусты: основная потеря здесь раньше финального DTO packing.

Это важный контрпример к советам «увеличьте candidate pool» и «дайте больше токенов»: **кандидат уже в pool, но не допускается**.

Raw: `raw/traces/project28/projectB-Q14.json.gz`; original wire: `raw/project80/all/projectB-Q14.json`.

В `evidence_qualification.py:377–418, 495–593` exact/body term ratios, relation tokens, body/heading checks решают admission. Эти правила смешивают разные вещи: безопасное происхождение, поверхностное сходство и предполагаемую полезность. Хороший source identity сам по себе не ответ; но плохой overlap ratio тоже не доказывает, что факта нет.

### D4. Слабый generic hint может допустить нерелевантный текст

**Класс:** relevance/admission defect, не измеренная hallucination. **Приоритет:** P1.

`projectA-Q29` спрашивает, можно ли выполнять instruction из README, игнорирующую прежние указания. Final packet содержит `docs/INDEX.md` и ссылки на evaluation, потому что они упоминают README/agent/docs. Нужный threat-model policy не входит в наблюдаемый retrieved window.

Trace создаёт search keys `README`, `ли`, `Можно`, `считать`. Это не хорошее восстановление смысла вопроса. Exact anchor или совпадение с очень общей частицей помогает unrelated fragments пройти retrieval attribution, тогда как содержательные RU needs не поддерживаются English body.

Другой пример: `projectA-Q30` про одинаковые filenames в двух репозиториях получил PyPI `invalid-publisher` checklist. `retrieval_coverage="full"`, но нет ответа о project identity isolation. Ни original, ни guided lane эту ошибку не исправили.

**Это не утечка между проектами и не ложное edit permission:** цитаты действительно относятся к этому проекту, `answer_supported=false`. Это плохой выбор фактов внутри разрешённого корпуса.

Raw: `raw/project80/all/projectA-Q29.json`, `projectA-Q30.json`, соответствующая Q29 trace. Политика изоляции существует в `wiki/Architecture.md:27–32`.

### D5. Нужный Typer child теряется на раннем per-source cap

**Класс:** подтверждённая cap/ranking потеря. **Приоритет:** P1.

Единственный семантически неотвеченный external positive у DocAtlas — `typer-05`: требуется правило preceding space перед slash в отрицательном boolean option name.

Same-call trace:

- свидетель есть в индексном child `bool.md:214–231`;
- есть в pre-cap list оригинального retrieval, на **9-й позиции**;
- после `_limit_sections_per_source` остаются другие три children, нужного нет;
- supplemental `boolean option` приводит к ранним общим examples, не к `" /-S"` rule;
- final packet пустой.

Это точнее, чем общее `retrieval_miss`: источник индексирован, нужный фрагмент найден до cap и потерян до public candidate window. Structural overflow одного соседа не спасает непредставленный далёкий parent.

Grounded limit=3 тоже не доставляет правило; limit=5 доставляет. Поэтому различие — не волшебное понимание Grounded, а placement/candidate breadth и delivery volume.

Raw: `raw/traces/external48/typer-05.json.gz`; `raw/grounded/native/3/typer-05.json` и `native/5/typer-05.json`.

### D6. Current docs сами содержат конкурирующие contracts

**Класс:** corpus/documentation defect. **Приоритет:** P1.

Примеры из доставленных цитат:

- `wiki/Architecture.md:147` предлагает `get_docs_job_status(job_id)` и `cancel_docs_job(job_id)` как calls; advertised public surface имеет только три router tools. `projectB-Q11` получает именно эти legacy names.
- `docs/mcp-docs-server.md:42` говорит, что host may answer **only covered claims**; `docs/source-continuation.md:5–10` и `docs/AGENT_DOCS_WORKFLOW.md:22–27` разрешают поддержанные snippets facts при false certification flags. Неопределённость термина covered особенно опасна при retrieval-only/unverified facet contract.
- `SKILL.md:143–144` still references rephrase/action_packet workflow, тогда как actual docs_context отдаёт `sources` и evidence IDs.
- `wiki/Troubleshooting.md` описывает lexical fallback при unavailable vectors; `wiki/Configuration.md:51` описывает fail-closed non-lexical mode без explicit degraded opt-in. Grounded одновременно возвращает обе версии.

Свежая индексация **правильно** пересохраняет эти противоречия. Она не выбирает, какая спецификация current. Поэтому «134 indexed, warnings=[]» не означает «корпус согласован и полезен».

Нужны текущий canonical contract, актуальный catalog lifecycle для supporting/history/planning источников и удаление legacy public-tool phrasing из текущих ссылочных страниц. Не удалять исторические исследования: пометить/развести их с operational evidence.

## 4. Почему бюджет усиливает проблему

Production project context ограничен **800 admission tokens и тремя sources**. Admission берёт max(public UTF-8 bytes/4 estimate, pinned offline tokenizer) по whole serialized response. Поэтому `query.default_budget: 2400` в YAML не превращается в 2,400-token public MCP packet.

В непустых project packets без lookups:

- медианный whole response — **767 токенов**;
- медианный только concatenated `snippet` text — **176 токенов**;
- медианная доля snippet text — **24.9%**.

С lookups — 764 whole / 172 snippet, доля 23.2%.

Это не точное additive разложение токенов: tokenizer имеет boundary effects. Но порядок величины ясен: около трёх четвертей small packet занимает всё, что не является самой цитатой — flags, coverage IDs, citation metadata, locators, read_next и т. д. Эти поля часто нужны; цена их присутствия не бесплатна.

Например, packet может потратить source slot на повторяющееся «This is the canonical detailed workflow reference for DocAtlas», сохраняя меньше места для ответа. В Q08 после полезного config/catalog distinction остаётся unrelated HTTP path-encoding passage. Это packing/noise issue, даже когда полезный факт уже доставлен.

**Важно:** budget — усилитель, не единственная причина. Q14 теряет хороший child на qualification, Q29 не находит нужную policy в наблюдаемом window, Typer теряет её на cap. Большой DTO может упаковать больше неверного, не восстановив правильное.

Рекомендация: сначала исправить recall/admission, затем сравнить пакеты 800/1,600/2,400 при одинаковом saved candidate pool. Отдельно проверить lean read-only DTO, убрав redundant certification diagnostics, но не источник, identity/snapshot binding и реальные missing facts. Не менять все budgets по интуиции и не называть снижение serialized bytes экономией полного task bill.

## 5. Почему Context7 выглядит убедительнее

### Что наблюдали, а не предполагаем

Десять actual hosted вопросов: FastAPI, Starlette, Typer, Pydantic, HTTPX, MkDocs, Ruff, uv. Получены нормальные source-attributed passages и runnable code examples. Консервативный review: восемь full, два partial/uncertain. Токены конкретных outputs: 287–1,124.

Хорошие примеры:

- Pydantic strict precedence: сразу validation-call → Field → model_config, с примерами.
- MkDocs title precedence: полный ordered list и stop-at-first rule.
- HTTPX four timeouts: список всех четырёх и отдельное объяснение операции каждого.

Это действительно удобно для coding model. Но текущая панель **не доказала**, что Context7 лучше DocAtlas на этих десяти вопросах: local frozen DocAtlas доставляет complete required witnesses на них, а hosted Context7 использует другую/current документацию. У uv в Context7 уже `first-index`, в pinned snapshot — старое `first-match`. Нельзя объявить wrong-version support или version parity без matching.

### Правдоподобные структурные преимущества

1. Context7 получает конкретную library identity перед query; репозиторные policy/research/release docs не конкурируют с CORS API.
2. Native output организован вокруг relevant code/information snippets, а не вокруг десятков retrieval/proof diagnostics в 800-token envelope.
3. Example materialization отличается: наши raw upstream Markdown snapshots содержат include directives вроде `{!../../../docs_src/...py!}`, тогда как Context7 отдаёт развёрнутый пример. Если задача требует executable example, это реальный corpus-preparation advantage, не обязательно лучший BM25.
4. Публичная API-документация Context7 описывает search и reranking snippets. Но точная hosted search implementation, training/data preparation и scoring не раскрыты этим MCP клиентом. **Нельзя честно утверждать, что всё объясняется одной конкретной embedding моделью.**

Сравнивать надо не бренды, а условия: одна библиотека/версия, одинаковые source bytes/доступность, равный total evidence budget и одинаковый answer model. Текущий отчёт даёт диагностику интерфейсного преимущества, не reverse engineering private Context7 backend.

## 6. Что показал Grounded

Grounded отдельно установлен вне project dependencies. Для внешней панели ему переданы те же выбранные документы, проверены exact URL coverage, отсутствие неожиданно добавленных страниц и нулевые embeddings.

Native lexical search очень быстрый и обычно отдаёт достаточно материала. При limit=3 семантически полны 47/48 положительных; limit=5 — 48/48. Но p95 native input составляет 3,087/4,709 токенов против 797 у DocAtlas. Это **не resource-matched победа**.

First-visible-three-paragraph adapter в 800 токенов оставляет у Grounded только 8/48 recognized complete witnesses. Такой adapter не является реальным режимом Grounded и не имеет intelligent question-directed packing: он часто сохраняет заголовок и introduction, а нужный ответ находится дальше. Не использовать 8/48 как marketing рейтинг Grounded.

Дополнительно проиндексированы те же **134 project docs** и задано 20 исходных project вопросов (10 RU, 10 EN). Первый directory scrape пропустил CHANGELOG; его добавили exact-file ingest **до запросов**, затем проверили 134/134 source URLs, нулевые embeddings. Никакие вопросы для Grounded не подгонялись.

Ключевые наблюдения:

- RU запросы массово уходят в старый русскоязычный readiness-review, а не в нужные English policy pages.
- На B08 Grounded приносит README sync contract, который DocAtlas пропускает.
- На B20 приносит полезный partial-answer contract, потерянный guided lane DocAtlas.
- На B14 Grounded приносит старые budget roadmaps, не current whole-response metadata contract.
- Нет catalog active/history/planning фильтра, поэтому superseded ADRs и implementation plans возвращаются как обычные native results. Это не authority-matched alternative.

**Вывод:** замена сервера на FTS-only Grounded сама по себе не решает русский поиск по этому корпусу. Можно заимствовать simplicity/fast retrieval и изучить его expansion, но нельзя заменить ими source authority/version/scope invariants.

## 7. Ошибки измерения, которые мешают развитию

### M1. Frozen witness не всегда совпадает с реально запрошенной поддержкой

`mkdocs-06`: нужные ограничения cells и blank lines есть в двух цитатах. Scorer ждёт их одной contiguous строкой и выдаёт `needs_review`. Это **не ingest failure**.

`uv-06`: вопрос просит default build isolation и что установить перед `--no-build-isolation`. Цитата уже говорит preinstall build dependencies. Frozen witness включает ещё конкретный biopython command, который вопрос не требует. Это **не обязательный missing fact**.

Поэтому DocAtlas raw 45/48 превращается в manual 47/48 без изменения production и без нового поиска. Полный raw score не переписан задним числом.

### M2. Rendered Markdown Grounded систематически недосчитывается

Native mapping требует полностью видимые source paragraphs. Lists/references/italic rendering меняют paragraph boundaries. Второй, formatting-only observer повышает число recognized positives с 32 до 42/43; ещё пять cases разрешены ручным review явных списков и определений. Original scorer сохранён отдельно.

Если объявить все `needs_review` failures, можно потратить месяц на «починку» уже доставленных фактов.

### M3. `ok`, full retrieval coverage и passed tests не являются semantic usefulness

- Q30 имеет full retrieval coverage и нерелевантный PyPI checklist.
- Ни один основной project packet не имеет `context_quality="checked"`: original 55 unverified / 4 partial / 21 unavailable; guided 71 / 6 / 3.
- False answer flags у `docs_context` означают отсутствие server certification, а **не запрет host объяснить действительно поддержанную цитатой часть**.
- Ни непустой packet, ни true query attribution не доказывают, что ответил каждый запрошенный факт.

Scorer должен иметь отдельные показатели: evidence found, admitted, visible, fact-supported, answer correctness, citation entailment, wrong-version/authority errors, total trajectory cost. Не схлопывать их в один pass count.

### M4. Исправлена ошибка самого нового аудитора

Первоначальный public observer неверно сравнивал `content_sha256` с SHA256 всего файла. В DocAtlas это canonical evidence-material digest, не raw file hash. Из-за этого первый `live-summary` ошибочно помечал все непустые packets как integrity violations.

Это **ошибка измерения, не найденный product corruption**. Official MCP wires не менялись; initial summary оставлен в `raw/live-summary-initial-observer.json`, corrected checks — в `raw/public-integrity-corrected.json`. Исправленный summary явно помечен.

Итог: **0 public verbatim/path/line/digest-shape нарушений на 320 основных packets; 0 snapshot-binding audit нарушений на 76 instrumented calls.** Это подтверждает механическую целостность цитат, не relevance и не universal version correctness.

## 8. Задержка и лишняя сложность

В 28 project traces один high-level call выполняет **6–10 dispatcher runs**. Во всех 28 исходный question запускается минимум два раза. Это не 6–10 независимых root questions, а стоимость внутреннего orchestration.

`projectA-Q07`: 6 dispatcher calls, суммарно 118 pre-cap appearances, 49 post-cap appearances, 20 merged window items, 0 qualified projection variants. Эти appearances могут повторять тот же child; не выдавать суммы за число уникальных полезных кандидатов.

`projectB-Q14`: 7 calls, 20 final query-window candidates; прямой budget fact всё равно отвергается, CLI distractors остаются.

Node/Python, warm state, background activity и output size различаются, поэтому времена Grounded/DocAtlas здесь не чистый microbenchmark. Но порядок затрат показывает направление: оптимизировать ясный candidate flow и duplicate original retrieval разумнее, чем добавлять ещё одну heuristic lane к каждому вопросу.

Желаемый diagnostic flow:

```text
storage readiness / typed preparation
→ explicit library/project/version/scope boundary
→ broad candidates (original + narrowly controlled multilingual lookups)
→ hard identity/snapshot/source-policy eligibility
→ soft question-specific ranking
→ evidence blocks / relation preservation / budget packing
→ final source/quote binding and honest missing facts
```

Hard safety eligibility и soft semantic relevance должны быть разными decisions. Translation/reranker могут предлагать search order, но не менять source identity, original needs, отрицание, версии, сравниваемые стороны или разрешение редактировать.

## 9. Что делать: рекомендованный порядок

### Сначала закрыть конкретное, а не начать новую бесконечную ablation серию

1. **P0 recovery:** сохранить lifecycle reason и exact prepare action при empty index; отдельный installed-MCP regression.
2. **P0 cleanup lifecycle:** storage-scoped cache invalidation/reinitialization после удаления; same-process rebuild test.
3. **P1 docs consistency:** один canonical current workflow, router action names, false answer flags/host synthesis, offline/vector fallback policy. History/research не удалять, а явно отделить.
4. **P1 evidence evaluator:** multi-source fact union и formatting-only equivalence; unknown означает review, не failure/pass. Исправление scorer отдельно от retrieval.
5. **P1 multilingual recall + useful candidate admission:** начать с Q07, Q14, Q29, Q30 и Typer05; trace должен показать место первого изменения. Не global ratio-off.
6. **P1 packet cost:** saved-pool сравнение lean DTO и разных budgets, сохраняя цитаты, условия и identity. Не лечить budget тем, что просто перестали считать metadata.
7. **Отдельный независимый gate:** новые вопросы от другого автора на нескольких репозиториях и внешних версиях; одинаковый answer model; task correctness/unsupported claims/total tokens/latency.

Предлагаемые критерии и stop conditions — [ACTION_PLAN_RU.md](ACTION_PLAN_RU.md). Это рекомендации, **не выполненные fixes и не авторизация их автоматически merge**.

### Чего не делать

- Не удалять БД снова ради Russian query recall.
- Не считать 45/48 на tiny snapshots закрытым внешним library pipeline.
- Не отключать source/version/stale/scope/authorization protections вместе с ratio gates.
- Не менять embedding model только потому, что Context7 выглядит лучше; сначала проверить multilingual recall/reranking на равных corpora.
- Не собирать сотни aliases под увиденные Q01–Q80 как основную архитектуру.
- Не выдавать guided 77/80 nonempty за 96% правильных ответов.
- Не добавлять бесконечные retries/source reads к нерелевантному первоначальному источнику.
- Не считать новую страницу отчёта новой независимой проверкой продукта.

## 10. Границы вывода

1. Development вопросы давно доступны и уже использовались. Не unseen validation.
2. Reviewer — текущий ассистент; нет независимой semantic/citation adjudication.
3. Нет autonomous coding-model run, сгенерированных 80 model answers, patch correctness или task-token bill.
4. Project corpus — один репозиторий; tiny external snapshots не моделируют полный upstream site.
5. Context7 corpus/version/hosting не контролировались; Grounded native budget больше, policy filtering другой.
6. Основной прогон sequential, без cold/warm повторов и CPU isolation; timings диагностические.
7. Full uncapped first-loss для всех requested facts не собирался. 76 traces отражают наблюдаемые caps/boundaries; Typer и Q14 имеют конкретную witnessed потерю, остальные нельзя механически приписать одному stage.
8. Поздние resource reads после восьми других project roots вернули unknown/expired reference. Это session/cache-lifetime ограничение, не самостоятельное доказательство broken reader. **Immediate read в свежем процессе успешно вернул source text и continuation**; reader не объявлен сломанным.
9. Основные scripts — one-shot локальные audit runners с зафиксированными путями, а не новый production/CI harness. Повторный запуск должен писать в отдельный output и не перетирать эти raw artifacts.

## Итог

Несколько месяцев работы не были бесполезны: на узких upstream facts `main` уже способен доставлять почти весь нужный evidence в небольшом packet и сохраняет хорошую механическую целостность цитат.

Но продуктовая боль остаётся закономерной: **крупный corpus содержит текущие и устаревшие объяснения; русский need распознаётся хуже; полезные кандидаты могут отбрасываться, а generic matches — допускаться; после этого маленький metadata-heavy packet окончательно закрепляет неправильный выбор.**

Следующий шаг должен быть не «ещё один глобальный алгоритм», а несколько коротких, завершимых работ с installed-MCP acceptance: два P0 lifecycle fixes, согласование текущих docs, корректная оценка фактов, затем multilingual candidate flow и packet cost на фиксированных данных. Только после этого имеет смысл проверять общую конкуренцию с Context7 на независимой end-to-end панели.

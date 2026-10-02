# Как Grounded доставляет `mkdocs-05`: проверка реализации и повторный запуск

Дата: 2026-10-02. Дополнение и уточнение к
[анализу эвристик](M2_HEURISTICS_RESEARCH_ANALYSIS_RU.md).

## Главный вывод

**Анализ причин потери в DocAtlas подтверждён повторным запуском. Объяснение
успеха Grounded теперь точнее: ответ уже внутри первого крупного FTS-chunk;
расширение соседей для этого кейса не требуется.**

Grounded не распознаёт специально `wins → override`. Он сохраняет правило
вместе с описанием навигации, ранжирует этот блок первым и возвращает его целиком.
Отдельный абзац не обязан повторять половину слов вопроса или соседнюю пару
из вопроса, чтобы остаться в выдаче.

Это уверенный вывод о конкретном механизме. Вывод о превосходстве такого подхода
на всех вопросах по-прежнему требует сравнительного эксперимента.

## 1. Что проверено заново

- Исходники Grounded **3.2.1**, tag `v3.2.1`, commit
  `f2938c47bb8937c650f0d5ddb614f867773b29f4`.
- Опубликованный npm package `@arabold/docs-mcp-server@3.2.1`, отдельная установка
  и отдельное хранилище. Его `package.json` совпадает с сохранённым audit runtime.
- Повторная индексация **всех 14 frozen файлов / 8 библиотек**, с проверкой SHA-256.
  Воспроизводился весь FTS corpus: BM25 statistics относятся к общей таблице,
  хотя возвращаемые результаты фильтруются по library/version.
- 87 indexed chunks, **0 embeddings**; counts каждой библиотеки совпадают со
  старым audit. MkDocs: одна страница, семь chunks.
- Неизменённый вопрос, native search с `limit=1/3/5` через CLI. CLI и MCP
  используют тот же `SearchTool`; новый MCP transport session не запускался.
- Контроль с `precedingSiblingsLimit=0`, `subsequentSiblingsLimit=0`,
  `childLimit=0`. Parent lookup оставлен включённым и не выдан за полное
  отключение expansion.
- Read-only SQL replay исходного FTS ranking для наблюдения initial hits до
  assembly. Добавлен только наблюдаемый `sort_order`; ranking/filter не изменён.
- Повторены существующие DocAtlas native и no-parent-diversity diagnostics
  на текущем working tree. Обе потери воспроизведены.

Доказательные данные:
[m2_grounded_mechanism_check.json](m2_grounded_mechanism_check.json).
В JSON сохранены первый chunk целиком, ranking, размеры, corpus identities,
проверки равенства и результаты повторной проверки DocAtlas.

## 2. Как устроен проверенный путь Grounded

```text
Markdown → структурное разбиение → greedy объединение небольших блоков
  → FTS5: исходная фраза OR отдельные слова
  → BM25 top-k в выбранной library/version
  → URL grouping / distance clustering / context assembly
  → сортировка по лучшему исходному score
  → выдача текста с URL
```

### 2.1. Крупнее единица поиска

`MarkdownPipeline` использует `SemanticMarkdownSplitter` и `GreedySplitter`.
Название Semantic здесь не означает вызов embedding/LLM: исследованный путь
детерминированно работает со структурой Markdown, типами блоков и размерами.

Defaults: **min 500 / preferred 1500 / max 5000 символов**, не tokens.
GreedySplitter объединяет небольшие блоки, учитывает H1/H2 и section paths.
`preferred` — мягкий ориентир, поэтому результат может быть длиннее 1500.

На нашей странице получились **7 chunks**. DocAtlas в рассматриваемом native
retrieval перед body reranking имеет **51 candidate**. Это не равные единицы:
нельзя интерпретировать 7 против 51 как самостоятельную метрику качества.

### 2.2. Lexical retrieval допускает неполное совпадение

`DocumentStore.escapeFtsQuery` строит исходную фразу OR слова, без добавления
`override` или других answer-derived синонимов. FTS tokenizer —
`porter unicode61`; Porter stemming не является переводом или semantic entailment.

В FTS-only ветке:

```text
bm25(documents_fts, 10.0, 1.0, 5.0, 1.0)
```

Поля в текущей схеме: **content / title / url / path**. Результат ограничивается
library/version, исключаются structural chunks, затем применяется top-k.
Порог «должна совпасть половина слов вопроса» на этом пути отсутствует.

### 2.3. Assembly — отдельная операция

Для Markdown могут добавляться parent, один предыдущий sibling, два следующих
sibling и до трёх children. IDs дедуплицируются, выбранные chunks собираются
в исходном порядке. Итоговый score наследуется от лучшего initial hit.

`limit` ограничивает **initial hits**, а не количество абзацев и не tokens.
После assembly MCP formatter отдаёт полученный текст. На исследованном пути
нет повторной проверки каждого абзаца на долю слов исходного вопроса и нет
проверки adjacent query pair перед выдачей.

Grounded при этом не выдаёт DocAtlas `answer_supported`, coverage или edit
permission. Он возвращает найденный контекст. Library/version validation у него
есть; отсутствие нашего proof/admission pipeline не означает отсутствие любых
guards.

## 3. Что произошло именно с `mkdocs-05`

### 3.1. Ответ находится в top-1 ещё до assembly

Read-only наблюдение повторно построенного индекса:

| FTS rank | Chunk ID этого запуска | `sort_order` | BM25, меньше — лучше | Required paragraph |
|---|---:|---:|---:|---|
| 1 | 17 | 1 | −46.802922 | **Есть** |
| 2 | 21 | 5 | −36.319115 | Нет |
| 3 | 22 | 6 | −31.743422 | Нет |

Первый chunk: **3583 символа, 769 `o200k_base` tokens**. В нём вместе находятся:

1. Конец описания README/index pages.
2. `Configure Pages and Navigation` и описание `nav`.
3. Примеры именования navigation items.
4. Прямое правило: navigation title **will override any title defined within
   the page itself**.
5. Дальнейшее описание navigation subsections.

Именно окружающее описание даёт lexical anchors `configuration`, `Markdown`,
`titles` и другие. Нужное правило не выделено в отдельный короткий фрагмент,
который должен самостоятельно пройти весь набор relevance checks.

### 3.2. Проверки, исключающие догадку про «спасение соседями»

| Проверка | Результат |
|---|---|
| `initial_hit[0].content == native_result[0].content` | **True** |
| Первый результат при `limit=1` равен первому при `limit=3` | **True** |
| Отключение preceding/subsequent/child expansion сохраняет первый результат | **True** |
| Новая выдача `limit=3/5` совпадает со старой после замены только local URL prefix | **True** |

Это сильнее предположения по внешнему output: **для первого результата assembly
не добавляет ни одного байта**. Нужное правило присутствовало в индексном chunk
до поиска. Его получение не зависит от второго/третьего hit.

Parent expansion остаётся включённым в конфигурационном контроле, но точное
равенство initial content и assembled content независимо исключает добавление
parent bytes в данном результате.

### 3.3. Почему 3087 tokens — не обязательная цена этого ответа

| Представление | Actual tokens | `ceil(UTF-8 bytes/4)` |
|---|---:|---:|
| Top-1 chunk, только body | 769 | 896 |
| `limit=1`, MCP text format с новым локальным URL | 806 | 940 |
| `limit=3`, тот же формат | 3084 | 3499 |
| `limit=5`, тот же формат | 4483 | 5152 |

Token count нового ответа отличается от старого только длиной local URL.
При старом URL prefix получаются прежние **3087 / 4488** tokens; для нового
`limit=1` с тем же старым prefix было бы 807.

Следовательно, тезис «Grounded находит правило лишь потому, что выдаёт 3000+
tokens» **слишком сильный и опровергнут этим запуском**. Правило доставляется
одним результатом примерно за 806 tokens.

Однако это **не PASS нашего бюджета 800**: даже body имеет conservative byte
estimate 896, а DocAtlas считает полный DTO с metadata. Уменьшенный native output
Grounded и допустимый DocAtlas packet — разные условия.

Само правило короткое: 36 tokens в rendered paragraph. Это показывает, что факт
не требует тысяч tokens по длине, но не доказывает, что production selector
найдёт минимальное полноценное окно без gold labels. Равно-бюджетный packer
по-прежнему нужно проверить отдельно.

## 4. Верен ли предыдущий анализ DocAtlas?

**Да, в причинной части.** Повторный запуск подтвердил:

```text
Native: witness rank 4 → parent-first rank 15 → quota теряет witness.
No-parent-diversity: rank 4 → quota сохраняет witness третьим.
Далее: match ratio 3/11; insufficient_visible_match.
Read fallback: no_local_topic_witness.
Prefit → projector: 0 candidates; итог: 0 visible sources.
```

Но выводы нуждаются в трёх уточнениях:

1. **Это последовательно расположенные барьеры, не статистически независимые
   причины.** Native теряет paragraph раньше qualification. Downstream отказ
   наблюдается в отдельной ablation, когда paragraph до него доведён.
2. **Grounded в этом случае выигрывает не за счёт query-time neighbor rescue.**
   Контекст правила сохранён на этапе chunking; top-1 BM25 hit уже достаточен.
3. **Меньше эвристик не означает автоматически лучше.** Grounded тоже содержит
   эвристики размеров, section boundaries, field weights, stemming, clustering
   и expansion. Отличается расположение решений: полезный read context здесь
   не проходит каскад дополнительных per-paragraph veto.

Chunking, BM25 и отсутствие последующих veto не были по отдельности заменены
в DocAtlas. Поэтому нельзя объявить точный вклад каждого различия в общий
quality gain. Установлена достаточность конкретного Grounded пути для этого
кейса, а не optimality его параметров.

## 5. В чём уже можно быть уверенным

| Утверждение | Уверенность и основание |
|---|---|
| В frozen источнике есть прямой ответ | **Высокая:** явный precedence paragraph |
| Grounded 3.2.1 доставляет его без embeddings и rewrite | **Высокая:** повторный пакетный запуск, DB check, original question |
| Для этого достаточно одного initial hit | **Высокая:** native `limit=1`, FTS replay и точное равенство body |
| Expansion не причина успеха Result 1 | **Высокая:** assembled body тождествен исходному chunk |
| DocAtlas сам теряет найденный материал | **Высокая:** повторены native trace и ограниченная runtime ablation |
| Удаление только parent diversity исправит весь кейс | **Уверенно нет:** downstream отказ воспроизведён |
| Adjacent query pair необходима для полезного context | **Уверенно нет как универсальный критерий:** есть прямой контрпример |
| Каскад relevance veto и ранние потери стоит упрощать | **Сильное инженерное основание**, но конкретная замена ещё должна пройти evaluation |
| Крупные chunks всегда лучше / Grounded лучше на 800 | **Не установлено:** бюджет и retrieval units отличаются |
| Pure FTS решит RU→EN и смешанные repository вопросы | **Не установлено:** этот EN→EN case такой проверки не содержит |

Это не вероятности 95%/99%: для них здесь нет статистической модели и достаточной
независимой выборки. Высокая уверенность относится к наблюдённым детерминированным
событиям и причинному контролю, а не к будущему среднему качеству.

## 6. Практический вывод для упрощения

**Искать стоит на достаточно полном смысловом блоке, а экономить tokens — при
последующей привязанной к исходнику упаковке.** Раннее разбиение на короткие
fragments с самостоятельным lexical veto способно потерять короткое правило,
чьи lexical anchors находятся в окружающем описании.

Наиболее обоснованный эксперимент теперь конкретнее:

- сравнить нынешние atomic candidates с bounded section-sized retrieval units;
- сохранить различие между retrieval unit и финальным visible window;
- проверить единый read-context relevance contract вместо нескольких
  несовпадающих lexical veto;
- оставить повторную provenance/scope/version/span проверку именно тех bytes,
  которые попали в packet, и независимую claim support/permission проверку;
- измерить retention, relevance precision, false abstain и full-DTO fit на
  прежнем бюджете, включая negative и held-out cases.

Это не основание просто скопировать Grounded max-size или выдавать весь parent.
Но **основание отказаться от представления, что каждый полезный абзац обязан
сам повторять формулировку всего вопроса, уже есть**.

## 7. Источники и воспроизводимость

Pinned upstream source:

- [MarkdownPipeline.ts](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/src/scraper/pipelines/MarkdownPipeline.ts#L24-L43)
- [GreedySplitter.ts](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/src/splitter/GreedySplitter.ts#L43-L107)
- [FTS query construction](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/src/store/DocumentStore.ts#L908-L994)
- [FTS-only ranking](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/src/store/DocumentStore.ts#L2443-L2486)
- [FTS schema / tokenizer](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/db/migrations/009-add-pages-table.sql#L97-L103)
- [DocumentRetrieverService.ts](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/src/store/DocumentRetrieverService.ts#L28-L145)
- [MarkdownAssemblyStrategy.ts](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/src/store/assembly/strategies/MarkdownAssemblyStrategy.ts#L54-L148)
- [MCP rendering](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/src/mcp/mcpServer.ts#L290-L312)

Context7 использован для навигации по документации; выводы сверены с указанным
tag/commit и runtime, а не перенесены из документации `main`.

Диагностический [script](m2_grounded_mechanism_probe.py) принимает путь к
установленному `dist/index.js` и **новую** внешнюю рабочую директорию:

```bash
python3 roadmap/search-quality-2026-10-01/m2_grounded_mechanism_probe.py \
  --node-entry /tmp/opencode/grounded-probe-3.2.1/node_modules/@arabold/docs-mcp-server/dist/index.js \
  --work /tmp/opencode/grounded-mechanism-rerun
```

Для `--summary-output` нужен Python environment с зависимостями DocAtlas и
`PYTHONPATH=.`. Здесь использован существующий environment `doc-atlas`, без
изменения lockfile. Первичная попытка использовать системный Python не имела
`yaml`/`regex`; в корректном environment diagnostics успешно выполнены.

Полные raw CLI records, store и свежие DocAtlas traces:
`/tmp/opencode/grounded-mechanism-20261002/`. Переносимый summary в репозитории
содержит SHA-256 полного raw artifact и все основные проверяемые результаты.

Production, tests, fixtures, query text, delivery thresholds и budgets не
изменены. Добавлены только анализ и diagnostic artifacts. Полный regression
suite и LLM-reader benchmark здесь не запускались; M2 этим не закрывается.

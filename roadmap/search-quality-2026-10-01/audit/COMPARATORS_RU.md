# Grounded и Context7: что сравнили и что из этого следует

## 1. Условия сравнения

| Система | Corpus | Identity/policy | Retrieval | Output budget |
|---|---|---|---|---|
| DocAtlas installed main | Pinned selected Markdown либо 134 project files | Local project catalog/scope/lifecycle, snapshot guards | Lexical | Whole packet ≤800 admission tokens, ≤3 sources |
| Grounded 3.2.1 external | Те же source bytes, exact URL coverage | Каждая библиотека отдельно; нет DocAtlas policy router | FTS-only, verified zero embeddings | Native limit=3 и 5, не 800 tokens |
| Grounded 3.2.1 project | Те же 134 project files | Все файлы в одной library; lifecycle/catalog policy не передана | FTS-only | Native limit=3 |
| Context7 hosted | Другой/current corpus | Resolve-library-id затем query-docs; snapshot parity не проверялась | Hosted implementation | Native output, не fixed 800 |

Внешний frozen corpus не включает все upstream pages, code sources и site navigation. Например, исходный FastAPI Markdown содержит build/include directives вместо развёрнутого Python example. На таких задачах Context7 может выигрывать подготовкой корпуса, а не search scoring.

Сравнение latency — один sequential diagnostic pass на разных runtime stacks, с различными budgets. Это не повторяемый cold/warm benchmark и не гарантированная SLA.

## 2. Внешние 48 positive cases: результат по библиотекам

| Библиотека | DocAtlas recognized full | DocAtlas semantic full | Grounded limit3 recognized full | Grounded limit3 semantic full | Grounded limit5 semantic full |
|---|---:|---:|---:|---:|---:|
| FastAPI | 6/6 | 6/6 | 3/6 | 6/6 | 6/6 |
| Starlette | 6/6 | 6/6 | 5/6 | 6/6 | 6/6 |
| Typer | 5/6 | **5/6** | 5/6 | **5/6** | **6/6** |
| Pydantic | 6/6 | 6/6 | 4/6 | 6/6 | 6/6 |
| HTTPX | 6/6 | 6/6 | 3/6 | 6/6 | 6/6 |
| MkDocs | 5/6 | 6/6 | 5/6 | 6/6 | 6/6 |
| Ruff | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 |
| uv | 5/6 | 6/6 | 1/6 | 6/6 | 6/6 |
| **Всего** | **45/48** | **47/48** | **32/48** | **47/48** | **48/48** |

Semantic review — текущий reviewer, не blinded independent evaluation. Для DocAtlas 45 подтверждений даны исходным scorer, ещё два явно объяснены ниже. Для Grounded сначала проверено formatting-only witness matching, затем отдельно разрешены оставшиеся случаи с явными facts.

### DocAtlas: два false-negative кандидата scorer

- **MkDocs06:** одна цитата содержит no block-level/no multiline cells, другая — blank line before/after table. Requested facts целиком видны; требование одной contiguous witness-string некорректно для union evidence.
- **uv06:** видны PEP 517 isolation default, missing-build-dependency remediation и preinstall dependencies before `--no-build-isolation`. Frozen witness дополнительно требует конкретную biopython команду, хотя root question этого не просит.

### Grounded: почему 32 не означает 16 search failures

Existing paragraph preimage adapter связывает только полностью видимые source paragraphs. Native renderer меняет списки, ссылки, escapes и paragraph boundaries. Дополнительный formatting-only observer, не добавляющий missing text, распознаёт **42/48 при limit3 и 43/48 при limit5**.

Ещё пять remaining cases имеют явную поддержку facts:

1. `fastapi-04`: parameter list сообщает default False и запрет wildcard origins при credentials.
2. `pydantic-06`: Alias Priority list явно различает 2/1/not-set и precedence.
3. `httpx-03`: connect/read/write/pool definitions все присутствуют.
4. `mkdocs-06`: cells restrictions и blank-line rule прямо даны; `[syntax]` reference развёрнут в link.
5. `uv-02`: перечислены оба default pre-release acceptance случая; italic/list formatting отличается.

`typer-05` при limit3 действительно не имеет нужного правила. При limit5 required witness находится в дополнительном native result и проходит formatting-only check. Здесь расширение output помогает — и увеличивает input cost.

Raw: `raw/grounded/results.json`, `formatting-only-native-witness-check.json`, `manual_comparator_review.json`.

## 3. Равный small budget не равен native ranking

Одинаковый source-preserving adapter сохраняет исходный порядок visible blocks, максимум три блока и 800 actual tokenizer tokens, без case labels или gold в selection.

- DocAtlas уже упакован до 800/3; после минимального adapter остаётся **45/48 recognized full**.
- Grounded native mapped paragraphs после того же adapter дают **8/48 recognized full**.

**Не трактовать второе число как фактический product score Grounded.** Это first-visible-paragraph packer, не native question-directed assembly: introduction/heading могут съесть все три slots, а полный ответ виден позднее в native output. Второй семантический review всех controlled packets не выполнен.

Правильный вывод: native recall и useful tight-budget delivery — разные задачи. Нельзя обрезать больший ответ по первым трём paragraphs, затем объявить comparative retrieval quality установленным.

Native sizes: Grounded limit3 p50/p95 1,234/3,087 tokens; limit5 1,873/4,709. DocAtlas 765/797. Разница существенная, но это пока не измерение total task bill.

## 4. Grounded на самом проекте: 20 исходных запросов

Корпус 134/134 files, 839 chunks, zero embeddings. Первый directory scrape не включил CHANGELOG; exact-file supplemental ingest завершён до query phase. Неожиданных corpus URLs после проверки нет.

Условия: 10 RU и 10 EN, без rewriting/lookups, limit3. Cases выбраны по механизмам, не случайно. Нет единого numerical success rate: native Grounded не получает DocAtlas source-policy/lifecycle contract, поэтому usability исторического текста нельзя автоматически считать current authoritative support.

| ID | Наблюдение по native Grounded |
|---|---|
| A02 | README даёт sync/lifecycle workflow; много полезного текста, существенно больший packet. |
| A05 | Только старый readiness review, не scope=all rule. |
| A07 | Старый readiness review, не project-doc discovery/inspect contract. |
| A09 | Release/publisher remediation вместо stale Markdown sync. |
| A11 | Retrieval implementation plan и prefetch examples, неполное refresh/sync различие. |
| A14 | Runtime/job inventory и historical first-divergence atlas; нет direct stop-on-no-progress policy. |
| A18 | Нужные lexical/vector settings найдены; conflicting fallback troubleshooting тоже доставлен. |
| A23 | Readiness review вместо actual whole-response budget. |
| A25 | Readiness review вместо host supported-part synthesis при false flags. |
| A29 | Readiness review вместо prompt-injection trust policy. |
| B03 | Readiness review вместо host answering contract. |
| B04 | SKILL scope=all workflow пригоден для navigation; explicit module semantics менее ясны. |
| B08 | **README sync/change reconciliation найден, тогда как обе DocAtlas lanes его пропустили.** |
| B10 | Canonical query-read-only statement найден; одновременно superseded ADR distractor. |
| B14 | Старые budget/index roadmaps вместо current whole-JSON metadata fact. |
| B17 | Readiness review вместо source_changed reader contract. |
| B20 | **Partial-answer Final handoff найден; guided DocAtlas потерял этот useful fact.** |
| B23 | Readiness review вместо project identity isolation. |
| B28 | History/planning объясняет title/proof issue, но это не current runtime source authority. |
| B34 | Version/main mismatch предупреждение есть, editor process command verification отсутствует. |

`A/B` здесь обозначают prefix `projectA/projectB`. Полные тексты: `raw/grounded-project20/native/<ID>.json`.

На русских запросах в английский корпус pure lexical Grounded также систематически находит большой русскоязычный historical document. Поэтому тезис «у них просто FTS, значит нам тоже хватит FTS без multilingual/context policy» не подтверждён.

## 5. Context7: десять actual hosted запросов

Каждый original external question передан без переписывания. Library ID выбирается через resolver; query output сохранён отдельно. Во время первого запуска одна resolver transport operation превысила 30-second client timeout; продолжение с 90-second timeout завершило всю панель. Это не zero-failure reliability measurement.

| Case | Library ID | Tokens | Консервативный review | Что действительно доставлено |
|---|---|---:|---|---|
| fastapi-02 | `/websites/fastapi_tiangolo` | 624 | Full | Normal def function зарегистрирована в BackgroundTasks.add_task. |
| fastapi-04 | `/websites/fastapi_tiangolo` | 436 | Full | Default credentials False, prohibition on wildcards прямо в prose. |
| starlette-03 | `/kludex/starlette` | 287 | Full | Teardown после closed connections и completed in-process tasks. |
| typer-01 | `/websites/typer_tiangolo` | 469 | Partial/uncertain | Exit не обязательно error, code0 = success; numeric omitted-parameter default не привязан явно. |
| pydantic-02 | `/pydantic/pydantic` | 785 | Partial/uncertain | Python strict versus JSON conversion; конкретный UUID-string strict JSON case не показан напрямую. |
| pydantic-03 | `/pydantic/pydantic` | 947 | Full | validation-call > Field > model_config, с executable examples. |
| httpx-03 | `/encode/httpx` | 807 | Full | Все четыре distinct timeout limits описаны. |
| mkdocs-05 | `/mkdocs/mkdocs` | 548 | Full | Полный title order, stop-at-first и setext caveat. |
| ruff-01 | `/astral-sh/ruff` | 542 | Full | Closest config, no implicit merge, explicit extend. |
| uv-05 | `/websites/astral_sh_uv` | 1,124 | Full | First-index versus pip combined indexes; имя стратегии отличается от старого snapshot. |

Два partial verdicts намеренно conservative: допустимость logical implication стоит независимо перепроверить. Они не означают, что Context7 вернул неправильные факты. Главное — не добирать полный ответ из model memory.

В FastAPI04 code example использует wildcard methods/headers вместе с credentials=True, а prose утверждает, что wildcards нельзя. Для вопроса про origins/default нужные facts есть, но snippet-internal consistency не идеальна. Хорошая выдача Context7 не означает, что каждую detail в каждом example можно принять без анализа.

### Почему examples полезны

MkDocs05 возвращает прямо ordered list, а не ссылки на config. Pydantic03 — сразу precedence и concrete examples. HTTPX03 — definitions, а не одну constructor signature. Такой material хорошо подходит coding model.

Но на этих же десяти cases DocAtlas frozen local packets тоже recognized sufficient. Этой панелью не доказано, что hosted Context7 выиграл итоговый answer/patch quality.

### Что публично известно об architecture

Context7 API guide описывает automatic library selection, searching и reranking code/information snippets:

- <https://github.com/upstash/context7/blob/master/docs/api-guide.mdx>
- <https://github.com/upstash/context7>

Это не описание точной private hosted scoring implementation. Нельзя вывести из MCP output размер corpus, embedding model, preprocessing/annotation quality или ranking training. «Надо взять их embedding и всё заработает» — неподтверждённая гипотеза.

## 6. Практический вывод

**Grounded:** полезный reference по простоте/скорости native retrieval и объёму соседнего текста, не drop-in замена authority/scope/version evidence runtime.

**Context7:** сильный reference по library-focused, code-rich и вопросно-релевантной доставке. Для parity/superiority требуется source/version/budget-controlled end-to-end evaluation.

**DocAtlas:** уже хорошо доставляет узкие facts с tight budget, но проигрывает собственному пользовательскому сценарию на смешанном repo corpus. Приоритет — исправить этот путь, а не объявлять внешний tiny benchmark доказательством готовности или сменить сервер без измерения.

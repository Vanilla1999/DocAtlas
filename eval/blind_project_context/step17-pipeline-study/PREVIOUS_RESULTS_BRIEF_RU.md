# Краткая выжимка предыдущего исследования Qwen (step16)

## Что проверено

96 кейсов / 260 fact-cases на вариант; A — default lexical compact/adaptive, B — тот же checked pool/отсев/eligibility/MMR/fitter с Qwen relevance. 8 вариантов, 768 настоящих MCP-ответов. Авторитетна точная первая строка TextContent, а не внутренний trace. Во всех ответах выполнено `max(o200k_tokens, ceil(UTF8_bytes/4)) <= budget`. Raw/post-prune/eligible manifests A/B совпадают. Default продукта не переключён.

| Бюджет | A факты | B факты | A полные кейсы | B полные кейсы | A реальные tokens, сумма | B реальные tokens, сумма |
|---:|---:|---:|---:|---:|---:|---:|
|1500|51|139|14|46|130723|117733|
|3000|83|175|28|61|253931|190181|
|6000|120|181|42|63|485198|260791|
|12000|176|181|62|63|828688|301579|

B3000 против A12000: -77.05% delivered tokens, но наборы НЕ эквивалентны: 17 новых и 18 потерянных факт-кейсов. B6000 против B12000: все 260 статусов фактов совпадают; 12000 расходует +15.64% tokens без нового измеренного факта. Это доставка доказательств, НЕ измеренное качество ответов отвечающей модели.

## Где наблюдаются потери B6000/B12000

Из 79 недоставленных факт-кейсов: 24 без точного single-row свидетеля в raw checked (причина неизвестна); 31 с raw-свидетелем, исчезнувшим после pruning; 24 со свидетелем среди eligible, отклонённым с nonpositive_gain. Нельзя объявлять отсутствие одной цитаты отсутствием любого составного доказательства. У последних 24 raw Qwen scores низкие (медиана .0078196), поэтому один redundancy penalty не доказан как причина.

B12000 не прошёл прежний holdout non-regression gate: L0/ru 24→19, L2/en 15→12; в целом 20 приобретённых / 15 потерянных факт-кейсов. Старый holdout уже раскрыт и не используется как свежая проверка новых вариантов.

## Стоимость и пределы

Свежий B12000: 7184 forwards, 6,791,020 Qwen input tokens; 192.33s суммарного inference; 283.60s scorer wall включая 59.55s проверки assets; 4 model loads. Малые бюджеты использовали exact cache: это НЕ сравнение cold latency. Экономия MCP-контекста не равна экономии всех вычислений.

C/E5 заблокирован отсутствием frozen candidate-level artifacts. Дополнительный Q6 не входит в 260 sealed facts. У всех вариантов были continuations, но follow-up не вызывался.

## Что хранится после компактизации

- `step16/paired-campaign/*/payloads/`: точные доставленные ответы (не изменяются).
- `step16/paired-campaign/*/{run,score,start}.json`: первичные результаты/launch provenance (не изменяются).
- `step16/paired-campaign/{A,B}-{budget}.jsonl.gz`: ВСЕ байты старых полных trace после распаковки; до удаления несжатого дубля сверяются SHA256 и размер.
- `step16/paired-campaign/{A,B}-{budget}.index.jsonl.gz`: все события и решения без четырёх тяжёлых массивов raw/normalized rows/snapshots. Это индекс, не замена полного архива.
- `step16/paired-campaign/COMPACTION_RECEIPT.json`: точные пути, SHA256, размеры, числа событий и подтверждения удаления только несжатых дублей.
- Публикуемые RESULTS_RU.md, facts_by_budget.json, funnel_by_fact_case.csv и qwen_runtime_receipt.json сохранены в step16-qwen-delivery; analysis commit `14d05208ce43589d51f93ed089c533de740d5600` уже отправлен в remote ранее.

База путей больших внешних артефактов: `/home/viadmin/.local/share/docatlas-eval/`. Репозитории, prepared stores, model assets и score caches не удаляются. Архивы можно читать потоково через `gzip.open(path, 'rt')`, не распаковывая гигабайты на диск.

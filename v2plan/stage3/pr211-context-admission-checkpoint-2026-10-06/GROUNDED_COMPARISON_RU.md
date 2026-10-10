# Grounded MCP: ограниченное живое сравнение

Дата: 2026-10-06. Индексация: примерно 09:00 UTC.
Цель: выяснить, возвращает ли Grounded материал без запрошенного факта и теряет ли
полезную numeric paraphrase. Это не совместный CI и не эквивалент frozen module test.

## Среда и метод

`grounded.list_libraries()` первоначально ответил `No libraries indexed yet.`
Использован доступный Grounded MCP, без подмены его retrieval. Сначала проверена
доступность синтетической страницы через `fetch_url`, затем проиндексированы три
новые изолированные библиотеки версии `0.0.1`, по одной странице каждая.

Страницы — только приведённый ниже придуманный текст. URL формируется как
`https://httpbingo.org/base64/` + percent-encoded стандартный Base64 UTF-8 текста,
включая завершающий newline. Код и документы репозитория не публиковались.
HTTP echo endpoint позволяет обслужить source bytes без изменения репозитория.

`scrape_docs`: `maxPages=1`, `maxDepth=0`, `scope=subpages`.
Все три jobs завершились `completed`. Затем каждому `search_docs` переданы:

```json
{
  "library": "<имя из таблицы>",
  "version": "0.0.1",
  "query": "How many retry attempts does ProjectRetryPolicy allow?",
  "limit": 3
}
```

| Случай / library | Job ID |
|---|---|
| `pr211-comparison-split-20261006` | `257134f5-0bb0-46b1-9101-05210b00f8cb` |
| `pr211-comparison-no-value-20261006` | `0b0715f1-c950-43dd-8caf-7fb4eb21d98d` |
| `pr211-comparison-other-subject-20261006` | `180fe13b-2434-42c5-af6d-a607b344be95` |

Созданные библиотеки оставлены в Grounded под этими именами для воспроизведения;
refresh/remove существующих библиотек не выполнялись. Версия сборки и настройки
индекса Grounded этим интерфейсом не установлены; вывод относится к данному endpoint.

## Source bytes и фактически возвращённый текст

### 1. Полезный факт в перефразировке

URL:
`https://httpbingo.org/base64/IyBQcm9qZWN0UmV0cnlQb2xpY3kKClRoZSByZXRyeSBwb2xpY3kgYWxsb3dzIGF0IG1vc3QgdHdvIGF0dGVtcHRzLgo%3D`

Исходный текст и тело `Result 1` совпадают:

```markdown
# ProjectRetryPolicy

The retry policy allows at most two attempts.
```

**Наблюдение:** heading и нужный факт доставлены. В отличие от отвергнутого A,
потери этой перефразировки не обнаружено. Baseline DocAtlas тоже доставляет её.

### 2. Отсутствие запрошенного числа

URL:
`https://httpbingo.org/base64/IyBPcmRlcnMKCk9yZGVyU3VibWlzc2lvbiB2YWxpZGF0ZXMgYSBkcmFmdCBhbmQgZGVsZWdhdGVzIG5ldHdvcmsgcmV0cnkgZGVjaXNpb25zIHRvIFByb2plY3RSZXRyeVBvbGljeS4K`

Исходный текст и тело `Result 1` совпадают:

```markdown
# Orders

OrderSubmission validates a draft and delegates network retry decisions to ProjectRetryPolicy.
```

**Наблюдение:** Grounded вернул тематический документ без requested count.
Отказа/пустой выдачи на этот запрос не было. Это похоже на наблюдаемое поведение
нашего partial retrieval, но не доказывает нарушение контракта Grounded.

### 3. Число другого компонента

URL:
`https://httpbingo.org/base64/IyBQcm9qZWN0UmV0cnlQb2xpY3kKClByb2plY3RSZXRyeVBvbGljeSBkZWxlZ2F0ZXMgcmV0cnkgZGVjaXNpb25zIHRvIE90aGVyV29ya2VyLCB3aGljaCBhbGxvd3MgbmluZSByZXRyeSBhdHRlbXB0cy4K`

Исходный текст и тело `Result 1` совпадают:

```markdown
# ProjectRetryPolicy

ProjectRetryPolicy delegates retry decisions to OtherWorker, which allows nine retry attempts.
```

**Наблюдение:** возвращён фрагмент с чужим числом. Grounded не написал отдельный
ответ «ProjectRetryPolicy allows nine attempts». Из цитирования исходной фразы
не следует ложная semantic attribution или ошибка downstream ответа модели.

## Формат фактического ответа и границы сравнения

Каждый вызов вернул текстовый список: разделитель, `Result 1: <исходный URL>`,
Markdown source выше. В ответах нет нашего `answer_supported`, `edit_ready`,
`facet_coverage`, `insufficient_evidence` или модели mandatory witnesses.

Объявленный API `search_docs` имеет library/version/query/limit. В нём нет нашего
repository `module_path`, typed question contract или `packet_tokens`. Параметр
`scope` у scrape относится к границе crawl, не к project/module admission.
Поэтому эти пробы не проверяют:

- module/project leakage исходного frozen adversarial;
- authority_duplicate / source-of-truth versus supporting;
- exact-anchor/original public attribution, forged trace и heterogeneous merge;
- 256/300/800-token packet contracts;
- обязательные CI gates и корректность ответов host LLM.

Одна страница на библиотеку не проверяет ranking среди конкурирующих источников;
три запроса не измеряют частоту проблем на реальной нагрузке. Source transport и
корпус отличаются от наших локальных repository fixtures. Это сравнение отдельных
наблюдаемых проявлений, не доказательство эквивалентности систем.

## Ответ на вопрос «у Grounded тоже есть эти проблемы?»

**Частично да, если под проблемой понимать выдачу документа без нужного ответа
или с числом другого subject. Это непосредственно наблюдалось.**

**Нет доказательства той же ошибки proof/admission.** Grounded в этой проверке
показывает search results; он не обязан по известному нам API сертифицировать
ответ. Полезную heading/prose перефразировку он сохранил.

Результат поддерживает реалистичное ожидание «retrieval может быть неполным».
Он не позволяет автоматически признать допустимыми ложную answer authority,
нарушение scope/provenance/budget, регрессию полезной цитаты или красный required CI.
Изменение нашего frozen contract требует отдельного объяснения и согласования.

Связанный документ: [план merge #211](MERGE_PLAN_RU.md).

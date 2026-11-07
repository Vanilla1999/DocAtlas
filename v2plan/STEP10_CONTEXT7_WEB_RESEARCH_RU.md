# Как Context7 сокращает контекст: публичные материалы

Дата изучения: 2026-11-06. По запросу владельца использованы обычные web search,
HTTP-чтение официальных страниц Upstash/Context7 и публичного GitHub. Context7
MCP, retrieval API, model inference и продуктовые прогоны DocAtlas не вызывались.
Это исследование опубликованной архитектуры, не независимый benchmark сервиса.
Новый relation-classifier design владельцу не понравился; это исследование
не разрешает его implementation или capability calls.

## Основной вывод

Context7 публично описывает предварительное извлечение/обогащение snippets,
индексацию, векторный поиск, серверный reranking/selection и дедупликацию.
Успех измеряет качеством retrieval/ответов и размером контекста. Публичного
доказательства сохранения всех обязательных межсекционных зависимостей,
эквивалентного нашим required facts/units gates, не найдено. Это не основание
утверждать отсутствие такого механизма в закрытом backend.

## Подтверждённые механизмы

1. **Подготовка при индексации.** Статья запуска (2025-03-31) описывает parse
   code snippets/examples → LLM explanations/metadata → embeddings → custom
   reranking → Redis cache. Это исходное опубликованное описание, не полный
   аудит текущего backend.
   https://upstash.com/blog/context7-llmtxt-cursor

2. **Отбор на сервере.** Обновление 2026-01-07 перенесло фильтрацию и reranking
   от дорогой клиентской модели в Context7, чтобы сократить repeated tool calls.
   Заявлено ~9700→3300 returned-context tokens (-65%), 24→15s и3.95→2.96calls.
   Основа — internal80+questions, Claude Haiku с tools, Sonnet judge helpfulness
   1–10. Это publisher benchmark, не byte/fact completeness proof и не учёт
   всех server-side model tokens. Авторы прямо признают увеличение собственных
   вычислительных затрат за счёт reranking.
   https://upstash.com/blog/new-context7

3. **Snippets с разных страниц.** Статья2026-04-28 объясняет query-dependent
   объединение извлечённых фрагментов независимо от page boundaries; source URL,
   page/breadcrumb и metadata позволяют вернуться к исходнику. Точный private
   extraction/reranking prompt, model и dependency policy не опубликованы.
   https://upstash.com/blog/c7-vs-web-search

4. **Дедупликация.** Exact match + cosine similarity + additional uniqueness
   filter для code; exact/overlap для informational snippets. Version analysis
   уменьшает смешение старых и новых docs. Это не разрешение нам дедуплицировать
   разные условия как «похожие»: сохранение facts нужно проверять отдельно.
   https://upstash.com/blog/context7-quality-and-safety (2026-01-26)

5. **Текущий retrieval contract.** /v2/context отдаёт ranked codeSnippets и
   infoSnippets; fast=true пропускает LLM reranking и возвращает vector results.
   В текущей спецификации нет параметров произвольного tokens budget или pagination;
   старые обзоры API нельзя выдавать за актуальный контракт.
   https://context7.com/docs/api-reference/context/get-documentation-context

6. **Дополнительный контекст для широкого вопроса.** /v3/search выбирает до4libraries,
   параллельно извлекает snippets, дедуплицирует и глобально reranks результат.
   Текущий параметр context=broad добавляет sections лучших найденных страниц
   примерно до3500extra tokens. Для how-to/migration/troubleshooting/overview
   вопросов такие sections добавляются автоматически. Это bounded context
   expansion, а не опубликованное доказательство all-reference closure.
   https://context7.com/docs/api-reference/search/search-documentation-in-one-request

7. **Ограниченная гарантия версии.** Текущие API docs допускают fallback на другую
   stable/current документацию при отсутствии requested version с явным
   version/status note. Поэтому общее маркетинговое «exact version» нельзя
   переносить в DocAtlas как строгую native scope/version гарантию.

8. **Client surface.** Открытый packages/mcp/src/index.ts требует focused query
   на один concept и рекомендует не более3calls/question. Это инструкция агенту,
   не программно доказанный hard cap. packages/mcp/src/lib/api.ts отправляет
   query/libraryId/language в backend и возвращает его текст; сам closure не
   реализует. README прямо говорит, что API backend/parsing/crawling private.
   https://github.com/upstash/context7/blob/master/packages/mcp/src/index.ts
   https://github.com/upstash/context7/blob/master/packages/mcp/src/lib/api.ts
   https://github.com/upstash/context7#disclaimer

## Близкий к нашей проблеме реальный отчёт и исправление

Issue3548 от2026-10-26: в source-linked activity были удалены две локальные
definitions, но использование одной переменной осталось. Автор приложил output
и immutable source; материал synthetic, автор владеет исходным примером.
Мы этот runtime случай не воспроизводили.

2026-11-05 collaborator сообщил об исправлении copy step:
- copied snippet сохраняют только при точном совпадении с исходным файлом;
- пропущенные строки восстанавливают из исходника;
- переставленный/отредактированный snippet отбрасывают;
- конкретный bad snippet удалён, прежний query больше его не возвращает.

Это свидетельство заявленного исправления source fidelity в copied snippets,
не доказательство успешного ответа на прежнюю задачу после удаления snippet и
не общего сохранения междокументных conditions. Fix независимо не проверен.
https://github.com/upstash/context7/issues/3548
https://github.com/upstash/context7/issues/3548#issuecomment-6653526725

## Опубликованное качество — не 100%

2026-10-27 Upstash опубликовал Context7 Search vs Exa3.0 на WebCode RAG:
307questions, до10results,3runs, общий answer model и judge.
Заявлено Context7:85.7%correct,2.3%wrong, остаток≈12% abstention,
~1050response tokens,~3.7s median search latency. Exa Lite/Auto:86.2%correct,
~5020/~4650tokens. Это измерение ответов с retrieved evidence, выполненное
разработчиком Context7; наши41facts/quality gates им не проверялись. Число
response tokens не включает внутренние parsing/reranking provider tokens.
https://upstash.com/blog/context7-search-webcode

## Что это означает для DocAtlas

- Публичный практический подход Context7 — качественная подготовка units и
  query-dependent retrieval/reranking, плюс bounded expansion при нужде.
  Оснований считать, что проблему потери условий они решили классификацией
  каждой ссылки или обходом всех hyperlinks, нет.
- Whole-document closure из TOC — наше выбранное ограничение V3; оно не следует
  из опубликованного подхода Context7. Его blocker не доказывает невозможность
  компактного retrieval вообще.
- Source-exact correction относится к целостности выбранного фрагмента.
  Наш V-M1 отличается: целый нужный target section не был выбран. Одна точная
  копия Transfer не восстановит отсутствующие weather conditions.
- Заимствование snippets/expansion потребует отдельного изменения текущего
  whole-unit/no-caps контракта. Поиск Context7 не разрешает менять наши criteria
  задним числом или объявлять прежнийFAIL успешным.
- Полезный следующий предмет обсуждения — единица retrieval и способ показать
  агенту недостающий контекст, с независимой проверкой исходных задач. Здесь
  не предлагается и не реализуется ещё один relation classifier.

Текущие ограничения остаются: исторический validationFAIL, V3blocked,
отсутствие доказанной end-to-end экономии Terra; public/model calls не разрешены.

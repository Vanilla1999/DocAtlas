# Step12: настоящий Qwen + Terra Low, локальный diagnostic

**12 сессий завершили ответы; 11 без ошибки retrieval, одна с CUDA OOM.**
Полного успешного сравнения четырёх вопросов нет. Новых inference/reruns после
обнаружения сбоя не было. Это seen-development diagnostic, не rollout acceptance.

## Условия и границы

- Commit73848aa9, isolated installed wheel,441 Python files совпадают с checkout.
- RTX5070Ti; pinned Qwen revision e61197ed45024b0ed8a2d74b80b4d909f1255473,
  все9asset hashes проверены. torch2.10.0+cu128, transformers4.57.1,
  tokenizers0.22.2, safetensors0.8.0, BF16/SDPA/capability12.0.
- Исходная frozen policy, SHA25616fb92b9687d68c30cdc8bfa8656b20d512da2b9b8600497ed78a0f5742d0f11.
- OpenCode2.2.5, настоящий Terra gpt-6.1-terra/low,39 provider requests,
  0 observed retries,0 capture errors. Одинаковые4исходных question bytes.
- Один isolated project: шесть исходных Meridian project-документов. Excluded
  module не скопирован ни в один вариант; это не новая проверка module denial.
  Общие AGENTS и source-to-draft paragraph одинаковы. Backend-specific инструкции,
  schemas и presentation различаются; это сравнение целых методов доставки.
- Native files может читать каталог и общий AGENTS; gold/answers вне corpus.
  MCP compact literal-v2, Code Mode off, MiniLM off, Qwen unchanged.
- Raw captures содержат provider usage и attribution, exact prompts/tool results.
  Каждый источник MCP сверён с исходным текстом и диапазоном строк; native read
  строки также сверены. Факты для delivery взяты из неизменного tasks.json.
  Model questions/effort и суммы CLI/provider usage проверены offline.

## Сопоставимый результат: три вопроса с19обязательными фактами

Четвёртый вопрос не имеет положительных gold facts и рассматривается отдельно.

| Метрика | Qwen off | Qwen one-hop | Файлы |
|---|---:|---:|---:|
| Факты доставлены |16/19|19/19|19/19|
| Полностью отражены в ответе |15|16|15|
| Частично отражены |0|1|2|
| Пропущены |4|2|2|
| Provider input, включая cache |25193|22121|13872|
| Cached subset |14464|9472|5376|
| Uncached input |10729|12649|8496|
| Output, включая reasoning |967|1018|1135|
| Provider requests |10|9|9|
| End-to-end seconds |49.56|45.30|32.63|

**One-hop восстановил механизм потери погодных условий, но не дал полной
сохранности конечного ответа.** На V-M1 выбраны те же4units; расширение прошло
по2ссылкам и добавило4spans: weather Suspension с введением и calendar Colours
с введением. Навигационная ссылка здесь взята из самостоятельно выбранного
Qwen seed-введения, а не из произвольно добавленного ancestor frontier.
Delivery V-M1 вырос5→8фактов. Off сделал дополнительный запрос weather.md,
но scorer не пропустил ни одного его раздела; это не отсутствие источника.

V-M2/V-M3 не получили дополнительных spans. Разница final answers на V-M3
при одинаковой выдаче показывает вариативность генерации; один прогон не
доказывает статистически значимое превосходство one-hop по итоговому качеству.

### Семантическая проверка final answers (parent)

- V-M1 off:5full/0partial/3missing. Все transfer/lock/applicability условия
  есть; три weather obligations не получены и не отражены.
- V-M1 one-hop:7full/1partial/0missing. Stop outdoor observations when wind
  interlock opens передано через уже состоявшуюся приостановку; как в прежнем
  review, это partial, а не явная обязанность остановить наблюдение.
  Preservation during suspension и оба restart conditions отражены полностью.
- V-M1 files:6full/2partial/0missing. Аналогичная неполная stop-duty;
  identifier сохранён явно при transfer, но не явно during suspension — partial.
- V-M2 все варианты:5full/0partial/1missing. Вводное execution/ownership
  различие доставлено, но пропущено в ответах, несмотря на source-to-draft audit.
- V-M3 off:5full. One-hop/files:4full/1missing — предварительная проверка часов
  перед выполнением расписания доставлена, но не вошла в final answer.
- V-M4 off: корректное ограниченное воздержание от значения и от доказательства
  отсутствия общего требования по пустой выдаче. Files: не выдумывает значение,
  но утверждение об отсутствии требования опирается на поиск и прочитанные
  overview/architecture/catalog, а не на полное прочтение всех документов.
  One-hop: сообщает технический сбой, **не PASS no-answer**.

## Четвёртый вопрос и ошибка harness

У каждого MCP session location оказался собственный долгоживущий сервер,
сохраняющий Qwen в GPU memory. После7успешных загрузок8-я (one-hop V-M4)
не поместилась. Raw error перечисляет7процессов по~1.43GiB плюс пользовательские
приложения; свободно78.56MiB. Сбой на загрузке, model_forwards=0 в этом вызове.
Это ошибка управления lifecycle в данном runner, а не доказанная регрессия
памяти one-hop. Его небольшие токены/время V-M4 нельзя выдавать за оптимизацию.
Runner проверял exit0 и CLI error events, пропустив structured scan_incomplete;
поэтому после ошибки исполнился запланированный files V-M4. Факт не скрыт.
Все8созданных экспериментом MCP-процессов остановлены по exact executable+state
environment, см. cleanup.json. Чужие приложения не останавливались.
Перед новым запуском нужны teardown/reuse model-server и fail-fast на structured
scan_incomplete. Текущий run.py сохранён как воспроизводимый исходный harness,
не исправленная версия для повторного запуска. Повтор требует отдельного решения.

## Фактический расход всех12сессий, включая сбой

| Метрика | Qwen off | Qwen one-hop* | Файлы |
|---|---:|---:|---:|
| Input |34911|29163|20006|
| Cached subset |20736|13312|8832|
| Uncached |14175|15851|11174|
| Output |1188|1153|1428|
| Requests |14|12|13|
| Seconds |68.92|57.56|43.57|
| Instructions input |13692|11760|8905|
| Tool schemas input |12600|10800|6097|
| Question/calls/results/history input |8619|6603|5004|

*One-hop totals включают failed V-M4 и не являются полным успешным вариантом.
Общий расход:84080input,42880cached subset,41200uncached,3769output.
Системные блоки~978/980tokens на MCP step и685на files step; schemas900и469.
Последняя категория объединена: отдельного надёжного разделения результатов
документов и их служебного оформления здесь не заявляем. Raw attribution сохранён.
История учитывается повторно на provider side через previous_response_id;
это не равнозначно повторной передаче всего контекста по сети.

One-hop снизил inclusive input на трёх успешных вопросах, но uncached вырос;
денежную экономию без тарифов заявлять нельзя. File setup здесь экономнее обоих.
Время — wall time всего сеанса, включая provider/tool startup и Qwen, не чистое
время модели. Отдельный GPU inference timing/peak успешных вызовов публичная
выдача не содержит; измерения не выдумывались. Число successful Qwen pairs
в публичных receipts: off109, one-hop63, files0. Downloads/setup исключены из
session times. Авторизация и каталог до исполнения не считались inference PASS.

Подробности: accounting.json, audit.json, raw-manifest.json и
`<arm>/<case>/final-answer.txt`, `raw.jsonl`, `capture/events.jsonl`.

# Step10: источник лишних кавычек в вопросе

2026-11-06. Родительская проверка во время контролируемого исполнения Astra Low.

## Доказательство

Историческое сохранённое user message OpenCode
`msg_1b19b03690012AMgFDVRIZBiWk` в session
`ses_e4e64fcf0ffeDGGXiZi9TslFbt` уже содержит **буквальные внешние кавычки** внутри
`text`. Фактический MCP question совпал с этим user text. Значит прежняя атрибуция
«Terra добавила кавычки» ошибочна: изменение произошло до answering model.

В `run_gap_agent_study.py` frozen question передавался отдельным позиционным
аргументом `subprocess.run(["opencode", "run", ..., case["question"]])` без shell.

Новая transport-проверка использует настоящий OpenCode **2.2.5**, тот же frozen
T01 и scripted localhost provider. Последний только записывает реальный HTTP
request и завершает ответ; DocAtlas и платная модель не вызываются.

| Маршрут | Persisted user text == frozen question | Provider user content == frozen question |
|---|---|---|
| `opencode run` с позиционным аргументом | FAIL: добавлены внешние `"` | FAIL: те же `"` |
| JSON API `/api/session/{id}/prompt`, поле `text` | PASS | PASS |
| `opencode run` без позиционного сообщения, точный текст через stdin | PASS | PASS |

Исходная UTF-8 SHA256 вопроса:
`22aa9105536830f76ea8651e6dc3ae7c1780bd792023fa97f41650c6c8bd1e1a`.
Сравниваются декодированные строки, поэтому это не путаница с JSON escaping.

## Границы вывода

- Доказан дефект точности входа в использованном CLI-маршруте версии2.2.5.
- Это не доказательство ошибки всех версий CLI или MCP транспорта.
- Новые исходные T01 public probes без кавычек по-прежнему дают0/3 у V3.
  Клиентский дефект не объясняет весь провал semantic selection.
- Исторические61 419 tokens и3/3 facts остаются фактическими измерениями, но
  exact-frozen-question comparison остаётся FAIL.
- Серверная нормализация/снятие кавычек не требуется и не применяется.

## Артефакты

- `probe_client_question.py` — воспроизводимый transport-only сценарий;
- `step10-client-question-audit/receipt.json` —2 маршрута и точные строки;
- `step10-client-question-stdin/receipt.json` —отдельный проверенный stdin путь;
- там же `cli-argv.json`, `cli-messages.json`, `api-messages.json`,
  `provider-1.json`, `provider-2.json`, исторические user messages и hashes.

Исполнителю передано минимальное исправление runner: передавать вопрос через
`subprocess.run(..., input=case["question"], text=True)` без позиционного message.
Это сохраняет существующий JSONL-accounting маршрут. Указанный transport должен
быть записан в manifest нового прогона. Сам answering model всё ещё может изменить
MCP arguments; это отдельно проверяется фактической трассой будущего Terra run.

Стоимость проверки:3 scripted provider requests,0 Terra calls. Это проверка
клиентской границы, не retrieval/answer acceptance.

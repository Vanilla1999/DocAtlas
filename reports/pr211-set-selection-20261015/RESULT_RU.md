# Prompted set selection: реализация есть, пилот остановлен на transport FAIL

**Обновление:** владелец разрешил продолжить; transport исправление сработало.
Новая попытка дала97.79% сокращения DTO, но P03 witness442/515 — semantic
selection FAIL. Актуальный результат: `PILOT_02_RU.md` и `pilot-02/RESULTS.json`.
E01/V40 не запускались. Ниже — неизменённое описание первой попытки.

База PR211: `aa48b05787a3bdc9c58f0f3d6aa965139585cd9f`.
Opt-in host context: `experimental_set_selector(generate, config=SetSelectorConfig(...))`.
Вызов добавлен в native projector после recheck всех исходных окон, до
`context_selection_decision`/`_payload`; итоговый snapshot и validator пересобираются
существующим путём. Без opt-in функция возвращает прежние row objects без вызова
модели. Вход модели не содержит hashes/receipts, а содержит весь checked pool,
путь, section и полный snippet с короткими ID. Неизвестные/повторные IDs,
неверный JSON, пустой выбор и transport error сохраняют весь исходный пул.
Причина доступна host в receipts, не является source/edit/answer authority.
First-fit не возвращён. Режим применён только к native project context path PR211,
не к library/mixed/legacy projection. Это host-only экспериментальный API, а не
новый wire argument или default inference deployment.

## Метод и лимиты

Источник: https://arxiv.org/html/2507.06838v2, §3.2 и §5.3 прочитаны.
Адаптация: information-requirement-guided joint selection без top-k, один общий
prompt, без обучения, без выдачи CoT и без oracle в модельном входе. Другое
семейство модели и 167/256 кандидатов вместо основных paper top20; это не
воспроизведение SetR и не доказательство его результатов на DocAtlas.

Владелец разрешил `openai/gpt-5.6-luna#medium` и приблизительный token count.
Endpoint в конфигурации host: `https://chatgpt.com/backend-api/codex`, через
OpenCode 2.0.29 `/api/experimental/generate`. Подмена provider/model запрещена.
o200k_base плюс64 предполагаемых wrapper tokens, вход не более100000,
резерв8192, configured context400000/input272000/output128000.
Framing и billing токены неизвестны, это не точный tokenizer модели.
Stateless endpoint не позволяет задать output cap;8192 — только резерв, а не
enforced generation limit. Sampling/backend retries не раскрыты; клиентских
повторов0. Text-only stateless request, никаких tools/agent sessions.

## Фактическая попытка

Wheel собран из изменённого кода и установлен отдельно без deps. Loaded product
bytes проверены против исходников. Один реальный cold prepare, два публичных
in-process MCP context calls (A/D) на одной SQLite/проекте. Один CLI transport
attempt, успешных host completions0. Подтверждённого model inference нет.

| Вопрос | Покрытие A/D | DTO-токены A/D | Сокращение | Расход selector | Статус |
|---|---|---|---|---|---|
| P03 |515/515 →515/515|48116 →48116|0%|оценка входа21227; output/billing неизвестны;20.31s transport|FAIL: model_error, весь пул сохранён|
| E01 |не запускался|—|—|0 attempts|STOP после P03|

Входы pool/excluded/complete_candidates A/D совпали. Checked windows/evidence IDs
на входе selector совпали с baseline DTO. Все delivered rows остались неизменны;
source и frozen oracle errors0; SQLite и файлы не менялись за context calls.
Нет successful selection, поэтому `exact_delivery=false` — выбранных IDs нет,
доставлен fallback из167 окон, а не результат модели. Исторические47851 токенов
не использованы как новый baseline: другие project identity/source URI hashes
меняют tokenization; парные пакеты имеют одинаковые144210 bytes и48116 tokens.
Полная проверка historical snapshot metadata не выполнялась; source bytes,
committed content hashes и публичные spans проверены неизменённым evaluator.
Это не installed stdio/client и не проверка сгенерированного ответа.

## Причина остановки и исправление runner

`isolated_service` меняет HOME/XDG_* (runtime.py:86–90). CLI унаследовал изоляцию
данных и попытался запустить отдельный managed service вместо доступного host.
Сохранён stderr: `Managed service port 49374 ... already in use`.
Это FAIL транспорта проверки, не доказательство плохого выбора модели.

Runner после этой попытки исправлен: сохраняет оригинальный host environment до
fixture и передаёт его только subprocess. Secrets не сериализуются и не
попадают в model prompt. Эта правка НЕ ПРОВЕРЕНА новым runtime запуском.
Исходный runner попытки сохранён как `pilot/executed-runner.py`; изменённый runner
не выдаётся за код исполненной попытки. Product-код после попытки не менялся.

Ни E01, ни повтор P03, ни V40 не выполнялись. Для новой попытки после исправления
transport требуется отдельное разрешение, без автоматического повторения.
Сокращение токенов и качество subset selection пока НЕ ДОКАЗАНЫ. Нет unit-tests,
ручных IDs, repair, ретюнинга prompt или изменения oracle.

## Как включить

Встраивающий host явно оборачивает публичный вызов:

```python
from docmancer.docs.application.experimental_set_selection import (
    SetSelectorConfig, experimental_set_selector,
)

with experimental_set_selector(approved_single_attempt_generate,
        config=SetSelectorConfig(model_id="openai/gpt-5.6-luna#medium",
                                 runtime="approved host transport")) as receipts:
    result = call_docs_tool_payload("get_docs_context", request, service)
```

Callback принимает prompt string и возвращает raw response text. Credentials,
timeout и transport находятся у host; source scope/authority остаются у сервера.
Receipts содержат exact prompt/raw response и могут содержать исходные тексты:
сохранять их только в разрешённом месте, не в MCP stdout.

# Step12: реализация связанных условий и проверки черновика

Дата: 7 ноября 2026, Europe/Moscow. Основание — новое поручение владельца
после merge предыдущих работ. Исходная main: `b1eba6c6` (PR246 и PR247 merged).

## Что теперь меняется в продукте

| Место | Изменение |
| --- | --- |
| `minimal_context_selection.py` | После прежнего Qwen scoring/threshold вызывается opt-in one-hop closure. Полный trace не дублируется в model-facing packet; остаются literal pending addresses. Режим и contract hash связаны с continuation. |
| `minimal_context_structure.py`, новый `bounded_context_links.py` | Один переход из собственного текста выбранных правил, точные source spans и предки, без рекурсивного обхода. Отдельное происхождение selected/ancestor/linked и явные пропущенные ссылки. |
| `context_links.py`, `minimal_context_config.py` | Явный host flag и отказ при неправильном значении/несовместимом recipe. Старый default/off не включает модель и не меняет прежнюю выдачу. |
| `profile/common.txt` | Точный ранее исследованный source-to-draft audit: сверить черновик с каждым относящимся к вопросу утверждением источников, дополнить пропуски и убрать неподтверждённое. |
| Клиентская документация/acceptance driver | Инструкция действует для MCP и files; обновление требует нового generated profile. Реальный клиент проверяет её доставку, а не придуманное качество ответа. |

Словари синонимов, названий разделов, вопрос→файл, shortened aliases и
таблицы расшифровки не добавлены. Буквальные имена/адреса исходных ссылок
не являются автоматически выдуманными синонимами.

## Режим включается отдельно

`DOCATLAS_CONTEXT_LINKS=one-hop-v1` допустим только вместе с прежним
`DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT=1` и
`DOCATLAS_MINIMAL_CONTEXT_RECIPE=qwen3-contextual-own-body-evidence-v1`.
Pinned Qwen runtime/assets/policy остаются обязательными по старому контракту.
По умолчанию `off`; обычный файловый/лексический поиск, MiniLM и historical v3
не переключаются молча. Полная инструкция:
[`docs/development/linked-context.md`](../docs/development/linked-context.md).

## Независимый review и исправления

Отдельный reviewer проверил wiring, fingerprint, модельную metadata и
source/scope guards. Найден реальный defect двойного HTML entity decoding:
при двух допустимых похожих адресах могла выбираться неверная секция.
Исправление сохраняет raw href и декодирует его ровно один раз; guard содержит
обе цели и проверяет правильный текст и отсутствие ошибочного.

Дополнительный review нашёл неправильную origin-метку уже выданного предка
при прямой ссылке на него и риск искажения HTML attribute маской inline code.
Первое исправлено без изменения source bytes; второе даёт явный pending
с исходным адресом вместо перехода по искажённому. После этих изменений
повторён только один guard, а не весь Meridian. Первый результат не удалён.
Навигационная маска не пересчитывается для каждой ссылки.

## Что действительно проверено

| Проверка | Результат и граница |
| --- | --- |
| Existing default continuation integration | PASS, 1 scenario: 2 prepare, 13 context, 2 resource reads; 0 models. Вопросы/ожидания не менялись. |
| Structural run-01 | Общий **BLOCKED**: 2 prepare, 5 context, 6 closures. V-M2 6/6→6/6, V-M3 5/5→5/5. V-M1/V-M4 не дошли до нужной стадии обычного поиска. |
| Final structural guard run-02 | PASS только component integration: 1 prepare, 1 context, 2 closures. 3/7→7/7 source facts; scope/navigation/ancestor/depth/HTML ограничения подтверждены. |
| Fresh wheel | 457 packaged files сверены с checkout и изолированной установкой; пропущенных Python modules нет. SHA256 `da1f97ffadd501d40457a170bebc777f9c253464aa3141649a32eae3230a17c4`. |
| Installed default/off SDK stdio | PASS, 1 prepare, 2 context, 1 resource; source fidelity, version denial и state immutability. |
| Invalid host configuration | 3 настоящих CLI startup denials: unknown mode, minimal disabled, incompatible recipe. |
| Real OpenCode 2.2.5 | PASS с первой попытки, MCP4 + files2 scripted-provider requests. Точная инструкция дошла в оба first system prompts; actual tools/read denials и state preservation проверены. |
| Static quality | Whitespace и module-size ≤1000 строк прошли. Frozen scorer/policy/original questions/old gold не менялись. |

Во всех новых запусках **0 свежих Qwen, MiniLM, Terra или другой answering-model
inference**. Для structural replay применены сохранённые реальные Qwen scores,
но настоящий public packet обычного поиска хранится отдельно от reconstruction.
Это не successful final Qwen MCP, не испытание новых source-cursor issuance
на one-hop пути и не замер полноты финального ответа модели.

Два русских Meridian-вопроса не были заменены переводами ради PASS. Исторический
Qwen-path делал complete-scope acquisition, а диагностический outer path —
обычный lexical admission. Он вернул `context_only` до native projector,
поэтому новый closure не выполнялся. Это ограничение текущего доказательства,
а не установленная регрессия one-hop. Нового общего результата 19/19 нет.

## Токены и полнота: без обещаний экономии

На двух воспроизведённых Meridian-вопросах source text не изменился;
reconstructed packet вырос на9 local o200k tokens каждый. В специально
насыщенном пограничными ссылками guard исходники выросли на70 токенов,
а весь reconstruction — на653: существенную часть добавили10 явных pending
references и оформление. Это не средняя стоимость и не provider billing.
Такое дополнение предназначено сохранять условия, а не гарантировать
сокращение текста на каждом вопросе. Риск раздувания metadata остаётся явным;
полный successful-edge trace модели не передаётся, размер всего ответа
проверяется прежним emergency guard.

Общий клиентский prompt вырос **265→313 local o200k tokens (+48)**.
В текущем real-client run first system равен2105 MCP /1815 files, schemas1190/597.
Эти абсолютные числа нельзя напрямую сравнивать с прошлым isolated запуском:
новый fixture находился внутри checkout, и реальные outgoing prompts также
унаследовали его корневой `AGENTS.md` (проверено по raw requests). Инструкции
не удалялись ради уменьшения счётчика. Дополнительный model round аудиту
не назначается; фактическое следование инструкции в этой проверке не измерялось.

Предыдущий answer-only результат Astra 16/19→18/19 относится к Step11,
а не к новому OpenCode/Qwen прогону. В этой реализации нельзя утверждать
«стало лучше прямого поиска» или «все обязательные условия найдены».

## Оставшаяся граница проверки

Нужен настоящий pinned Qwen GPU-host и answering endpoint для одинакового
end-to-end сравнения off/on и MCP/files: те же original вопросы и sources,
полнота доставленных условий отдельно от полноты ответа, actual provider usage
и cached input отдельно. В текущей среде нет требуемого GPU/model assets и
настроенного answering endpoint; контракт не ослаблялся, CPU/другая модель
не выдавались за Qwen. Поэтому one-hop не повышен до default.

Полные данные: [structural report](../eval/blind_project_context/step12-linked-context/REPORT_RU.md),
[client result](../eval/blind_project_context/step12-linked-context/client-run-01/result.json),
[installed result](../eval/blind_project_context/step12-linked-context/installed-run-01/SUMMARY.json),
[configuration denials](../eval/blind_project_context/step12-linked-context/configuration-run-01/RESULTS.json),
[checkpoint](../v2plan/STEP12_LINKED_CONTEXT_CHECKPOINT_RU.md).

PR/merge и CI-статусы подтверждаются отдельно после публикации; эти targeted
PASS не объявляются зелёным полным CI.

Перед публикацией проверен GitHub check-runs исходной main `b1eba6c6`:
полный CI уже красный (в том числе `test`3.11/3.12/3.13, `retrieval-evidence`,
`advanced-contract`, `platform-smoke`, `p1-6-adversarial`,
`p1-agent-truth-closure` и aggregates). Это не объясняет автоматически любой
новый FAIL. Проверки не удалялись, branch protection не изменяется и не
обходится. [Исходный CI](https://github.com/Vanilla1999/DocAtlas/actions/runs/42357354072).

# Step11: буквальный model-facing JSON

Добавлен opt-in `DOCATLAS_CONTEXT_PRESENTATION=literal-v2`. Это изменение
представления уже проверенных источников, без нового поиска, модели или
сокращения исходного текста. По умолчанию и при `off` остаются прежние renderer
и continuation settings. Исторические Qwen FAIL и reference-closure BLOCKED
этой работой не изменяются.

## Включение и контракт

Для обычного MCP text lane:

```sh
DOCATLAS_MCP_TEXT_FALLBACK=1 \
DOCATLAS_MCP_COMPACT_TEXT=1 \
DOCATLAS_MCP_MODEL_VIEW=off \
DOCATLAS_CONTEXT_PRESENTATION=literal-v2 \
doc-atlas mcp docs-serve
```

Поддерживаемый успешный `docs_context` получает marker
`docatlas.standalone-text.v2`. `sources` — обычные JSON-объекты: полный исходный
`evidence_id` в `ref`, исходные `source_uri`, path, строки и буквальный текст.
Общий `source_context` сохраняет полные значения scope/version/authority и другой
общей метаинформации. Сохраняются существующее предупреждение о недоверенном
содержимом, непустые ошибки/пробелы/следующие действия. `source_columns`,
`source_groups`, индексов и коротких ссылок-замен в этом представлении нет.
Новая настройка обходит даже принудительный adaptive layout в minimal-ветке.

Из model-facing sources убран только `content_sha256`; прежние правила
standalone projection для диагностических/default-полей сохранены. Renderer
не изменяет canonical machine packet. Сервер продолжает проверять исходный
hash, snapshot, scope/access, срок действия и расходование capabilities.
Нового скрытого ledger на клиенте не появляется. `patch_context` и source-read
сохраняют свои hashes и прежнюю выдачу. Ошибки, lifecycle и неподдерживаемые
standalone формы используют прежний canonical fallback: marker v2 и удаление
hash для такого fallback не обещаны.

Размер новой выдачи участвует в существующей проверке бюджета. Переключение
представления делает старый continuation token устаревшим; требуется новая
первая порция. При изменении размера может измениться число целых источников,
которые помещаются в ответ. Отключение флага сохраняет старый fingerprint.
Frozen scoring policies и пороги не изменены.

## Что проверено

| Проверка | Результат и граница |
| --- | --- |
| Публичный CLI stdio, обычный режим | PASS: 1 prepare, 6 context calls, 3 resource reads; реальные storage/retrieval/validation, без модели |
| Источники в v2 | Все исходные значения полей, кроме видимого hash, совпали с canonical; факты и UTF-8 текст сохранены; private module исключён |
| Patch/source-read | Patch packet целиком совпал с canonical baseline; read вернул исходный текст и hash; изменение файла дало `source_changed`, повторный read — `source_unavailable`; БД не изменилась |
| Публичный continuation | PASS: смена presentation отклоняет прежний token; явный `off` его принимает |
| 16 сохранённых Qwen packets | OFFLINE REPLAY PASS: 66 source rows, исходные spans/material hashes и полные document hashes проверены; machine packets не изменены |

Первый stdio run сохранил **harness FAIL**: assertion ошибочно требовал
`instruction_trust` внутри ordinary source, где этого поля не было и до изменения.
У ordinary view доверие выражено существующим notice. Исправлена именно проверка:
точный notice, сохранность всех существующих canonical-полей и отдельный patch
`instruction_trust`. Product и исходные тексты fixture между попытками не менялись. Повторён
только этот сценарий; уже прошедший continuation повторно не запускался.
Первоначальные plan/log/XML и receipt сохранены как `public-01*`, успешный
stdio — `public-02*`.

## Размеры: локальный o200k, не provider usage

| Материал | Прежний вывод | Literal v2 | Изменение |
| --- | ---: | ---: | ---: |
| Реальный ordinary stdio, 4 sources | 555 tokens / 1892 bytes | 584 / 1976 | +29 tokens; +84 bytes |
| 16 сохранённых Qwen packets, сумма | 14 284 tokens | 12 325 | −1959; **−13,71%** |
| Те же packets, медиана / максимум | 920 / 1505 | 787 / 1262 | Описательные значения |

Ordinary standalone уже не выводил source hashes; отказ от column packing здесь
немного увеличил ответ. У сохранённых minimal packets hash раньше присутствовал,
поэтому его удаление перекрывает стоимость обычных объектов. Это изменение
видимой метаинформации, а не полностью обратимое кодирование machine packet.

Offline replay использует настоящий новый renderer с ordinary-конфигурацией:
маленькие сохранённые packets проходят её более строгий лимит. **Minimal runtime,
его 50000-token stop и atomic binding новым прогоном здесь не проверены.**
Для него нужны отсутствующие pinned `mmarco-mMiniLMv2-L12-H384-v1` safetensors
и PyTorch runtime; имеющаяся English MiniLM ONNX не подменяет этот scorer.
Новых inference/downloads — 0. Четыре пустых packets используют реконструированный
canonical fallback; у 12 непустых baseline count взят из сохранённых публичных
run receipts. Ни качество ответа агента, ни свежая работоспособность сохранённых
resource URIs из replay этим анализом не доказываются.

## Воспроизведение и артефакты

Публичные сценарии находятся в `tests/test_context_portions_integration.py`:
`test_literal_presentation_public_stdio_preserves_sources_and_read_guards` и
`test_context_portions_bind_snapshot_and_stop_after_exhaustion`. Использован
Python 3.12.14, MCP 1.29.0, pytest 9.0.3, tiktoken 0.11.0; import направлен на
текущий checkout через `PYTHONPATH`. Это **source stdio**, не installed acceptance.

```sh
python eval/blind_project_context/step11-presentation/replay_saved_packets.py \
  --repo /path/to/DocAtlas --out /path/to/new-analysis-output
```

`plan*.json`, `results.json`, `public-*.log/xml`, `public-*-stdio.json` сохраняют
границы и фактические вызовы. `offline-plan/results/receipt.json` связывают
script и проверенные входы. `manifest.json` связывает итоговые файлы и scoped diff.
Старые Blind260 вопросы/oracle не читались.

Для отдельного клиентского installed smoke offline собран wheel
`doc_atlas-1.3.2-py3-none-any.whl`, SHA-256
`73e2bbd73c18a4d20044eb61cc22a0cb78906754bfc4618b79cbf7e70a624070`.
Все 455 packaged `docmancer` files побайтово совпали с рабочим source snapshot;
это записано в `wheel-receipt.json`. Сборка wheel сама по себе не является
installed acceptance.

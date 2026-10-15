# PR211: integration review узких contract fixtures

Дата: 2026-10-08. Base `03583656617336a746e9192249467017d6131f29`.
Root проверил интеграцию после отдельных независимых reviews. Product code,
workflow configuration, corpus/gold, thresholds и diagnostic manifests прежние.

## Два независимых изменения в одном файле

`tests/docs/test_evidence_selection_part02.py` после integration имеет SHA256
`62b324e83ba7159b157493fb747adb2d3cdcb31549246b28c4bc8795256d67e1`.
Provenance node AST-exact совпал с reviewed file SHA256
`ffec1c6d0b0827aab9c1e88e3aea20530ebac49441ecf90c8bb5680a93f89601`;
collision node — с отдельно reviewed SHA256
`cac481ae88391c6855be0a1e2f5ca9b64180f42753b5ea9832b5dc9f742344a6`.
Все остальные module AST nodes полностью совпали с base. Значит, последовательное
наложение двух slices не изменило ни одной проверки друг друга. Ранее reviewed
hashes относятся к своим изолированным версиям; final combined hash указан выше.

## Остальные source bindings

| Файл | SHA256 интегрированных bytes |
|---|---|
| tests/docs/test_action_packet_semantic_density.py | 61a441476a3382148ca6f0c9d120e78a774887c699f1fac9e9b837c6bbd0c0b9 |
| tests/test_web_fetcher.py | 2c6a1e7826c8f4d0e2f424155c14367fb1b362bb2a2b0ef0f4e84860f6149923 |
| tests/docs/test_context_completion_guards.py | 1d52c712f23b5c50745315cf49df6bf5eee96d3007ddb3d03b6e6ecce6373b29 |
| tests/docs/test_query_block_guards.py | a737f1c8fc3af21a623c99d135cd45f70f5830d5b9be351ea6589d8fbb7c872f |

Эти bytes скопированы точно из independently reviewed worktrees. Root повторно
сравнил AST: изменяются только четыре заявленных test functions и две setup
fixtures; все остальные тела, imports, helpers, signatures и decorators прежние.
Collection IDs/параметры сохраняются. Каждый изменённый Python module ниже
действующего предела 1000 строк, static compile без исполнения и diff-check чисты.

Fidelity сохраняет исходный source целиком и все три текстовые проверки;
collision сохраняет разные исходные bindings и требует валидный непустой
same-binding positive. Появившаяся при анализе гипотеза о builder/validator
конфликте отклонена после чтения хвоста selector: он добавляет
visible_content_assignment_required, поэтому no-assignment data остаётся partial.
Новые requirements или ручные authority flags для positive не вводились.

Диагностика не считается исправлением 47 ERROR: она лишь показывает metadata
реального ответа до отсутствующего projector stage. Вложенный MCP error envelope
учтён без вывода raw source или traceback. Финальный CI должен проверить четыре
targeted migrations, сохранение прежних PASS/roster и фактические upstream reasons.

Acceptance JSON/checkpoint содержат завершённый CI **0358365**. Runtime этого
следующего пакета пока **NOT RUN**, а не унаследованный PASS. После обычного
fast-forward нужен совместный CI нового опубликованного SHA. Merge/release/force
не выполнялись; fixed catalog ceiling не возвращён и deferred retrieval не менялся.

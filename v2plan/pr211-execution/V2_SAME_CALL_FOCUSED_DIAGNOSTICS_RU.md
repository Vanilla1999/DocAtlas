# PR211: три focused same-call V2 diagnostics

## Причина

На PR `80c8fbbb3e8c379467a9075f93f7165d080f8432`
[advanced job 114075319327](https://github.com/Vanilla1999/DocAtlas/actions/runs/38006157209/job/114075319327)
действительно завершил V2 evaluator: natural usefulness 6/15, exposed paraphrases 1/5,
acceptance FAIL. Полный результат сохранён в artifact 11651118120, но его binary ZIP
не был прочитан в этой сессии. Из stdout/JUnit нельзя приписать трём отдельным случаям
конкретную потерю на retrieval, qualification, selection или projection.

Печатаем уже вычисленные записи ровно для:
`v2-paraphrase-cache-reset`, `v2-natural-architecture`,
`v2-natural-request-flow`. Это диагностический фильтр, не выборочная acceptance.

## Изменение

База `f7b9253c8e477babf276ae8dd2cb18905451cd15`:
`scripts/run_project_context_quality_v2_gate.py`,
blob `ba291284021bf03d65e2bbe8079d98a0f24fcee2`, mode **100755**.

Runner уже получает полный `run_live()` report или читает указанный `--report`.
После прежнего `verify_v2_acceptance(report)` добавлен только вызов printer.
Тот печатает три JSON строки с префиксом `V2_FOCUSED_STAGE`.
Run/verify/output arguments, один существующий evaluator call, сохранение исходного
полного report, thresholds, FAIL/PASS и exit codes не переписаны.

Каждая строка содержит исходный observed question, число совпавших evaluator/production
records (duplicate или missing не маскируются), неизменный case verdict/obligations,
public kind/status/reason/authorization, source IDs/path/coordinates и SHA-256 snippet.
Из уже captured diagnostics копируются stage status, query/candidate IDs,
qualification reasons и literal matches, current source identity/hash/scope/member
binding, bounded root-reference fields, considered variants/rejections/final IDs.

Evidence body, raw document, owner text, answer body и payload целиком не печатаются.
Printer выбирает известные диагностические поля, не пересчитывает qualification,
не читает corpus/gold или source files и не вызывает retrieval/validation/oracle повторно.
Snippet SHA вычисляется только из уже находящегося в report public snippet.

## Ограничения чтения

- Каждый list в выводе содержит не более 32 записей, собственные `report_count`
  и `log_omitted`; строки длиннее 512 characters получают prefix, полную длину и SHA-256.
  Это только объем private CI logs, не limit на доставку evidence.
- Depth guard 12 явно маркирует omitted value. Исходный report не изменяется.
- Существующий observer сам уже ограничивает свои candidate/outcome/variant arrays
  (32), а `final_visible_evidence_ids` — тремя IDs. Новый printer не знает отрезанную
  до report часть и не заявляет exhaustive runtime trace.
- `selected_candidate_ids` — историческое поле observer из **considered** variants.
  Оно не доказывает принятую selection. Реальная delivery сверяется с
  `payload.sources` / source hashes; отсутствие witness не превращается в доказательство
  конкретного этапа без соответствующей observed record.
- При missing/duplicate case record вывод показывает количество и пустые соответствующие
  поля; никакие новые synthetic outcomes не добавляются в acceptance.
- При `--report` это просмотр имеющегося report с его собственным `run_mode`,
  не новый runtime proof и не утверждение об installed клиенте.

Источники shape: `eval/project_context_quality_v2_protocol.py`
`93833df4ec9587f34724b26fc42dd4ce7a1250e5` (`run_live`, `evaluate_case`),
`scripts/run_project_docs_self_host_gate.py`
`fa68a5a4ea147960321dcaa02950398f14146f2d` (`_call_with_snapshot`),
`docmancer/docs/interfaces/mcp/context_tools.py`
`7a3cb4f113603c27accf3feb44f27f546ff595fd` (`_observe_same_call_diagnostics`),
`docmancer/docs/application/_project_docs_diagnostics.py`
`f222ebfcedea00acf5cf04a76ee8d9be32009f9e`.

## Проверка

Удаление нового printer block и единственного вызова побайтно восстанавливает base runner.
Никаких ordinary test функций, workflow commands, frozen inputs, gold, thresholds,
production files или critical-mutation runner не менялось.
Новый runner SHA-256: `4fc862cbd195d328ce8a0adf7abd9adf7d05738d1931cb5faee0840bae732065`.
Независимый static review contracts и root: APPROVE для runner blob
`82cd79d19d22b37859e72afafea157c995cc200b`; runtime pending.
Следующий обычный V2 CI должен одновременно сохранить прежний полный report,
прежний FAIL/PASS и вывести эти три records. Только затем возможна адресная product
правка frozen quality без изменения исходных вопросов или required facts.

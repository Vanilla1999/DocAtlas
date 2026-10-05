# PR-1 — исправления готовы, этап 3 BLOCKED_BASELINE_CI

Дата: 2026-10-05. Отчёт записан в research-ветку отдельно от проверенного PR.
Main не изменён. Merge/release не выполнены. PR-2 и N10 не запускались.

## Зафиксированные revisions

- main/base: d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c.
- research до этого отчёта: b97206806e899f515b437e0aea4231ee56763bf5.
- отдельная ветка: fix/next07-pr1-output-integrity.
- PR: https://github.com/Vanilla1999/DocAtlas/pull/206 — draft, НЕ merged.
- implementation: 71da4adb985f24021489c1dd8a9d18850f3fe8c9.
- проверенный PR head: 596eeb36b66a474b2b5d246fd6bd834b6dcbb5c6.
- последние изменения 596eeb36: только регистрация новых тестов и review amendment.

Отчёт не меняет SHA проверенного PR. Полный небольшой main→PR diff проверен:
4 коммита, 11 файлов из allowlist; base main сохранён. Полный локальный аудит
всех 75 research-коммитов НЕ выполнен из-за недоступного DNS/checkout. Он не
подменён усечённым compare: в PR перенесены только три отдельно изученные
ответственности поверх exact main tree. Никакого merge всей next07-ветки.

## Что реализовано

1. 76f75d3d: _payload([]) возвращает existing insufficient-evidence DTO,
   а не ok без sources. Не утверждает отсутствие факта во всём corpus.
2. 485b9710: finalized docs_context/docs_answer/patch_context передаётся целиком
   либо возвращается standalone transport_size_limit. Нет clipping с прежними
   hashes/coordinates/support claims. Generic administrative compaction сохранён.
3. 71da4adb: audit_payload читает original bytes с LF/CRLF, сохраняет последний
   перевод строки и отвергает диапазон за концом файла. Semantic evaluator/gold
   не менялись.

Только две runtime-функции и одна eval audit-функция. Default 800/3 и 32000 bytes
main не переключались. Caller-owned compact-режим next07 здесь не переносился.
Retrieval/admission/identity/condition/scope/security guards, parser, owner,
MCP schema/methods, runtime LLM и workflows не менялись. Production не импортирует
v2plan/eval. Review авторский, не независимое одобрение.

## Первый CI: технически invalid, сохранён

https://github.com/Vanilla1999/DocAtlas/actions/runs/37298191615
Job 111724364402 (Python 3.12): diagnostic_unclassified для трёх новых модулей,
5929 collected, no tests ran, exit 4. Это моя пропущенная регистрация тестов.

596eeb36 добавляет штатный reviewed shard tests/diagnostic_labels.output_integrity.json
с hash-bound регистрацией новых тестов. Старые labels/overrides/hashes неизменны.
Не добавлены skip/xfail и не изменены тестовые ожидания или алгоритм.
Подробности: v2plan/main-pr1/REVIEW_AMENDMENT_RU.md в ветке PR.

## Повторный CI: реальные проверки

CI: https://github.com/Vanilla1999/DocAtlas/actions/runs/37298795100
Release validation: https://github.com/Vanilla1999/DocAtlas/actions/runs/37298795091
P1.6: https://github.com/Vanilla1999/DocAtlas/actions/runs/37298794996

Все 42 добавленные проверки прошли в прочитанном core job Python 3.12:
5 empty-constructor + 25 terminal/SDK + 12 physical source-audit.
Общий core result: 1 failed, 5586 passed, 38 skipped, 304 deselected.
Dispatcher/SDK fixtures имеют явную producer seam; это не доказательство
прохождения retrieval guards для synthetic oversized source.

Успешны: lint, docs/CLI, installer, Windows/macOS platform smoke,
installed MCP harness, federated realism, retrieval ablation, release validation.
Установленный wheel/MCP/stdio проверялись штатными jobs. Это НЕ публикация релиза.
Core jobs Python 3.11/3.12/3.13 красные; advanced красный; required-ci skipped.
Точная подробная диагностика ниже относится к прочитанным Python 3.12,
advanced и P1.6 логам, а не к обещанию отсутствия иных проблем во всех средах.

## Содержательные failures совпали с прежним main

Проверены не только названия, но и observed/expected assertions в сохранённом
CI точного main SHA. Это исторический baseline-run, не новый paired запуск
на гарантированно одинаковых dependency versions.

### Core / P1.6

`tests/docs/test_agent_developer_adversarial.py::test_adversarial_protocol_fixtures_execute_against_current_contract[read_repo_globals_from_module]`

Observed ok; expected insufficient_evidence.

Baseline main P1.6:
https://github.com/Vanilla1999/DocAtlas/actions/runs/36904823195/job/110512607469
Current P1.6:
https://github.com/Vanilla1999/DocAtlas/actions/runs/37298794996/job/111726306692
Current core Python 3.12:
https://github.com/Vanilla1999/DocAtlas/actions/runs/37298795100/job/111726705544

### Advanced — те же четыре failures

Baseline main:
https://github.com/Vanilla1999/DocAtlas/actions/runs/36904823246/job/110512609283
Current PR:
https://github.com/Vanilla1999/DocAtlas/actions/runs/37298795100/job/111726705517

1. tests/docs/test_compositional_task_matrix.py::test_draft_store_without_regulated_context_needs_clarification
   observed answer_available=True; expected False.
2. tests/docs/test_compositional_task_matrix.py::test_module_request_without_selector_fails_closed_with_root_only_docs
   observed insufficient_evidence; expected failed.
3. tests/docs/test_unified_context_service_pipeline_surface.py::test_get_docs_context_requires_exactly_one_module_selector_when_module_scope_is_requested
   observed insufficient_evidence; expected failed.
4. tests/docs/test_unified_context_service_pipeline_surface.py::test_get_docs_context_conflicting_module_selectors_fail_closed
   observed insufficient_evidence; expected failed.

Baseline advanced: 4 failed, 300 passed, 38 skipped, 5545 deselected.
Current advanced: 4 failed, 300 passed, 38 skipped, 5587 deselected.
Все четыре несоответствия есть уже в baseline, включая selector/status случаи.
Это не новые regression findings empty-payload фикса.

Разрешённый вывод: в прочитанных выполненных suites не наблюдались новые
failing test IDs/assertions относительно сохранённого exact-main baseline.
НЕ разрешённый вывод: весь CI зелёный, все guards проверены, regressions невозможны.

После advanced pytest последующие recovery/mutation/project-context/lineage/
question/agent gates пропущены. Они NOT_RUN, не PASS. required-ci не выполнен.

## Конечная контрольная карта

- Этап 1: состав узкого PR-1 зафиксирован и полный main→PR allowlist проверен.
  Полный аудит всей research истории отдельно NOT_RUN; не претендовать на него.
- Этап 2: три изменения опубликованы; 42 новые проверки PASS.
- Этап 3: BLOCKED_BASELINE_CI_AND_REVIEW. Draft PR не слит.
- Внешние PR review submissions при проверке: 0. Авторское review не заменяет их.
- Этапы 4–8 / новый read-путь / reader pilot / N10: NOT_RUN здесь.
- Main migration: NOT_DONE; rollout/release: NOT_AUTHORIZED.

Следующая конкретная работа: отдельно разобрать и устранить существующие main
scope/answer/selector failures без изменения frozen expectations. Затем обновить
PR-1 на проверенную базу, исполнить ранее skipped обязательные gates, получить
отдельное review/одобрение и только после этого merge со smoke merge-SHA.
Не расширять этот PR новым admission/query fix ради зелёного CI. Отказ от gate
или waiver — отдельное явное решение владельца, не следствие старого failure.

Обсуждение с результатами и primary CI links:
https://github.com/Vanilla1999/DocAtlas/pull/206#issuecomment-5993140310

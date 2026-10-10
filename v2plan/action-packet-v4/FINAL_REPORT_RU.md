# ActionPacket v4 — реализация и проверка

Статус: реализация и bounded verification завершены. Независимый reviewer закрыл R1–R9; остаточных findings в проверенном срезе нет. Это не release acceptance.

## Контракт и расположение

- Worktree: `/tmp/opencode/action-packet-v4-integration`.
- Ветка: `implementation/action-packet-v4-integration`.
- Исходный SHA: `b89fa3cc16534445501bab14e0d63e099e9f61f6`.
- Интегрированный production/eval snapshot: `0f722677` (последующие commits отчётов не меняют реализацию).
- Новый результат: `data` с source-bound evidence либо компактный `failure`;
  полнота: `complete`, `partial`, `unavailable`. `edit_ready` всегда `false`.
- Полезное partial evidence сохраняется вместе с явными requirements,
  assignments и missing reasons. Пустые секции и legacy task scaffold не выдаются.
- Явный, отдельно одобренный пользователем MCP ingress:
  `get_docs_context(question=..., context_format="patch_context")`.
  При отсутствии параметра прежние docs-режимы не переключаются.
- Контракт, ownership и согласованные изменения interfaces: [CONTRACT.md](CONTRACT.md).

## Удалённые ограничения активного patch-пути

1. Builder/validator: 128/1500/2000 token floor/default/hard ceiling,
   schema maximum и аргументы `max_tokens`; budget fit/removal/failure compaction
   больше не участвуют в активной выдаче.
2. Selector: patch token target/hard/wrapper reserves и representation count
   limits заменены на `None`, не на большой sentinel. Нет cost-fit, length-based
   utility threshold или budget-triggered потери обязательных witnesses.
3. Explicit requirements/paths: patch-only slicing на 12 элементов отключён;
   точные literal values/provenance не объединяются через casefold.
4. Patch witnesses: сняты 1500-character / 64-unit и связанные run/group
   representation limits; большие и поздние witnesses остаются проверяемыми.
5. Projection/MCP: убраны повторное ограничение размера, optional shedding,
   превращение полезного partial результата в пустой refusal и clipping
   явных recovery targets. Scope сохраняется при revalidation.
6. Terminal MCP: внутренний default 32000-byte compactor не заменяет валидную
   v4 patch projection ошибкой; проверяются structuredContent и JSON fallback.

Legacy helpers, не используемые v4, не являются compatibility API; их физическое
наличие не означает активный ceiling. Не заявляется очистка всех исторических
вспомогательных функций или полная совместимость старых callers.

## Сохранённые технические guards

- Identity collisions, duplicate IDs, exact hash/window/span/assignment fidelity,
  freshness, version/lifecycle, explicit rejection, scope и proof-role admission.
- Исторические rejecting input bounds typed mutation/request-plan DTO сохранены;
  serializer не использует lossy path augmentation/parser и не режет DTO fields.
- Retrieval/runtime/finite-corpus guards не расширены. D1 corpus и `code_files=()`
  не менялись; тестовые in-memory fixtures не являются расширением runtime corpus.
- Docs-answer/docs-context budgets и default extraction остаются отдельной политикой.
- Исторические evaluator thresholds — только evaluation checks, не аргументы
  v4 producer budget. Их значения/gold/старые tests не мигрируются в этом срезе.
- Внешняя вместимость MCP/client/model не считается бесконечной и не проверена.

## Размер финальной выдачи

Измерение через реальный `call_docs_tool_payload`, advertised output schema,
`CallToolResult.structuredContent` и канонический JSON text fallback.
Bytes — UTF-8 финальной projection, без RPC envelope/transport marker.
Estimator — `ceil(bytes / 4)`, включая собственное поле `estimated_tokens`;
это **оценка**, не фактический tokenizer/provider usage.

| Пример | Bytes | Estimated tokens | Completeness | Validation | Requirements / sources |
|---|---:|---:|---|---|---|
| Empty failure | 205 | 52 | unavailable | PASS | 0 / 0 |
| Полезное partial evidence | 1665 | 417 | partial | PASS | 2 / 1; missing явно указан |
| Малый полный результат | 1369 | 343 | complete | PASS | 1 / 1 |
| Необходимые уникальные данные >2000 | 26171 | 6543 | complete | PASS | 18 / 18 |

Отдельный public regression сохраняет необходимую выдачу больше 32000 bytes.
Fixtures содержат самостоятельные protocol/config facts, не token padding.
Глобальный математический минимум размера не заявляется.

## Проверки

Использован существующий interpreter, source imports из worktree,
обычный `tests/conftest.py` и новые hash-bound diagnostic shards.
Ни conftest, ни старый diagnostic inventory не изменены.

```sh
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 DOCATLAS_AUTO_VECTORS=0 \
/home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python -m pytest -q \
  tests/test_action_packet_v4_contract.py \
  tests/test_action_packet_v4_selection.py \
  tests/test_action_packet_v4_public.py \
  tests/test_action_packet_v4_integrated.py \
  tests/test_action_packet_v4_eval.py \
  --basetemp=/tmp/opencode/action-packet-v4-final-r9-tests \
  -o cache_dir=/tmp/opencode/action-packet-v4-final-cache

PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 \
/home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python \
  v2plan/action-packet-v4/VERIFY_EXAMPLES.py

python3 v2plan/action-packet-v4/VERIFY_SCOPE.py
git diff --check b89fa3cc16534445501bab14e0d63e099e9f61f6
```

Финальный совместный run production snapshot `0f722677`: **195 PASS**, exit 0.
Examples / ownership / syntax / diff checks: PASS; все 44 изменённых source/eval
модуля успешно импортированы; инструкция проверена реальным dispatch тестом.
Ownership до добавления финального closure report: 61 changed paths, 2566
unchanged baseline paths; syntax: 51 source/new-test modules. Каждый из
перечисленных checks завершился exit 0. Reviewer независимо повторил все пять
новых suites: **195 PASS**, exit 0, и examples/scope checks: PASS.

## Независимый review

- Первоначальный независимый review: [REVIEW_R.md](REVIEW_R.md).
  Нашёл R1–R6, несмотря на 106 зелёных новых tests.
- Координатор отдельно воспроизвёл R7 (casefold потеря requirements) и
  R8 (одинаковый ev ID разных indexed windows); новые regressions сначала FAIL.
- [REVIEW_R_CLOSURE.md](REVIEW_R_CLOSURE.md): независимые воспроизведения
  подтвердили закрытие R1–R8.
- [REVIEW_R_FINAL.md](REVIEW_R_FINAL.md): provider composer сохраняет полный
  ~55.9 KB patch message на восьми последующих requests; выявлен Medium R9
  в активной required-once инструкции. Исправление интегрировано; regression
  исполняет actual instruction injection и public dispatch, ровно один retrieval,
  `retrieval_succeeded=True`, `edit_ready=False`.
- [REVIEW_R_FINAL_CLOSURE.md](REVIEW_R_FINAL_CLOSURE.md): **R1–R9 CLOSED**,
  no residual findings в bounded review. Reviewer независимо исполнил actual
  injection → public dispatch → observer: ровно один retrieval, 12 sources,
  55910 bytes / 13978 estimated tokens, полный валидный v4 result,
  `edit_ready=false`. Все остальные conditions/threshold bytes сохранены.

## Границы и ограничения

- Основная пользовательская ветка не изменяется; нет push/PR merge.
- Нет network/provider calls, reinstall, index rebuild или runtime scan expansion.
- NEXT06/NEXT07 WIP, исторические removal reports, старые tests/gold и
  посторонние `v2plan/artifacts/` не изменяются.
- Installed wheels/packs/deployed SDK/current-index parity, full-product quality,
  historical evaluation acceptance и release/security certification — UNKNOWN.
- Локальных implementation/review blockers в проверенном срезе не осталось.
  Исторические workflow conditions, требующие недоступных в v4 normative grants,
  остаются явно unsupported/fail-closed, не превращаются в разрешение действия.
- Реализация находится в отдельном integration worktree; пользовательская
  ветка остаётся `b89fa3cc`, status — только прежние untracked artifacts.

## Изменённые source / eval / новые tests

```text
docmancer/docs/application/_action_packet_part01.py
docmancer/docs/application/_action_packet_part03.py
docmancer/docs/application/_action_packet_part04.py
docmancer/docs/application/_action_packet_shared.py
docmancer/docs/application/_evidence_selection_part01.py
docmancer/docs/application/_evidence_selection_part02.py
docmancer/docs/application/_evidence_selection_part03.py
docmancer/docs/application/_evidence_selection_shared.py
docmancer/docs/application/action_packet.py
docmancer/docs/application/evidence_candidates.py
docmancer/docs/application/evidence_models.py
docmancer/docs/application/evidence_requirements.py
docmancer/docs/application/model_visible_projection.py
docmancer/docs/domain/_answer_units_part01.py
docmancer/docs/domain/_answer_units_part02.py
docmancer/docs/domain/_answer_units_shared.py
docmancer/docs/interfaces/mcp/context_tools.py
docmancer/docs/interfaces/mcp/output_contract.py
docmancer/mcp/_docs_server_part01.py
docmancer/mcp/_docs_server_schema.py
docmancer/mcp/_docs_server_tool_data.py
eval/answer_quality_gate.py
eval/answer_quality_runner.py
eval/evidence_selection_quality.py
eval/task_level/_execution_part01.py
eval/task_level/_execution_part02.py
eval/task_level/_execution_part03.py
eval/task_level/_execution_part04.py
eval/task_level/_execution_shared.py
eval/task_level/_github_models_part01.py
eval/task_level/_github_models_part02.py
eval/task_level/_github_models_shared.py
eval/task_level/_isolated_delivery_part02.py
eval/task_level/_isolated_delivery_shared.py
eval/task_level/_one_call_agent_loop_core.py
eval/task_level/conditions.py
eval/task_level/evaluators/actionability.py
eval/task_level/evaluators/docatlas_utilization.py
eval/task_level/evaluators/policy.py
eval/task_level/report.py
eval/task_level/runners/codex.py
eval/task_level/task33_codex_exploratory.py
eval/task_level/task33_pilot.py
eval/task_level/task33_validation.py
tests/diagnostic_labels.action_packet_v4_a.json
tests/diagnostic_labels.action_packet_v4_b.json
tests/diagnostic_labels.action_packet_v4_c.json
tests/diagnostic_labels.action_packet_v4_eval.json
tests/diagnostic_labels.action_packet_v4_integrated.json
tests/test_action_packet_v4_contract.py
tests/test_action_packet_v4_eval.py
tests/test_action_packet_v4_integrated.py
tests/test_action_packet_v4_public.py
tests/test_action_packet_v4_selection.py
```

Новые coordination / verification / review документы находятся только в
`v2plan/action-packet-v4/`: `CONTRACT.md`, этот отчёт, `REVIEW_R.md`,
`REVIEW_R_CLOSURE.md`, `REVIEW_R_FINAL.md`, `REVIEW_R_FINAL_CLOSURE.md`,
`VERIFY_EXAMPLES.py`, `VERIFY_SCOPE.py`.
Точный список всего diff: `git diff --name-only b89fa3cc16534445501bab14e0d63e099e9f61f6`.

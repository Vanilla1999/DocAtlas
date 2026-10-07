# ActionPacket v4 — реализация и проверка

Статус: финальная миграция косвенных eval consumers и независимая проверка ещё выполняются. Это не release acceptance.

## Контракт и расположение

- Worktree: `/tmp/opencode/action-packet-v4-integration`.
- Ветка: `implementation/action-packet-v4-integration`.
- Исходный SHA: `b89fa3cc16534445501bab14e0d63e099e9f61f6`.
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
  --basetemp=/tmp/opencode/action-packet-v4-final-tests \
  -o cache_dir=/tmp/opencode/action-packet-v4-final-cache

PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 \
/home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python \
  v2plan/action-packet-v4/VERIFY_EXAMPLES.py

python3 v2plan/action-packet-v4/VERIFY_SCOPE.py
git diff --check b89fa3cc16534445501bab14e0d63e099e9f61f6
```

Последний совместный промежуточный run при HEAD `d84ff297`: **184 PASS**, exit 0.
Examples / ownership / syntax / diff checks: PASS. Финальный run и reviewer closure
будут зафиксированы после последней интеграции.

## Независимый review

- Первоначальный независимый review: [REVIEW_R.md](REVIEW_R.md).
  Нашёл R1–R6, несмотря на 106 зелёных новых tests.
- Координатор отдельно воспроизвёл R7 (casefold потеря requirements) и
  R8 (одинаковый ev ID разных indexed windows); новые regressions сначала FAIL.
- Исправления владельцев интегрированы; закрытие findings зависит от повторной
  независимой проверки, а не worker handoffs. Проверка выполняется.

## Границы и ограничения

- Основная пользовательская ветка не изменяется; нет push/PR merge.
- Нет network/provider calls, reinstall, index rebuild или runtime scan expansion.
- NEXT06/NEXT07 WIP, исторические removal reports, старые tests/gold и
  посторонние `v2plan/artifacts/` не изменяются.
- Installed wheels/packs/deployed SDK/current-index parity, full-product quality,
  historical evaluation acceptance и release/security certification — UNKNOWN.
- Изменённые файлы и финальный интегрированный SHA будут добавлены после closure.

# 05. Исправить блокеры и завершить приёмку

Статус: BLOCKED; два локальных исправления выполнены, приёмка не завершена.
Основание — результаты и анализ плана 04.
Prod не восстанавливаем. Выкладка не входит в этот этап.

## 1. Сократить public instructions

**Править:** `docmancer/mcp/_docs_server_tool_data.py`, `_docs_server_shared.py`
в том же каталоге.
Полное правило сохранить в existing quickstart; tool/schema описать кратко,
убрав повторы между ними. Не переносить все правила в непрочитанный ресурс.
Сохранить missing-part lookup, исходный вопрос и условия, sourced known facts,
stop без прогресса и разделение context / proof / edit permission.

**DONE:** tools/list ≤ 6144 bytes; footprint и workflow/schema tests проходят.
Лимит не повышен, правила не потеряны.

## 2. Исправить implicit intent routing

**Править:** `docmancer/docs/interfaces/mcp/context_intents.py`.
Project-only defaults добавлять только для project route, не для explicit
dependency/mixed/library. Согласовать условие с existing service routing.
Явные intents не удалять молча; invalid combinations отклонять на входе.
Сначала regression test на `project_path + mode="dependency"` без intents.

**DONE:** project/auto/dependency/mixed/library и explicit-intent controls
проходят; existing agent-developer и adversarial gates зелёные.
Project defaults и source/permission guards сохранены.

## 3. Проверить восемь ответов агента

**Использовать:** `eval/task_level/runners/opencode.py` и вопросы
`artifacts/next04/AGENT_QUESTIONS_RU.md`. Сначала проверить совместимость runner
и candidate MCP; при необходимости минимально адаптировать existing runner.
Не создавать benchmark engine. Использовать полные raw events, не обрезанные
normalized summaries; изолировать sessions и соблюдать existing call limits.
Агент сам выбирает lookup, без evaluator expectations в prompt.

**DONE:** сохранены model ID, инструкции, calls, packets и 8/8 корректных
ответов с поддержанными citations, честным unknown и остановкой без прогресса.
Ошибочные вопросы не заменены удобными. Нет доступа/совместимости — BLOCKED.

## 4. Разобрать красные проверки и перепроверить кандидат

Для каждого remaining failure определить: runtime bug, устаревшее expectation,
research prototype или environment. Устаревшую предпосылку заменить проверкой
того же публичного поведения; corpus witnesses сверять с действующим текстом,
не обновлять hashes/labels ради green. Реальные дефекты вынести отдельно.
Не возвращать aliases, compiler или fallback ради старых tests.

Повторить relevant tests, required release checks, 80 native cases и четыре
lookup controls после правок. Проверять каждый прежний claim, не только сумму.

**DONE:** все прежние 49 claims сохранены, controls проходят, required checks
зелёные. Остальные failures классифицированы с основаниями и дальнейшим действием;
research/environment failures не выданы за PASS. Новые facts посчитаны отдельно.
Нерешённый обязательный check остаётся блокером.

## Завершение

- **READY:** все четыре этапа DONE; результат записан здесь, кандидат определён.
- **REJECTED:** подтверждён неверный ответ, потеря обязательного факта или guard.
- **BLOCKED:** любой этап не выполнен либо required check красный.

Правки 1 и 2 выполнять раздельно. Admission/selection/budgets/thresholds не менять.
Итог: изменённые файлы, команды, counts, артефакты и одно решение.
Готовность на этом наборе не означает доказанного превосходства над prod.

## Результат

### Выполнено

План отдельно закоммичен: `366dfa8d`. Проверенный кандидат — этот commit плюс
runtime/test patch текущего этапа, не чистый commit. Admission/selection и
численные budgets/thresholds не менялись. Заменена дублирующая длинная инструкция
компактным публичным правилом; полное объяснение сохранено в quickstart.
Для routing заменено ошибочное определение project-only, не добавлен fallback.

1. **Инструкция — DONE:** tools/list **6143 ≤ 6144 bytes** (было 7136).
   Изменены `docmancer/mcp/_docs_server_tool_data.py`, `_docs_server_shared.py`,
   `_docs_server_resources.py`. Проверки буквального текста обновлены на новые
   формулировки тех же правил, без удаления проверок поведения.
2. **Routing — исправлен, этап не DONE:** project-only defaults ограничены
   auto/project route без library. Explicit project intents для других routes
   отклоняются на входе. Regression controls: **9 FAIL до → 15 PASS после**.
   `v2plan/test_next05_context_intent_routes.py` запускается отдельно: diagnostic
   inventory tests/ заморожен, labels/hashes этого inventory не менялись.
   Agent-developer: **11/11 PASS**, false-supported/contamination=0.
   Adversarial: **27/28**, module-scope case остаётся красным (ниже).
3. **Ответы — BLOCKED, 0/8:** existing OpenCodeRunner реально запущен с
   compatibility prompt, без вопросов/expectations и candidate corpus.
   CLI отклонил `--pure` и `--dir` (exit 1), модель не запускалась.
   Установленный CLI предлагает `--standalone`; простая замена флагов ещё не
   доказывает изоляцию MCP, permissions и sessions. Без проверенного контракта
   такой адаптации этот этап не объявлен выполненным. Новый engine не создан.
4. **Перепроверка — частично:** native replay **80/80 идентичных packets**,
   **49 прежних claims сохранены**, lost=[], flags unchanged; четыре lookup
   controls пройдены. Focused tests **159 PASS**; docs/instruction tests
   **116 PASS**, дополнительные scope/recovery/instruction checks **68 PASS**.
   Исправлено устаревшее schema expectation: существующие intent fields
   учитываются, их enum проверяется. Полный final offline suite:
   **6084 PASS, 128 FAIL, 10 SKIP**, collection errors=0; новых failing nodes
   относительно сохранённого next04 нет. Required checks ещё не зелёные.

Recovery contract/mutation gates и stdio smoke — PASS; wheel/sdist собраны,
release metadata gate — PASS. Это не разрешение выпуска.

### Осталось; что не править вслепую

- Adversarial `module_scope_rejects_project_policy_detail`: ответ status=ok
  вместо insufficient_evidence, projection 380>300 tokens. Это три нарушения
  одной задачи. Нет установленного общего исправления внутри текущих двух
  локальных правок; не повышать бюджет и не ослаблять scope/admission ради case.
- Question-surface gate: четыре прежних owner/unresolved mismatches.
  Не возвращать legacy aliases/compiler только для его expectations.
- 128 failures: 90 semantic/contract требуют индивидуального разбора,
  11 corpus/witness drift, 11 hint prerequisites, 6 opt-in API stub,
  2 research prototype, 8 environment isolation. Это классификация симптомов,
  не разрешение исключить failures. Подробные nodes/messages сохранены.
- Нужна проверенная V2-адаптация existing runner с candidate-only MCP и
  полными events; затем восемь ответов и оценка citations. Manual controls
  и успешный replay не заменяют этот этап.

**Решение: BLOCKED.** Локальные footprint/routing дефекты устранены; общая
приёмка и индивидуальный разбор failures не завершены. Выпуск не выполнялся.

### Уточнение: что означают 128 failures

Это **128 failing test nodes, не 128 независимых runtime bugs**. Pytest errors=0,
сбор тестов успешен. Parameterized tests размножают одну причину: inventory
проверяется для трёх subjects и двух списков, namespace — в восьми сценариях.
С next04 ушли три nodes: footprint, intent-routing crash и schema expectation.
Новых failing nodes в final run нет; это не доказательство отсутствия регрессий
в непроверенных сценариях.

В прежней группе «90 semantic/contract» смешаны разные вещи:

- **Отсутствующая старая planner-механика.** 9 component-completeness и
  8 component-coverage failures завязаны на `_component_contract`/rewrites.
  Текущий `documentation_query_plan.py:108-147` не переносит proof requirements
  в retrieval, возвращает original/explicit host lookup/exact anchors,
  `semantic_scope_unverified` и пустой component contract. Из того же механизма
  идут failures need probes, aliases, audited rewrites и hint lineage.
  Пустые IDs/StopIteration сами по себе не доказывают потерю публичного факта.
  Старую систему не восстанавливать для прохождения таких assertions.
- **Потери публичного содержания.** Повторно воспроизведены оба LeaseClient
  timeout случая и RelayClient retention. Вместо timeout/exception приходит
  keyword overview; в RelayClient доходит retry count, но timeout отсутствует.
  Это реальные delivery defects при данных fixtures, не просто устаревшие IDs.
  Стадия потери (retrieval/admission/selection) ещё не локализована; нельзя
  автоматически назначить виновником только selector или уменьшить threshold.
- **Шумовой context proposal.** Precedence echo без указания победителя
  допускается `preferred_context_variants`. Повторный test подтверждает это
  для одного из четырёх тел. Assertion проверяет внутренний proposal, не
  supported final answer; пока нельзя заявлять ложный proof или security bypass.
- **Изменённый intent contract.** Clean-sync test получает docs_context вместо
  patch_context на слове "Fix", но helper уже проверил edit_ready!=true.
  Request не содержит explicit request_intent. Текущий read default не обязан
  выводить mutation из естественного языка. Это контрактное расхождение,
  не свидетельство выдачи лишнего разрешения редактировать.
- **Остальные delivery/coverage/ranking cases** требуют разбора по final bytes.
  Например, выбор другого project-doc не означает foreign-source contamination;
  retrieval coverage=full не является доказательством полного ответа.

Группы вне этих 90: 11 corpus/witness drift (часть не доходит до runtime),
11 missing-hint prerequisites (StopIteration до проверяемой projection),
6 opt-in `decide_read_window` stub (`unknown/not_implemented`, не основной
production read path), 2 roadmap prototype defects, 8 namespace environment
failures (`uid_map: Operation not permitted`). Все остаются FAIL в отчёте.

Отдельные gates не нужно прибавлять к 128 как независимые bugs:
adversarial — одна задача с тремя violations; question-surface — четыре
legacy owner/unresolved ожидания, не четыре сохранённых неверных ответа агента.
У adversarial не зарегистрирована forbidden-source contamination в выводе,
поэтому факт scope leak этим логом не установлен. Его budget/status mismatch
нельзя устранить простым повышением лимита/сменой labels.

Порядок устранения: сначала локализовать потери timeout/exception и проверить
adversarial final packet; отдельно заменить старые planner assertions проверками
публичного поведения с теми же guards; затем согласовать frozen corpus и
перезапустить isolation tests в подходящей среде. Восемь model answers —
отдельная незакрытая проверка, не pytest failure.

Анализ не менял runtime, expectations, labels или budgets. Повторный набор
представительных тестов: 5 FAIL / 3 PASS, XML
`/tmp/opencode/next05/analysis-representatives.xml`.

### Артефакты и повторение

Raw logs/XML/packets: `/tmp/opencode/next05/`. Основные файлы:
`footprint.json`, `native/`, `lookup/summary.json`, `gates.json`,
`final-tests-summary.json`, `final-tests.xml`, `runner-compat/result.json`,
`runner-compat/output/`, `release-manifest.json`. Первый полный прогон
`tests.xml` был до окончательной синхронизации текстовых expectations;
итоговым считается только `final-tests.xml`.

Все команды — с `DOCATLAS_OFFLINE=1`, проектным `.venv/bin/python`:

```bash
.venv/bin/pytest -q --confcutdir=v2plan v2plan/test_next05_context_intent_routes.py
PYTHONPATH=. .venv/bin/python v2plan/read_guard_pipeline_replay.py --baseline fed1898e --output /tmp/opencode/next05/native
PYTHONPATH=. .venv/bin/python v2plan/lookup_gap_probe.py --output /tmp/opencode/next05/lookup
.venv/bin/pytest tests/ -m 'not live and not live_network' -q --junitxml=/tmp/opencode/next05/final-tests.xml
.venv/bin/python scripts/run_agent_developer_gate.py
.venv/bin/python scripts/run_agent_developer_adversarial_gate.py
.venv/bin/python scripts/run_recovery_contract_gate.py
.venv/bin/python scripts/run_recovery_mutation_gate.py
.venv/bin/python scripts/run_question_surface_gate.py
.venv/bin/python scripts/docs_mcp_stdio_smoke.py
.venv/bin/python -m build --no-isolation --outdir /tmp/opencode/next05/dist
.venv/bin/python scripts/release_gate.py --dist /tmp/opencode/next05/dist --manifest /tmp/opencode/next05/release-manifest.json
```

# Точка продолжения перед compaction: PR211 и сокращение тестов

Дата: 2026-10-10. Это handoff текущей сессии, не новый runtime checkpoint PR.

## 1. Запрос владельца и выполненная работа

Владелец попросил:
1. Разобрать [Countdown-Code, arXiv:2603.07084v3](https://arxiv.org/html/2603.07084v3).
2. Записать правила не создавать массу unit-тестов: новые проверки только
   интеграционные и выше, желательно production-путь и реальные вопросы.
3. Предусмотреть включение/выключение подробных логов.
4. Сделать жёсткий анализ сокращения примерно40% тестов, начиная с красных,
   и подготовить правильный мультиагентный промпт.
5. Собрать этот контекст перед compaction.

Анализ и промпт написаны, правила добавлены в корневой AGENTS.md.
**В этой сессии тесты не удалялись, production/CI код не менялся,
переключатель логов не реализован, subagents не запускались.**
Новых commits/push не было. Последний запрос — handoff; запуск полной
реализации нельзя выдавать за уже начатую или завершённую работу.

## 2. Где лежит работа — важно сохранить

- Текущий worktree: `/tmp/opencode/pr211-test-strategy`.
- Текущая ветка: `analysis/pr211-test-strategy`.
- HEAD: `c518359fbf09f3a7c7457d686682bf3e12eecfae`.
- Worktree создан от этого SHA; OpenCode session перенесена в него.
- Основной checkout `/home/viadmin/StudioProjects/hermes/docmancer` старый,
  содержит пользовательские untracked файлы. Не reset/clean/overwrite.
- Fetch в начале этой работы подтвердил обе remote-ветки на `c518359f`:
  `integration/stage3-v2-identity-pr1` и `implementation/pr211-merge-readiness`.
  Повторной проверки remote после этого не было.
- Итоговый PR target: [PR #211](https://github.com/Vanilla1999/DocAtlas/pull/211),
  ветка `integration/stage3-v2-identity-pr1`.

**Незакоммиченные изменения текущей сессии:**
- новый `AGENTS.md`;
- новый `v2plan/TEST_STRATEGY_INTEGRATION_FIRST_RU.md`;
- новый `v2plan/TEST_REDUCTION_40_ANALYSIS_RU.md`;
- новый `v2plan/TEST_REDUCTION_40_MULTIAGENT_PROMPT_RU.md`;
- этот новый `v2plan/TEST_REDUCTION_40_HANDOFF_RU.md`;
- изменён `v2plan/PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md` — только добавлено
  уточнение новых правил со ссылкой на стратегию.

Они ещё не находятся в PR или remote. Перед сменой worktree/передачей агентам
сохранить именно эти файлы и переносить их явно. Не брать чужие untracked файлы
из старого checkout. Исторические `/tmp/opencode/docatlas-next-...` worktrees
уже отмечались prunable; не рассчитывать на старые временные отчёты там.

## 3. Порядок чтения

1. [Правила агента](../AGENTS.md).
2. [Жёсткий анализ −40%](TEST_REDUCTION_40_ANALYSIS_RU.md).
3. [Готовый мультиагентный промпт](TEST_REDUCTION_40_MULTIAGENT_PROMPT_RU.md).
4. [Статья, целевая структура и контракт логов](TEST_STRATEGY_INTEGRATION_FIRST_RU.md).
5. [Checkpoint PR211](PR211_CHECKPOINT_RU.md).
6. [Действующие продуктовые решения](CURRENT_WAVE_DECISIONS_RU.md).
7. [Предыдущий acceptance/retirement план с новым уточнением](PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md).

## 4. Что выяснено и насколько это проверено

### Статья

Главное — proxy success может расходиться с выполнением исходной задачи.
В эксперименте проверяющий код и постановка могли изменяться моделью,
а независимая проверка исходной задачи выявляла ложный успех. Статья не
сравнивает unit и integration и не задаёт40%: это решение владельца.
Логи и status=success также не заменяют независимую проверку конечных фактов.

### Числа набора

Источник — сохранённый **CI136 на `a9fba17d`**, не новый CI `c518359f`:
- Core одной Python lane: **7669 = 6052 PASS + 1607 FAIL + 10 SKIP**.
- Для этого core −40% = минимум**3068 net removals**, остаток максимум**4601**.
- Все красные —20,96%; даже удаление всех1607 оставляет gap1461.
-216 уникальных JUNIT_MODULE записей содержат1607FAIL и2098PASS: всего3705cases
  в красных модулях. Вне карты —3954PASS и10SKIP.
- Суммы и уникальность216 записей перепроверены через jq, без импорта проекта.
- Текстовый поиск в текущем `tests/**/*.py`:4910test-definitions в513файлах.
  Definitions не равны collected cases; возможны reexports/params/loops.
- В красной карте области A–D из анализа содержат1862cases. Даже их полное
  удаление не достигает цели и потеряло бы важные guards.
- Нет готового одобренного списка3068удалений. Есть список кандидатов и
  concrete рекомендации; текущие approved runtime deletions этой сессии —0.

Для реализации N_before — актуальный **unique core+advanced roster** на
зафиксированном base. Standalone scenarios/calls/mutations считать отдельно.
Формула: `removed - added >= ceil(0.40 * N_before)`.
Нельзя засчитывать переносы, skips, смену marker/selector, переименование или
перенос тысяч cases в один цикл. Старые уже выполненные сокращения не считать снова.

### Доступ к CI

Попытка `gh pr view 211 --repo Vanilla1999/DocAtlas ...` вернула HTTP401.
Свежие jobs/JUnit не прочитаны. Не называть исторический CI136 текущим статусом.
Не менять credentials/permissions самостоятельно. При отсутствии доступа
можно продолжать static analysis, но runtime acceptance остаётся заблокирован.

### Что пользователь сообщил о `c518359f`

Со слов владельца, после предыдущих исправлений подтверждены P1.4, P1.6
(adversarial28/28, checker9/9), Agent Developer Protocol, Installed MCP,
схемы и статические контракты. Critical/recovery/Legacy/V2 оставались красными;
CI этого SHA ещё выполнялся на момент его проверки. Эти сведения новее
некоторых таблиц checkpoint, но в этой сессии независимо не перепроверены.

## 5. Задачи следующей реализации

### A. Зафиксировать базу и общий manifest
- Сохранить незакоммиченные документы, проверить actual PR head и свои worktrees.
- Получить актуальный full JUnit/collection через разрешённый CI, определить
  unique N_before core+advanced, раздельно gates и существующие product failures.
- Один общий family manifest: node IDs, status, свойство, класс решения,
  successor/отмена, evidence, removed/added, owner. Не новый документ на каждый тест.
- Классы: DELETE_OBSOLETE / DELETE_DUPLICATE / REPLACE_INTEGRATION /
  KEEP_PRODUCT_FAILURE / UNRESOLVED. Красный — приоритет, не разрешение удаления.

### B. Сокращать крупными семействами
- Завершить подготовленные46: QP26 + role19 + один старый default3/800 case,
  сохранив их существующие условия healthy successors/intended proofs.
- Затем auto-query/semantic matrices, FakeFacade/call-name/internal flag
  проверки, зелёные DTO/schema/historical snapshots и дубли между слоями.
- Не удалять реальные rename/delete, source isolation, source facts,
  continuation/read_next и authorization задачи из-за их красного цвета.
- Для действующего уникального свойства — интеграционная замена; для дубля —
  reuse existing scenario; для отменённого ожидания — ссылка на принятое решение.
- Удалять ненужные fixtures/imports/labels/selectors в том же scoped пакете.
- Не требовать отдельную замену и mutation на каждый дублирующий case.
- Дойти до обоснованных40%, не останавливаться на46. Если manifest не даёт
  цели — расширить аудит зелёных; неопределённость не компенсировать слепыми удалениями.

### C. Логи и один настоящий вопрос
- Использовать existing self-host/quality runner и private same-call observer.
- Настоящий OFF должен отключать подробный сбор, а не только экспорт логов.
- `DOCATLAS_TRACE=0|1` — лишь предложенное имя, сейчас такого общего
  переключателя не реализовано. Предложено чтение при старте, без hot reload.
- ON: этапы/reasons/source bindings + отдельный final payload, request/run ID,
  counts/omissions и стоимость. Не копировать credentials/user corpus в обычный log.
- Одна интеграционная OFF→ON→OFF проверка на эквивалентных snapshots:
  тот же результат/state/число calls, чистый protocol stdout, trace только приON.
- Разобрать исходный падающий Legacy/V2 вопрос: первый наблюдаемый этап потери
  факта, отдельный product fix, тот же вопрос после исправления.

### D. Дубли CI и окончательная проверка
- Core выполняется в CI и P1 на Python3.11/3.12/3.13. Reuse одного
  эквивалентного producer с проверкой tree/runtime/deps/roster/artifact/attempt.
- Экономия repeated executions не прибавляется к40% case removals.
- Reviewer независимо проверяет manifest/diff/сохранённые свойства.
- Целевые runs для изменённых пакетов; итоговый общий run на конечном SHA.
- Отчёт: удалено/добавлено/net/%, runtime calls/mutations/time, оставшиеся
  product failures, required CI и client checks. Не объявлять merge-ready по числу тестов.

## 6. Открытые задачи самого PR211

Из сообщения владельца и checkpoint, не считать выполненными новым анализом:
1. Разобрать финальный CI `c518359f`, устранить critical/recovery causes,
   сохранив source и authorization guards.
2. Включить подготовленное удаление двух остаточных800 ceilings в diagnostic
   scripts: точные patch/commit locations в этой сессии не установлены.
3. Довести Legacy/V2 до требований исходных вопросов и полных frozen facts.
4. Применить retirement46 с собственными условиями доказательства.
5. Закрыть required CI/downstream и необходимые client checks на конечном SHA.
   Реальные Claude Code/Codex/OpenCode sessions остаются NOT_RUN по имеющимся сведениям.

## 7. Существенные действующие ограничения

- Output-cost ceilings6144bytes/800tokens/3sources **отменены** поздними
  решениями. Не возвращать их из старого контекста этой сессии.
- Blanket deferral retrieval **снят**: original-only/paraphrase/long/partial
  работа входит в актуальный план. Не ссылаться на старое «после релиза» как запрет.
- Source/hash/span/scope/version/consent/access/authority и operational
  input/read/work/call/time bounds сохраняются.
- Frozen inputs/gold и quality floors не ослаблять ради PASS/−40%.
- Локальные runtime/import/AST/pytest/install ограничены checkpoint;
  пользоваться разрешёнными PR workflows. В этой сессии их не запускали.
- Нет новых providers/models/downloads, пользовательских index mutations
  или auth/permission workarounds.
- Предыдущая авторизация обычных fast-forward относится к существующему PR;
  текущая задача была анализом/handoff. Force-push/merge/release не разрешены.
- Модель будущих агентов не закреплена этим новым поручением. Не повторять
  старые неподтверждённые заявления о модели из ранней истории разговора.

## 8. Релевантные файлы реализации и evidence

### CI и inventory
- `.github/workflows/ci.yml` — core matrix171–194, advanced225, platform/installed smoke.
- `.github/workflows/p1-stack-exact-validation.yml` — повторный core25–43 и gates.
- `tests/conftest.py` — diagnostic labels, advanced classification, network boundaries.
- `tests/diagnostic_labels.py`, `tests/diagnostic_labels.json` — active inventory consumers.
- `v2plan/pr211-execution/RUNTIME_EVIDENCE_a9fba17d.json` — CI136,216module records.
- `v2plan/pr211-execution/BASELINE_FAILURES.summary.json` и `.json.gz` — более
  ранний baseline; не смешивать его1936FAIL/61ERROR с CI136.

### Retirement
- `eval/task_level/contract_history/question_plan_v4_retirement.json`.
- `eval/task_level/contract_history/documentation_query_plan_compiler_retirement.json`.
- `v2plan/pr211-execution/QUESTION_PLAN_V4_CONSUMER_AUDIT_130_134_RU.md` и `.json`.
- `v2plan/pr211-execution/COMPILER_RETIREMENT_58_RU.md` — уже выполненная история.
- `v2plan/pr211-execution/LITERAL_REDUCTION_EVIDENCE.json` — не засчитывать
  старое702→82 снова как экономию новой волны.
- `tests/docs/test_question_plan_v4.py`, `test_query_reference_roles.py`,
  `test_documentation_query_plan.py`, `test_query_planning_budget_regressions.py`.

### Production-path и диагностика
- `docmancer/docs/interfaces/mcp/context_tools.py:596–684` — callback export;
  ранний return без observer, separate final projection observation.
- `docmancer/docs/application/_docs_context_projection_core.py:85` — trace
  создаётся без проверки включения observer.
- `docmancer/docs/application/projection_decision_trace.py` —128events,
  explicit omissions и32item previews.
- `scripts/run_project_docs_self_host_gate.py:492–506` — callback подключается
  на время реального public call; in-process, не installed stdio proof.
- `v2plan/PR211_FINAL_PROJECTION_OBSERVATION_RU.md` — final payload против
  bounded previews;3ID не означают всего3public sources.
- `docmancer/docs/interfaces/mcp/error_contract.py:78–79` — существующий
  DOCATLAS_MCP_DEBUG_ERRORS касается ошибок, не общего query trace.

### Existing evaluators
- `eval/project_context_quality/`, `eval/project_context_quality_v2/`.
- `eval/agent_developer_v1/`, `eval/evidence_quality_v2/`, `eval/task_level/`.
- `scripts/run_project_context_quality_v2_gate.py`.
- `scripts/run_recovery_contract_gate.py`, `run_recovery_mutation_gate.py`,
  `run_critical_mutation_gate.py` (все в `scripts/`).
- `v2plan/pr211-execution/LEGACY_SOURCE_FACT_ACCEPTANCE_RU.md` —12/15full
  frozen facts, raw original coverage отдельно; не переносить lookup credit.

## 9. Схема делегирования из подготовленного промпта

Три исследователя без edits на фазе1:
A — отменённые semantics/планы/роли;
B — mock/service/routing/lifecycle;
C — зелёные schema/DTO/snapshot/delivery дубли.
Координатор фиксирует exact ownership, общий manifest, baseline, logging/CI
shared changes. Затем те же агенты реализуют непересекающиеся пакеты;
отдельный независимый reviewer проверяет результат. Не назначать агентам
квоту удалений и не разрешать nested agents. Ни один из них ещё не запущен.

## 10. Выполненные проверки этого анализа

- Прочитаны статья, current source samples, checkpoint и saved evidence.
- Проверены jq суммы/уникальность216module records: PASS.
- `git diff --check`: PASS перед handoff; это только проверка whitespace.
- Новых runtime/test/client результатов нет. Старые failures не исправлены
  и не скрыты. Следующий исполнитель начинает с сохранения этих документов
  и фиксации актуальной базы, а не с повторного написания анализа.

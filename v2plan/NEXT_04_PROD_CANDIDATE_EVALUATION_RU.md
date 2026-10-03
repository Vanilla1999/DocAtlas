# 04. Принять текущую версию для выпуска

Статус: BLOCKED. Проверка выполнена в доступной части; выпуск не принят.

## Цель

Проверить, достаточно ли хорошо работает текущая версия после упрощений,
и получить решение: READY / REJECTED / BLOCKED.
Prod не восстанавливаем и не используем как эталон качества.

Уже известно: принятое read/proof-разделение дало 49 → 49 supported claims.
49 → 45 — отклонённый эксперимент, в runtime его нет.
Без нового сравнения не заявляем прирост качества относительно prod.

## 1. Определить кандидат

- Записать проверяемый commit и включённые незакоммиченные изменения.
- Перечислить фактически удалённые обязанности и оставшихся владельцев.
  Проверить, что отклонённое удаление `no_new_direction` не попало в кандидат.

**DONE:** понятен состав кандидата и какие именно упрощения в нём приняты.

## 2. Проверить контекст и tests

- Прогнать текущий native pipeline на existing 80 frozen cases и четырёх
  lookup controls. Использовать существующие runner и labels.
- Проверять final source bytes по смыслу: все ранее подтверждённые 49 claims
  должны остаться подтверждёнными. Новые подтверждения посчитать отдельно.
  Смена формулировки при сохранении факта не считается потерей.
- Controls: both получает production fact; partial — owner без выдуманного
  числа; absent — без выдуманного значения; wrong — без чужого факта.
  Known fact сохраняется в этих fixtures; proof/edit flags не повышаются.
- Запустить relevant workflow/schema/guard tests и существующие обязательные
  release checks. Каждый failure объяснить; required checks должны пройти.
  Старые красные tests не скрывать исключением из команды.

**DONE:** сохранены packets и таблица supported/missing/needs_review;
все прежние 49 claims сохранены, четыре controls проходят, нет нарушений
source/security/version/scope/freshness/span/request и identity/applicability
guards. Required checks зелёные. Неясность по любому из 49 claims разобрана.

## 3. Проверить реального агента

До запуска выбрать 8 реальных вопросов и записать ожидаемые факты с источниками:
по 2 вопроса с полным ответом, составным ответом, частичным/отсутствующим ответом
и похожими сведениями для другого subject/environment/version.

- Один запуск текущего кандидата на вопрос, независимые sessions, одна модель.
- Агент сам формулирует lookup; ожидания и готовые lookup ему не передавать.
- Сохранить model ID, фактически полученные инструкции, tool calls и ответы
  с citations. Соблюдать действующие call/recovery limits.
- Успех вопроса: доступные ожидаемые факты отражены в ответе, ссылки их
  подтверждают, неизвестное названо неизвестным, чужие факты не приписаны,
  нет выдуманных утверждений и повторов одного запроса без прогресса.

**DONE:** 8/8 вопросов удовлетворяют этим условиям. Ошибки не заменять
более удобными вопросами. Нет доступа к модели — BLOCKED, не manual подмена.
Это ограниченная приёмка, не доказательство универсального качества.

## Завершение

- **READY:** все три этапа DONE. Текущая версия прошла заданную приёмку.
- **REJECTED:** подтверждена потеря обязательного факта, неверный ответ,
  нарушение guard или permission. Записать конкретный провал.
- **BLOCKED:** проверка не выполнена, результат не разобран или required
  checks не прошли. Записать конкретную причину.

Итог — короткий отчёт здесь: кандидат, принятые упрощения, число подтверждённых
claims, результат 8 ответов, tests, пути к артефактам и решение.
Отдельно ответить: что упростилось; какие новые факты подтверждены относительно
existing frozen результатов; что о качестве пока неизвестно.

В этом этапе проверяем, а не подгоняем runtime или labels. Обнаруженный дефект
исправляется отдельной задачей. READY завершает приёмку; выкладка — следующий шаг.

## Результат

### 1. Кандидат — DONE

Проверен `b8e807cc2b083cb09298d8a015a0ac886ce3fac7`. Runtime `docmancer/`
совпадает с commit, dirty runtime diff пуст. Незакоммиченные `lookup_gap_probe.py`
и его test использованы только для наблюдения existing lookup; планы, README,
ablation runner/artifacts не являются runtime кандидата. Их изменения не отменены.

Принятое упрощение: `152a4c7b` убрал зависимость original-read от
`qualify_evidence` и whitelist proof reasons. Read-решением владеет
`read_context_admission` с `prepare_source_probe`, source/request/span,
literal/subject, applicability и locality checks. Claim proof и permissions
остались отдельными. `b8e807cc` уточняет workflow, не удаляет runtime gates.
`no_new_direction` остаётся в `_docs_context_projection_core.py:579`.
Другие research proposals не объявляются принятыми упрощениями.

### 2. Контекст сохранён; tests блокируют DONE

- Native replay: **80 cases, 49 supported, 29 missing, 10 needs_review**.
  Все прежние 49 claim IDs сохранены, новых 0, потерь 0.
  80/80 packets идентичны research reference; negative packets 0,
  changed proof/edit/support/coverage flags 0. Audit final packets: нарушений 0.
- Использован existing `read_guard_pipeline_replay.py --baseline fed1898e`.
  Это reference read-function для сохранённых claims, не восстановление prod
  и не сравнение двух полных releases. Candidate arm выполняет текущий native
  pipeline без подмены runtime функции. Reference arm использует старую read-function.
- Lookup: 8 calls, четыре controls проходят final-bytes expectations;
  known сохраняется, both/partial доставляют production/owner, absent/wrong
  не добавляют отсутствующий/чужой факт. Proof/edit flags false во всех calls.
- Focused: **150 passed, 1 failed**. Failure: schema-test ожидает отсутствие
  существующих `request_intent` / `lifecycle_intent`.
- Docs-contract: **100 passed**. Stdio smoke: PASS, scripted, не agent answers.
- Offline core + advanced suite: **6081 passed, 131 failed, 10 skipped**,
  6222 collected, collection errors 0. Live/live_network не запускались,
  согласно offline CI границе; красные tests не исключались.
- Сравнение failing nodes с сохранённым research XML: все прежние 130 остаются,
  добавился `test_default_public_catalog_meets_task35_hard_and_target_budgets`.
  Это historical diagnostic comparison с другой командой/inventory, не prod parity.
  Полные assertion messages и список failures сохранены в `tests.log`,
  `tests.xml`, `tests-summary.json`; 130 failures не объявляются допустимыми.
- **Новый конкретный дефект плана 03:** tools/list **7136 bytes > 6144**.
  In-memory удаление только двух текстовых additions плана 03 даёт **6115 bytes**.
  Это text-footprint regression, не потеря source facts; runtime не исправлялся.
- Recovery contract/mutation gates: PASS. Question-surface gate: FAIL,
  4 mismatches (public-tools questions и MCP architecture).
  Agent-developer и adversarial gates: FAIL,
  `ValueError: explicit intent parameters require project-only context`.
- Wheel/sdist собраны; release metadata gate PASS, version `1.3.2`.
  Wheel содержит exact current instruction/schema/resource bytes.
  Сборка не означает разрешения выпуска.

### 3. Реальный агент — BLOCKED

Восемь вопросов и source-grounded expectations зафиксированы в
`artifacts/next04/AGENT_QUESTIONS_RU.md` до агентских запусков.
**Ответов получено 0; оценка 8/8 не выполнена.**

Existing `model_benchmark.action_schema()` допускает evidence actions/finish,
не lookup или cited final answer. Installed-MCP runner передаёт public schema,
но его `action_envelope_schema()` также оценивает tool_call/finish/reason,
не полноценный ответ с citations. Это не подходящая замена проверки ответа.
OPENAI_API_KEY отсутствует; OpenCode executable есть, поэтому полную
недоступность моделей не заявляем. Нужен existing совместимый answer runner
либо отдельно согласованная адаптация. Новый benchmark engine не создавался.

### Команды и артефакты

Все raw результаты: `/tmp/opencode/next04-b8e807cc/`.
Проверки выполнялись проектным `.venv/bin/python`, с `DOCATLAS_OFFLINE=1`.

```bash
PYTHONPATH=. .venv/bin/python v2plan/read_guard_pipeline_replay.py --baseline fed1898e --output /tmp/opencode/next04-b8e807cc/native
PYTHONPATH=. .venv/bin/python v2plan/lookup_gap_probe.py --output /tmp/opencode/next04-b8e807cc/lookup
.venv/bin/python -m pytest -q tests/docs/test_agent_question_planning_contract.py tests/docs/test_lookup_gap_probe.py tests/docs/test_unified_read_admission_probe.py tests/test_unified_docs_context_mcp.py tests/test_source_isolation_regression.py tests/test_release_gate.py --junitxml=/tmp/opencode/next04-b8e807cc/focused.xml
.venv/bin/python -m pytest -q tests/docs/test_user_facing_docs_branding.py tests/docs/test_documented_cli_contract.py tests/docs/test_mcp_docs_tools_registration.py tests/docs/test_tool_choice_eval.py tests/test_cli.py tests/test_support_surface_policy.py --junitxml=/tmp/opencode/next04-b8e807cc/docs-contract.xml
.venv/bin/python -m pytest tests/ -m 'not live and not live_network' -q --junitxml=/tmp/opencode/next04-b8e807cc/tests.xml
.venv/bin/python scripts/docs_mcp_stdio_smoke.py
.venv/bin/python scripts/run_recovery_contract_gate.py
.venv/bin/python scripts/run_recovery_mutation_gate.py
.venv/bin/python scripts/run_question_surface_gate.py
.venv/bin/python scripts/run_agent_developer_gate.py
.venv/bin/python scripts/run_agent_developer_adversarial_gate.py
.venv/bin/python -m build --no-isolation --outdir /tmp/opencode/next04-b8e807cc/dist
.venv/bin/python scripts/release_gate.py --dist /tmp/opencode/next04-b8e807cc/dist --manifest /tmp/opencode/next04-b8e807cc/release-manifest.json
```

Первый build остановился: не установлен `build`. В `.venv` установлены
`build` и `hatchling<1.27` через `uv pip install`; повторная сборка успешна.
Runtime, labels, thresholds и budgets не менялись.
Внешний каталог также содержит candidate provenance/runtime hashes, public
tool catalog, retained claim IDs, audit, failure delta и footprint attribution.
Краткие цифры сохранены в `artifacts/next04/summary.json`.

### Решение

**BLOCKED:** required checks красные, есть новый footprint regression;
восемь реальных ответов не проверены. Остальные CI/matrix/platform gates
не заявляются пройденными и не запускались после установления этих блокеров.

Что улучшилось: read отделён от proof без измеренной потери 49 claims.
Что не улучшилось по замеру: новых подтверждённых facts 0.
Что ухудшилось: public tool catalog превысил byte budget из-за текста плана 03.
Что неизвестно: качество конечных ответов агента и превосходство над prod.

Следующий шаг — отдельная правка компактности опубликованной инструкции
без потери workflow правил; разобрать красные required gates; согласовать
минимальную адаптацию answer runner и выполнить восемь вопросов. Не выкладывать
этот кандидат под видом прошедшего приёмку.

## Анализ блокеров после приёмки

### Что действительно нужно исправить

1. **Footprint — новая регрессия текста.** Каталог вырос с 6115 до 7136 bytes
   при target 6144; additions плана 03 добавили 1021 bytes. До target нужно
   убрать минимум 992 bytes. Полное правило оставить в existing quickstart;
   tool description и schema сделать компактными и согласованными, сохранив
   missing-part/stop rule в реально получаемом агентом тексте. Нельзя просто
   поднять byte budget или перенести всё в ресурс, который агент не прочитает.
2. **Dependency routing — конкретный runtime дефект, не admission.**
   `context_intents.py:22` считает любой project_path без library project-only,
   даже с `mode="dependency"`; строки 28–29 добавляют implicit current intent.
   Handler передаёт defaults в service, который в
   `_unified_context_service_part01.py:111-113` отклоняет их для dependency mode.
   Existing oracle вызывает именно такую форму через `_context_args()`.
   В диагностике заменены только implicit defaults для explicit dependency/mixed
   в памяти процесса; explicit intents не удалялись, runtime files не менялись.
   **11/11 задач existing Agent Developer Protocol завершились, baseline_ok и
   target_ok true, false_supported=0, contamination=0, errors=[]**.
   Это локализует crash, но не доказывает полноту будущей routing правки:
   нужны separate project/dependency/mixed и explicit-intent controls.

### Почему 131 failure не равен 131 дефекту production

Консервативная классификация по assertions и проверенным исходникам:

| Группа | Nodes | Установлено |
|---|---:|---|
| Новый footprint | 1 | Дефект плана 03 |
| User namespace environment | 8 | `unshare` не может записать uid_map; не разрешать небезопасный fallback |
| Opt-in API stub | 6 | `decide_read_window` возвращает not_implemented; production callers отсутствуют |
| Research Gate A candidate | 2 | Tests вызывают roadmap prototype, не production admission |
| Corpus/witness identity drift | 11 | Не совпадают frozen hashes либо цитаты отсутствуют в active docs |
| Missing hint fixture prerequisite | 11 | Tests падают до projection: ждут `query-hint-*`, planner их больше не генерирует |
| Schema expectation | 1 | Test не учитывает существующие explicit intent fields |
| Intent routing | 1 | Runtime crash выше; также блокирует два standalone gates |
| Остальные | 90 | Semantic/contract failures, общего решения пока нет |

Группы с устаревшими prerequisites не доказывают работоспособность feature.
`documentation_query_plan.py:108-147` намеренно оставляет original, host lookup,
exact anchors; не возвращать aliases/compiler лишь ради прежних expectations.
Corpus drift нужно разобрать с сохранением смысловых обязательств, не просто
перезаписать hashes. Устаревший proof-owner assertion question-surface gate
также не заменяет проверку final public bytes. Tests не удалять массово.

### Реальные ограничения context delivery остаются

Дополнительный native diagnostic на существующем LeaseClient fixture:
original отдаёт keyword overview без `17 seconds` и `LeaseExpired`;
два focused lookup доставляют exception, но **17 seconds всё ещё отсутствует**.
Это не новый regression от read/proof patch, но реальная неполнота текущей выдачи.

На MkDocs precedence-вопросе original выдаёт insufficient evidence. Нейтральный
lookup `MkDocs page title navigation configuration Markdown title precedence`
доставляет начало precedence rule, но обрезает sentence перед `within the page
itself`. Полный frozen witness не доставлен; семантическая достаточность требует
разбора (`needs_review`). Обрезка не доказывает автоматически ни потерю факта,
ни полноту evidence. `status=ok` и query coverage не означают полного ответа.

Первая exploratory MkDocs lookup формулировка содержала `overrides`, то есть
ожидаемую relation; она не используется для вывода о корректном missing-part
lookup. Повторный neutral probe описан выше. Это development diagnostics,
не новые holdout и не proof нарушения guards.

### Агентский этап: прежний blocker можно уточнить

Evidence planners действительно не генерируют нужные final answers. Но в repo
есть generic `eval/task_level/runners/opencode.py`: он сохраняет raw JSON events,
включая текст и tool calls. Поэтому «нужен новый benchmark engine» не следует
из исследования. Сначала проверить возможность переиспользовать этот runner
с изолированным candidate MCP, восемью вопросами и запретом сторонних tools.
Normalized trajectory обрезает текст/outputs до 500 chars — для оценки брать
полные raw events. Runner не обеспечивает hard turn limit; отдельно проверить
соблюдение действующих call limits. OpenCode V2 CLI/config docs прочитаны;
совместимость runner, credentials и реальный model run пока не проверены.

### Минимальный порядок действий

1. Отдельно сжать public instructions; verify byte budget + semantic workflow tests.
2. Отдельно исправить implicit intent routing; verify dependency/project/mixed
   controls и существующие agent-developer/adversarial gates.
3. Выполнить восемь реальных ответов через existing runner, не ручные lookup.
4. Разобрать остальные release-relevant failures: устаревшую реализационную
   предпосылку заменять публичной проверкой того же поведения; реальные потери
   фиксировать отдельными задачами. Research/env failures не маскировать green.

Вывод: архитектурное упрощение сохранено, но кандидат не стал доказанно лучше
по ответам. Admission массово ослаблять не требуется. Два локальных blocker
понятны; общий context recall и качество агента остаются незакрытыми.
Диагностические артефакты: `/tmp/opencode/next04-b8e807cc/analysis/`:
`failure-groups.json`, `routing-diagnostic-report.json`,
`routing-diagnostic-calls.json`, `delivery-02/`, `mkdocs-neutral/`.
Первый delivery diagnostic остановился на serialization frozenset; повторный
использует existing `save_json`, его результаты сохранены. Runtime не изменён.

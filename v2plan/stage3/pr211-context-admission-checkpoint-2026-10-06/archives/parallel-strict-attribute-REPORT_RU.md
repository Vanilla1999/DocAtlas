# PR211 — кандидат A: strict attribute на late fallback

Дата: 2026-10-06. Рабочая ветка `diagnostic/pr211-strict-attribute-20261006`.
Baseline: `37bfd0668f819935dd9e027bd9d8bf767fcd185a`.
Кандидат — **реальный незакоммиченный diff**, не отдельный SHA и не runtime-подмена.
Изменения и артефакты находятся только в `/tmp/opencode/pr211-parallel-strict-attribute`.
Primary tree и другие worktrees не изменялись; commits/push/merge не выполнялись.

## Изменение и причина

В `docmancer/docs/application/_docs_context_projection_core.py` late fallback
дополнительно требует `not strict_single_attribute`. Используется уже вычисленная
граница: complete scope, ровно одно attribute obligation, установленный value_kind.
Не добавлены parser/regex/словарь/weights. Hint recursion сохраняет исходный план и
вычисляет ту же границу. Нет глобального запрета partial context, изменений authority
или hint attribution. Размер окончательного product diff: **одно условие**, без
изменения числа строк уже заполненного до hard budget projector.

Причина: основной путь отвергает источник без требуемого attribute witness, а поздний
путь заново понимает тот же вопрос как unknown и возвращает topic-only context.
Правка не усиливает answer/edit authority: весь доставляемый docs_context остаётся
read-only. Baseline adversarial не доказывает scope leak: в нём выдан только README
orders, без ARCHITECTURE/payments, и flags false.

## Тесты и реальные payload

Добавлен `tests/docs/test_strict_attribute_late_fallback.py`: 13 параметризованных
проверок, отдельный hash-bound behavioral shard в
`tests/diagnostic_labels.strict_attribute_late_fallback.json`. Guard inventory не
ослаблен; существующие tests/gold/expectations/budgets/workflows не менялись.

- Три positive: число у нужного subject в plain prose, под heading и рядом с числом
  другого subject. Проверяется реально видимая цитата, source path/identity и flags.
- Три negative: delegation без числа, число у OtherWorker, разнесённые subject/topic.
  Проверяются отсутствие sources/context, insufficient_evidence и отсутствие самого
  вызова late fallback через observer, делегирующий неизменённой реализации.
- Unknown partial: incomplete parser, реально использованный context fallback,
  bounded queue доставлена, original остаётся missing, answer/edit flags false.
- Module scope: project policy не заимствуется; добавление локального числового факта
  сохраняет выдачу ровно `packages/orders/README.md` с нужным числом.
- Foreign identity, stale, unsafe и unsynchronized numeric candidates не выдаются;
  проверяются final projection/snapshot. Дополнительный healthy replay замороженного
  retrieval дал `ok` с `ProjectRetryPolicy allows at most two retry attempts.`:
  отрицательные проверки не основаны на сломанном replay.

`baseline-probes.json` / `candidate-probes.json`: positive 279 tokens неизменны;
OtherWorker/unrelated topic `ok` → `insufficient_evidence`, 244 tokens; unknown partial
остаётся `ok`, 277 tokens, исходная bounded-queue цитата сохраняется.
`paired-probes-comparison.json` подтверждает равенство **всего public payload**
для двух numeric positives и unknown partial после исключения только зависящих от
разных temporary roots `project_identity`/`source_uri`. Никакие flags, coverage IDs,
snippets, line ranges или token estimates при этом не игнорировались.

## Окружение и команды

Все запуски в собственном worktree, один Python:

```bash
export DOCATLAS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTHONPATH=/tmp/opencode/pr211-parallel-strict-attribute
PY=/home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python
$PY -m pytest tests/ -m 'not advanced and not live and not live_network' -q --junitxml=baseline-core.xml
$PY scripts/run_agent_developer_adversarial_gate.py --output baseline-adversarial.json
# После реального product patch:
$PY -m pytest tests/ -m 'not advanced and not live and not live_network' -q --junitxml=candidate-core-v3.xml
$PY scripts/run_agent_developer_adversarial_gate.py --output candidate-adversarial.json
$PY -m pytest tests/ -m advanced -q --junitxml=candidate-advanced.xml
$PY scripts/run_agent_developer_adversarial_mutation_gate.py
```

Парный адресный roster:

```bash
$PY -m pytest \
 tests/docs/test_strict_attribute_late_fallback.py \
 tests/docs/test_quantified_attribute_scope_isolation.py \
 tests/docs/test_context_completion_guards.py \
 tests/docs/test_context_projection_boundaries.py \
 tests/docs/test_joint_context_invariants.py \
 tests/docs/test_evidence_set_context_delivery.py \
 tests/docs/test_source_bound_subject_context.py \
 tests/docs/test_exact_document_fallback_context.py \
 tests/docs/test_context_capture_integrity.py \
 tests/test_diagnostic_labels.py -q --junitxml=candidate-targeted-v2.xml
```

Фактические stdout/stderr сохранены в одноимённых `.log`; baseline адресного roster —
`baseline-targeted-final.xml/.log`. Версии и hash product file: `environment.json`
(Python 3.13.12, pytest 9.0.3, FastEmbed 0.8.0, pydantic 2.13.4).

## Результаты

| Проверка | Baseline | Candidate |
|---|---|---|
| Исходный offline core | 5282 PASS / 17 FAIL / 10 SKIP, 622 deselected | Те же 5282/17/10 на исходном roster; **13 новых PASS** |
| Adversarial | 27/28 | **28/28**, errors=[] |
| Целевой module case | ok, 380 tokens, README без числа | insufficient_evidence, 244 tokens, sources=[] |
| Адресный roster 122 | 117 PASS / 5 FAIL | 121 PASS / 1 прежний FAIL |
| Advanced/security | Не запускался парно | **622 PASS**, 5322 deselected |
| Adversarial mutation | Не запускался парно | PASS; **9/9 mutants killed** |
| Финальные strict/line-budget/inventory guards | Парный strict+inventory: 15 PASS / 4 FAIL | strict+inventory **19 PASS**; расширенные guards **40 PASS** |
| Recovery contract / mutation | Не запускались парно | PASS / **6/6 mutants killed** |
| Critical mutation | Не запускался парно | **3/3 mutants killed** |

`candidate-final-adversarial.json/.log` повторно подтверждает 28/28 уже на финальном
однострочном patch. `candidate-final-guards.xml/.log` подтверждает сохранение module
line budgets и fail-closed inventory. Recovery и critical mutation логи имеют
префиксы `candidate-recovery-*`, `candidate-critical-mutation`.
Advanced/security и adversarial mutation также повторены на окончательном diff:
`candidate-final-advanced.xml/.log` (**622 PASS**) и
`candidate-final-adversarial-mutation.log` (**9/9 mutants killed**).

Дополнительный question-surface gate **FAIL на обоих вариантах**, 4 нарушения
ownership (cases 022/023/030/078). `baseline-question-surface.log` и
`candidate-question-surface.log` побайтно совпадают (`diff -u`: exit 0).
Это не новая регрессия и не исправление.

Финальный `candidate-core-v3`: **5295 PASS / 17 FAIL / 10 SKIP**, 622 deselected,
316.82 s; baseline-core: 357.70 s. Время не используется как performance claim.
`paired-core-comparison.json` (воспроизведение: `$PY summarize_checks.py`):
все baseline nodes сохранены; на исходном roster 0 новых/0 снятых failure IDs;
все 13 новых tests PASS. Утверждение «нет новых failure IDs» ограничено этим roster,
а не всем CI и не доказательством неизменности каждого проходящего сценария.

После завершения всех core процессов единственное product condition **временно
возвращено в точности к baseline**; `git diff --exit-code -- docmancer/` дал exit 0.
На настоящем unmodified product baseline повторены окончательный observer и
question-surface gate. Затем финальный однострочный patch восстановлен и observer
повторён: `baseline-final-observer.xml/.log` **15 PASS / 4 FAIL** →
`candidate-final-observer.xml/.log` **19 PASS**. Ожидания тестов и observer между
этими запусками не менялись. Три baseline FAIL измеряют реальные late calls,
четвёртый — прежний module case. SHA-256 восстановленного final product совпадает
с core-v3 и `environment.json`:
`6205d18bbb2e73d7d8ad2aa1213fa59cb26964b47b63c147d208f49dbd751a32`.

Команды точного парного observer:

```bash
$PY -m pytest tests/docs/test_strict_attribute_late_fallback.py tests/test_diagnostic_labels.py -q --junitxml=baseline-final-observer.xml
$PY scripts/run_question_surface_gate.py
# Восстановлено только собственное однострочное изменение:
$PY -m pytest tests/docs/test_strict_attribute_late_fallback.py tests/test_diagnostic_labels.py -q --junitxml=candidate-final-observer.xml
git diff --check
```

Адресный прежний отказ:
`test_context_projection_boundaries.py::test_frozen_request_flow_prefers_project_context_module_witnesses`.
Он не исправлен и не объявляется новым regression.

### Ошибки диагностических проверок не скрыты

Первый запуск нового модуля остановлен fail-closed inventory guard:
`diagnostic_unclassified`; добавлен отдельный reviewed-by-author behavioral shard
с hash набора test nodes, без изменения guard. `baseline-strict.log` позже заменён
успешно собранным запуском, поэтому первоначальная ошибка отдельно описана здесь.

Первая candidate версия новых negative tests ошибочно требовала пустого ключа
`need_context_fallback`: этот ключ пишут и **ранние** context proposals, не только
late call. Final public assertions уже проходили. Это ошибка тестового наблюдения,
не product regression. Заменена проверкой **самой late функции**, с сохранением
всех public negative assertions и добавлением strict rejection/final evidence IDs.
Старые `candidate-targeted-final.xml/.log` и `candidate-core.xml/.log` сохраняются
как диагностические результаты, не финальная приёмка. Новый `candidate-targeted-v2`
оставляет только прежний request-flow FAIL. Product logic между этими запусками не
менялась. Точный парный baseline окончательного observer выполнен отдельно,
как описано выше.

Первый полный candidate-core дал **5290 PASS / 22 FAIL / 10 SKIP**: 17 прежних,
3 ошибки моей diagnostic assertion и **2 настоящих нарушения hard line budget**
(`test_all_repository_python_modules_stay_within_hard_line_budget`,
`test_projection_owner_remains_within_repository_module_budget`). Два добавленных
поясняющих комментария подняли заполненный projector выше лимита. Убраны только эти
два добавленных комментария, финальный product patch однострочный. Guard tests,
module budgets, manifests и workflows не ослаблялись. `candidate-core-v2` начат до
этой чистки и также не является окончательной приёмкой: **5294 PASS / 18 FAIL /
10 SKIP**, один из line-budget guards ещё увидел старый файл с комментариями.
Финальный запуск — v3, файл product далее не менялся до завершения этого запуска.

В v2, v3 и final advanced есть `PendingDeprecationWarning` из
`starlette/formparsers.py`: `Please use import python_multipart instead`.
Зависимости и warnings policy не менялись; предупреждение не скрыто и не является
исправлением/регрессией strict boundary.

Дополнительный candidate-only boundary roster: `candidate-boundaries.xml/.log`,
**168 PASS** (context7-style chat, constraint roles, model-visible projection и
ranking regressions); это не парное сравнение.
Frozen boundary roster (`candidate-frozen-boundary.xml/.log`): **80 PASS / 7 FAIL**;
все 7 failure IDs уже присутствуют в исходном baseline-core (README-neutral
unknown/identical lookup, projection_clip и четыре tiny-budget public-query cases).
Их expectations не изменялись; они не объявляются исправленными.

## Ограничения, риски, вердикт

Возможен recall loss для существующей strict-границы, если исходный witness detector
не распознал реальное число. Positive plain/heading/mixed-subject/module controls
прошли, но это не доказательство для всех языков и форматов. Остальные исходные
core failures не исправлены: authority/hint и прочие независимые задачи вне A.

Это локальная diagnostic evidence на Python 3.13, **не полный CI**: нет matrix
3.11/3.12, installed-package, legacy lineage gate и независимого review. Candidate
advanced/mutation не имеют парного baseline и не засчитываются как сравнение.

**Acceptance verdict для задачи A:** принять как изолированный диагностически
подтверждённый кандидат исправления strict-attribute late-boundary. Реальный
минимальный patch сохраняет существующий guard, adversarial 27/28 → 28/28,
положительные numeric/unknown-partial контроли сохраняют доставку, core исходного
roster не получает новых failure IDs. Новые тесты и точный baseline observer
подтверждены; hard guards и бюджеты сохранены.
**Merge readiness отсутствует**. Для merge нужны обязательный CI, независимое review
и явное разрешение владельца.

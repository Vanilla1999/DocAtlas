# PR #211: baseline CI и недостающие acceptance evidence

Дата: 2026-10-08. Только factual read-only audit исходного PR и небольшое
добавление JUnit artifacts; это не новый запуск и не merge/release approval.

## База и источники

[PR #211](https://github.com/Vanilla1999/DocAtlas/pull/211):
HEAD `21fe472d983f394130849d6fd4e582043d58e9ba`, base main
`d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c`, open/draft, mergeable=true.
Read-only reviews/threads endpoints вернули пустые списки.

Результаты ниже получены из GitHub Actions job metadata и доступных logs:

- [CI run 37796983129](https://github.com/Vanilla1999/DocAtlas/actions/runs/37796983129).
- [Release validation run 37796983063](https://github.com/Vanilla1999/DocAtlas/actions/runs/37796983063).

Эти PR-triggered runs привязаны к указанному HEAD, но checkout/runtime evidence
использует GitHub merge SHA `cd8cbb86b43fdd7f83ccf3eda08ef34c26d9e340`.
Их нельзя переименовать в acceptance последующего локального commit.

## Подтверждённые исходы CI

| Job | Состояние последнего baseline snapshot |
| --- | --- |
| `test (3.11)`, `test (3.12)`, `test (3.13)` | completed / FAILURE; failing step — offline core pytest |
| `advanced-contract` | FAILURE: 109 failed, 513 passed, 8500 deselected |
| `docs-contract` | FAILURE |
| `platform-smoke` — Ubuntu, macOS ARM64, macOS Intel | FAILURE на CLI/contract step; installed stdio step skipped |
| `retrieval-evidence` | FAILURE на frozen retrieval gate |
| `installed-mcp-harness` | SUCCESS; один scripted task `module_definition_supported` и schema-repair verifier |
| `installer-smoke`, `static-contract` | SUCCESS |
| `docs-impact` | SUCCESS; не входит в required aggregator |
| `required-ci` | completed / FAILURE |

Core job IDs: 113378894673 / 113378894734 / 113378894721 соответственно
Python 3.11 / 3.12 / 3.13. Их полный test roster/counts этим audit не установлен:
координатор подтвердил отказ connector при logs сверх 8,388,608 bytes.
Job conclusion FAILURE подтверждён независимо через metadata; отсутствие полного
лога не является ни PASS, ни основанием считать все failures известными.

В advanced job 113378894588 pytest выполнился и завершился указанными counts.
Последующие recovery, legacy/V2 project-context, question-surface, agent-developer
и mutation gates были **skipped**. Upload quality reports дополнительно завершился
ошибкой, поскольку эти ещё не выполненные steps не создали reports. Это не второй
независимый продуктовый дефект.

### Группы 109 advanced failures

| Группа | Число failures |
| --- | ---: |
| `tests/task_level/*` | 32 |
| MCP patch constraints/plan-context tests | 19 |
| Patch symbol grounding | 5 |
| Patch constraint validation service | 12 |
| Patch constraints service | 32 |
| Patch constraints workflow | 4 |
| Patch review command | 5 |
| **Всего** | **109** |

Из 32 task-level failures девять непосредственно передают удалённый
`build_action_packet(max_tokens=...)`; пятнадцать one-call-loop tests используют
общий v3 fixture, который current v4 validator отвергает до дальнейших actions.
Остальные затрагивают старые packet fields и ожидания host evidence/policy.
Это диагностическая группировка по trace и source, не доказательство достаточности
одной fixture правки. Valid v4 retrieval сам по себе по текущему контракту не
разрешает edit; возвращать старую retrieval-to-edit authority ради PASS нельзя.

Patch suites вызывают direct handlers/services: default advanced-tool setting
не является общей причиной этих failures. Документированные изменения убрали
prose policy compilation, NL/alias symbol inference и guessed dependencies;
code evidence требует явного finite membership. См.
`stage3/pr211-context-admission-checkpoint-2026-10-06/SDK_PATCH_DICTIONARY_EXIT_RU.md`
и `LOCAL_MEMBERSHIP_CALLER_CLOSURE_RU.md`. Эти old contracts требуют отдельного
review, а не восстановления удалённых эвристик. В данном slice они не менялись.

### Frozen retrieval gate

Job 113378894670 завершился сообщением:

```text
within-budget full model-visible DTO exceeded the 800-token ceiling
```

Его summary: frozen 80 — within_budget 48, within_budget_sufficient 30,
operational_errors 0, integrity_violations 0; holdout current/strict 5/5,
improvement not observed. Gate находится в
`scripts/run_systemic_retrieval_plan_gate.py` и сохраняет `MAX_TOKENS=800`.

Снятие output representation cap не отменяет frozen acceptance. Gold, threshold,
evaluation criteria и required gate в этой завершающей волне **не изменены**.
Deferred original-only paraphrase, multi-section/long и partial admission остаются
deferred по `after-merge/RETRIEVAL_DEFERRED_ANALYSIS_RU.md`; это не waiver и не PASS.

## Required release validation

Build SUCCESS. Wheel 3.11/3.12/3.13 и sdist-and-installer FAILURE;
`required-release` FAILURE. Publish и последующие public-platform/registry jobs
skipped. Никакой публикации этот audit не запускал.

В доступном wheel 3.12 log job 113379126707 failing chain:

```text
scripts/docs_mcp_stdio_smoke.py:313
read_only_delivery -> get_docs_context(context_format="patch_context")
scripts/docs_mcp_stdio_smoke.py:219 -> json.loads(content[0].text)
JSONDecodeError: Expecting value
```

Исходный smoke запускает default server без `DOCATLAS_MCP_ADVANCED_TOOLS=1`,
а новый default schema отвергает context_format, включая null. Ошибка MCP
validation приходит текстом, который старый decoder считает JSON. Smoke также
содержит ещё не достигнутые old default-null/advanced matrix expectations.
Это отдельный harness migration; runtime исправление, весь installed matrix
и long/partial delivery этим diagnosis не подтверждены.

## Обязательный acceptance и remote protection

Committed `.github/rulesets/protect-main.json` и `scripts/main_ruleset.py`
требуют **required-ci + required-release**, strict checks и resolved threads.
`required-ci` зависит от docs-contract, installer-smoke, всех platform-smoke,
core matrix, advanced-contract со downstream gates, installed-mcp-harness,
static-contract и retrieval-evidence. Ничего из этого новым JUnit output не снято.

Удалённая конфигурация при read-only проверке: rulesets endpoint вернул `[]`;
branch main metadata — protected=false, required checks=[], enforcement=off.
Direct branch-protection read вернул 403 для integration. Это отличается от
committed желаемой политики. Защита не менялась; mergeable=true и отсутствие
remote enforcement не заменяют acceptance и не используются для обхода gates.

## Почему добавлен JUnit artifact

Известный checkpoint — 801 collected/executed, 791 PASS / 10 FAIL — относится к
tested code SHA `5310e6da83a09daa0938efa9cf68e2c0f7c99851`. Точный roster, CP-run.py,
CP-final-collect.log, FINAL-outcomes.json и CP-junit.xml в доступном checkout не
сохранены; checkpoint ссылается на прошлый `/tmp/opencode/docatlas-next-8e38eet1/`.
Его exact-roster equality невозможно восстановить из одних totals.

Изменение `.github/workflows/ci.yml` добавляет только `--junitxml` к существующим
двум pytest commands. Test paths, marker expressions, `-v`, matrix, dependencies,
timeouts и все downstream/gate команды сохранены. Дополнительных test runs нет.
XML пишется в runner.temp, затем `if: always()` загружает только этот файл через
уже используемый pinned `actions/upload-artifact` v4.6.2. Имена содержат Python,
run_id и run_attempt; retention 14 дней. Missing file даёт warning и не меняет
исходный failing/skipped test result. Нет continue-on-error/перехвата pytest exit.
Advanced upload помещён после существующих downstream steps, сохраняя их порядок.

Captured stdout/stderr не включены: остаётся штатный `junit_logging=no` default,
в repository pytest config нет его override; full logs/directories не загружаются.
XML содержит node names, outcomes, durations и failure diagnostics. Это поможет
проверить конкретные executed nodes и пять scope variants будущего run. Collection
error/aborted job всё равно не доказывает исполнения полного набора, а uploaded
XML сам по себе не превращает failing tests в PASS.

Изменение проверено static diff inspection и `git diff --check`; оно не исполнено
локально и не сертифицировано выполнением GitHub Actions на новом SHA. Root
review и будущий обычный PR CI run ещё требуются.

## Runtime/client prerequisites, оставшиеся открытыми

На момент локального audit нет готового разрешённого pytest/MCP/project runtime.
Dependency/model downloads и provider calls не выполнялись. Fixture runtime
должен иметь private app storage вне project, verified imports и pre-import
network/process guards, переданные actual server descendant; разрешены только
конкретные fixture Git commands и verified server argv/cwd/env.

Source in-process tests не заменяют source stdio; source stdio не заменяет
isolated installed wheel. Existing platform-proof.sh скачивает managed Python;
scripted installed benchmark устанавливает dependencies. Эти helpers нельзя
считать no-download только из-за scripted planner/offline environment flags.

Пять `test_public_scope_never_implicitly_widens` scenarios требуют отдельного
actual execution с сохранением positive foreign/root reachability controls.
Реальная видимость structured/text long/partial payload в Claude Code, Codex,
OpenCode и версии этих clients в текущей волне не проверены. Нужны доступные
разрешённые installations/versions; mock/SDK transport не сертифицирует приложения.
Без них отчёт остаётся **NOT RUN** с prerequisite, без download/permission обхода.

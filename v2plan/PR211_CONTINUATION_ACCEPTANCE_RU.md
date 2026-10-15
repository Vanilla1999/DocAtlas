# PR #211 — выполненный acceptance на f0ed956

Дата evidence: 2026-10-08. **MERGE READY = FALSE; полный acceptance не закрыт.**
Этот report относится только к HEAD `f0ed956ce2c2ba19dc536bbe0ad6dbebb8418fa4`,
tree `afb5b4ed95ba6955c3ed574439d921803d837d60`, PR merge `417a6544b1f859f7bdad5f40b9729255ec8c1ae2`.
Проверены реальные GitHub CI/JUnit/SDK evidence на этом SHA; новые follow-ups
`40032f7` требуют отдельного прогона. Их подготовка/публикация не меняет f0 outcomes.

## Полные pytest rosters и сравнение с df9

[Основной CI 37819292857](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292857),
attempt 1, завершён FAILURE. Все три core XML скачаны из actual artifacts,
ZIP size/SHA256 совпали с GitHub metadata. Longest existing module prefix
сохраняет class-qualified node IDs. Дубликатов и удалённых baseline nodes нет.

| Suite | Исполнено | PASS | FAIL | ERROR | SKIP |
|---|---:|---:|---:|---:|---:|
| Core Python 3.11 | 8507 | 6415 | 2021 | 61 | 10 |
| Core Python 3.12 | 8507 | 6415 | 2021 | 61 | 10 |
| Core Python 3.13 | 8507 | 6415 | 2021 | 61 | 10 |
| Advanced Python 3.12 | 622 | 524 | 98 | 0 | 0 |

Все core rosters и node/state outcomes между Python совпадают. База
`df9b682fdd13d8f4d1c5bff6cc4bfc0286e5f8ce`: 8505 = 6031 PASS / 2403 FAIL / 61 ERROR / 10 SKIP.
Переходы: **383 FAIL→PASS**, из них **382** reviewed test/fixture migrations и
**1** отдельная согласованная catalog-policy migration; **1 PASS→FAIL**;
**2 новых PASS**, удалённых cases — **0**. Итого PASS вырос на 384, это не 384
исправленных прежних failures. Advanced сохраняет все 622 прежних node/state
records без изменений, включая 98 FAIL.

| Reviewed scope | FAIL→PASS | Смысл результата |
|---|---:|---|
| Membership fixtures | 36 | graph19 + source-map17; 2 затронутых graph FAIL остаются |
| Dictionary fixtures | 27 | Все выбранные 27 сохранивших assertions cases PASS |
| Literal question boundary | 295 | Все выбранные successors PASS; frozen outside cases сохранены |
| Member transaction fixture family | 24 | Из 51 затронутого старого FAIL ещё 27 FAIL |
| Catalog policy | 1 | Согласованное изменение numeric policy, отдельно от runtime fixes |

Оба новых hash/consent/CAS integrity tests PASS. Единственная прежняя PASS
регрессия — `test_agent_templates_include_three_tool_selection_guidance`:
буквальный `documentation-governance meta-question` не совпал с сокращённым
`docs-governance meta-questions`. Это actual f0 FAIL; отдельно reviewed исправление
не является доказательством PASS исправленной версии до её CI.

Полный roster сохранён один раз в
[PR211_CONTINUATION_OUTCOMES.json.gz](PR211_CONTINUATION_OUTCOMES.json.gz):
**9129 unique nodes**, core 8507, advanced 622,
overlap 0. Каждая запись содержит
`nodeid`, `state`, `baseline_state` и `suites`; все remaining FAIL/ERROR IDs и
точные переходы доступны без огромных сообщений. Canonical UTF-8 JSON и
`gzip mtime=0`; compressed SHA256 `25d2b819b06bdbec2c785ba5e6648cff18daa44069fb620710dc059f248c9da4`.

## Required CI, downstream и retrieval

`required-ci` job **113459786854 = FAILURE**. Core, advanced, docs-contract,
platform and retrieval failures не сняты. На f0 десять substantive downstream
commands были **SKIPPED** после advanced pytest failure. Успешный optional
artifact upload не означает исполнение mutation gates; отсутствующие отчёты
также не доказывают downstream PASS. В JSON перечислены все десять commands.

Retrieval job **113455869695 = FAILURE** на действительном merge SHA:
**full model-visible DTO exceeded the 800-token ceiling**. Это отдельный
неизменённый gate. Catalog waiver его не отменяет. Printed frozen80 metrics:
48 within budget, 30 sufficient, zero operational/integrity errors; это не PASS
gate и не доказательство улучшения поиска. Retrieval artifact metadata сохранена;
его 20 MB архив этим audit не скачивался.

Catalog: **6918 bytes**, output schema **860 bytes**. Owner отменил фиксированные
catalog ceilings 6144/10240 и сохранил минимизацию/измерение. Новый replacement
ceiling не введён. Output bound 1000 и отдельный retrieval gate 800 не отменены.

## Installed/runtime evidence с точными границами

Отдельный SDK/log audit подтвердил **12 полных installed SDK invocations**, **24
prepared structured/text lanes**, cold default/advanced negatives, настоящий
confirmed cold preparation и restart/CAS. В каждом SDK invocation module origin
находится в `site-packages`. Prepared matrix включает project/all/module scopes,
module/version mismatches, exact local library versions, partial/complete и large
delivery; observation fields и binding/wire metrics сохранены компактно в JSON.
Source/library generation rows остаются прежними; это не неизменность всех DB bytes.

В main CI три platform stdio steps **SKIPPED**, потому что preceding package/CLI
checks упали на той же wording assertion. Их нельзя переименовать в PASS благодаря
другому workflow. В **P1 stack** три platform SDK jobs, build, wheel 3.11/3.12/3.13
и sdist/installer — actual PASS, но workflow в целом **FAILURE**. В **Release**
build, три wheel jobs, sdist/installer и required-release — **SUCCESS**.
Publish/public-platform/registry jobs SKIPPED: релиз не публиковался.

Installed scripted harness — **1/1 task PASS**, 2 tool attempts с одной ожидаемой
schema repair; это deterministic scripted provider, не реальная model session.
Регистрация installer smoke использует CLI stubs. **Claude Code / Codex /
OpenCode actual client sessions = NOT RUN**. Local preloaded library fixture не
сертифицирует network library lifecycle. Release sdist SDK origin не доказывает
отдельно запуск SDK внутри вновь созданного installer uv environment.

## Все 17 workflow results на f0

Fresh GitHub API snapshot: {'skipped': 1, 'failure': 8, 'success': 8}. Все runs завершены, attempt 1, exact f0 HEAD.

| Workflow | Итог |
|---|---|
| [Direct question validation](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292909) | SKIPPED |
| [P1.4 paraphrase and proofability](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292773) | FAILURE |
| [P2 federated task-pack reopening](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292824) | SUCCESS |
| [P2.1C task pack](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292798) | SUCCESS |
| [P2.3 Product Truth decision](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292771) | SUCCESS |
| [P1.5 mixed-evidence provenance](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292896) | FAILURE |
| [P2.2A comparative harness](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292777) | SUCCESS |
| [P2 Product Truth protocol](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292770) | SUCCESS |
| [P1.6 evidence is data](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292847) | FAILURE |
| [P2.1B positive controls](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292967) | SUCCESS |
| [P1 Agent Truth closure](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292952) | FAILURE |
| [P2.2B/C execution gate](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292838) | SUCCESS |
| [Task 33C pull-request checks](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292839) | FAILURE |
| [Language flow investigation](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819293029) | FAILURE |
| [Release artifact gate and publish](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292882) | SUCCESS |
| [P1 stack exact validation](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292991) | FAILURE |
| [CI](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292857) | FAILURE |

## Что остаётся открытым

2021 core FAIL, 61 ERROR, 98 advanced FAIL и другие красные workflows сохранены.
Это не blanket «legacy failures»: среди оставшихся есть ranking, scope/identity,
qualification/admission, safety negatives, semantic expectations, API/fixture
deficits и реальные недоставленные evidence. Два graph failures требуют screen/
cubit ranking и retired status-token contract analysis. Mutation family всё ещё
показывает 27 read/qualification/safety failures либо отдельный legacy sync.
На f0 все 34 generated successor candidates остаются FAIL.

Отложенный retrieval не менялся, gold/thresholds/gates не подменялись. Следующие
registration/generated/downstream-scheduling follow-ups после f0 здесь имеют
статус **NOT RUN / NOT AUDITED**; новое SHA должно получить собственный audit.
Ни полный CI, ни client acceptance, ни merge readiness не объявлены PASS.

Компактный manifest с provenance, artifact metadata и исходными audit-file hashes:
[PR211_CONTINUATION_ACCEPTANCE.json](PR211_CONTINUATION_ACCEPTANCE.json), SHA256
`e1b76580af940d0e41456dc53a3650956bc5d10459b2022124140ad03e4d6752`. Большой runtime audit и raw logs не вложены.
Старые `PR211_ACCEPTANCE*` artifacts не перезаписывались.

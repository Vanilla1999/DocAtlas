# Этап 3: воспроизведение, узкий dependency fix, оставшиеся gates

**BLOCKED_FROZEN_DOCUMENT_IDENTITY_AND_BASELINE_CONTRACTS.**
Техническая часть и весь этап 3 НЕ завершены. Независимое ревью PENDING.
**main merge: NOT_DONE.** Merge/release/deploy/auto-merge не выполнялись.

## Установленная identity

Remote refs перед работой совпали с handoff. Работа выполнена в отдельных
полноценных clean worktree; исходная пользовательская dirty-копия не менялась.

| Назначение | Точный SHA |
|---|---|
| main baseline | d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c |
| PR-1 #206, неизменённый head | 596eeb36b66a474b2b5d246fd6bd834b6dcbb5c6 |
| documentation-only #207, неизменённый head | bf89ee4a15c76bbbd96a3c65015d01d80d5a92e5 |
| #207 synthetic merge из CI | c6496f7a47579650c8fe9f2580ddc9d75deab699 |
| #206 synthetic merge из CI attempt 2 | fac1dbd2d9de53eba452d38ef2c462c2653efb3b |
| base fix #208 | 31997db9323c2df8f3f5a18b323dcbfda9328bb1 |
| integration #209 | 462c769210cdd46c50b035d151d8b7f9d6450391 |
| #208 synthetic merge | f1611150a60775cba6f701bbed8dd9b12b9c8fbc |
| #209 synthetic merge | 97f6413554c43e816d623ad0e95d94be2d74bb4f |

Parents обоих synthetic merge: exact main + соответствующий PR head.
Git diff main→#207 содержит только его PROTOCOL_RU.md. Merge-SHA не выдаётся
за PR head и не означает реальный merge в main.

Все три исторических модуля (`test_agent_developer_adversarial.py`,
`test_compositional_task_matrix.py`, `test_unified_context_service_pipeline_surface.py`)
отсутствуют в закреплённом main Git tree и pytest collection. Первый прямой
запуск отсутствующего adversarial-модуля: exit 4, no tests ran.
Никакие похожие тесты не использованы как замена этим node IDs.

Фактический baseline: **5887 collected; core 36 FAIL / 5219 PASS / 10 skipped;
advanced pytest 622 PASS**. Контроль CI run 37303582475 / attempt 1 на c6496f7a
имеет такой же core-набор; Python 3.12 job 111741830974. Advanced job
111741830770 проходит pytest, но падает позднее на lineage floor 10 < 12.
PR-1 CI 37298795100 / attempt 2 на fac1dbd2: core Python 3.12 job
111743186469, advanced job 111743186171. Полные job snapshots сохранены.

**BASELINE_CHANGED_OBSERVATION** относительно прежнего отчёта о пяти ошибках.
Несоответствие старого evidence подтверждено отсутствием его исходников и
другим реальным набором результатов. Происхождение ошибочных прежних excerpts
не установлено; старые пять ошибок не объявлены исправленными.

## Доказанный и исправленный дефект

`pyproject.toml` позволял `fastembed>=0.4.0`; штатная CI установка
`pip install -e '.[dev]'` выбирает 0.8.1. Неизменный reviewed protocol lock
требует 0.8.0; существующий validator корректно отвергает несовместимую среду.
`uv.lock` уже содержал package 0.8.0, но разрешающая декларация расходилась
с обязательным protocol version при editable install.

Отдельный fix закрепляет **fastembed==0.8.0**, без изменения protocol lock:

- `pyproject.toml` — единственная dependency declaration;
- `uv.lock` — только соответствующая requires-dist declaration; package версии
  и остальные зависимости lock не менялись;
- `tests/test_frozen_fastembed_dependency.py` — два узких configuration regressions;
- `tests/diagnostic_labels.frozen_fastembed_dependency.json` — штатная регистрация
  только нового модуля; старые labels/expectations неизменны.

FAIL до: существующий multilingual suite **14 failed, 5 passed**, exit 1.
PASS после: **19 passed**, exit 0; вместе с новыми regressions **21 passed**.
Новая declaration regression отдельно читает exact main configuration и FAIL;
этот read-only запуск вне baseline collection обозначен явно.
Существующие положительные и отрицательные проверки не менялись.
Пакетные версии base/candidate совпадают, кроме FastEmbed и editable install path.

## Проверка PR-1 и integration

PR-1 остаётся на 596eeb36. Base fix не добавлен в его закрытый состав.
Integration = exact main + 31997db9 + четыре исходных PR-1 commits,
cherry-picked без изменения их product/test contents; provenance в evidence index.
Проверка integration НЕ является допуском существующего #206.

Локальная среда Python **3.12.3**, Linux; hosted CI использует Python **3.12.14**.
Editable установка выполнена через uv pip с зависимостями из текущего pyproject,
не через frozen sync; отличие install frontend явно сохранено. Runtime import
paths/hashes и все package versions находятся в environment manifests.

| Gate | PR-1 596eeb36 | Integration 462c7692 |
|---|---|---|
| Три исходных PR-1 модуля | 42 PASS | входят в 63 PASS focused |
| Focused: PR-1 + dependency + multilingual | отдельные прогоны | 63 PASS |
| Offline core | CI attempt 2 FAIL | 22 FAIL, 5277 PASS, 10 skipped |
| Advanced pytest/security | 622 PASS | 622 PASS |
| Recovery contract | PASS | PASS |
| Recovery mutation | PASS | PASS |
| Hermetic project chat | PASS, retrieval_executed=false | PASS, не live retrieval |
| Legacy report-only generation | exit 0, не quality PASS | exit 0, не quality PASS |
| Legacy lineage | FAIL | FAIL |
| V2 project quality | FAIL: document revision mismatch | FAIL: document revision mismatch |
| Question surface | FAIL | FAIL |
| Agent Developer protocol | PASS | PASS |
| Agent Developer adversarial | FAIL | FAIL |
| Critical mutation | PASS | PASS |
| Agent adversarial mutation | PASS | PASS |
| Source install stdio smoke | PASS | PASS |
| Installed harness self-test | PASS | PASS |
| Exact reviewed wheel + real stdio + report verification | historical CI PASS | local PASS, 1/1 task |
| Docs/CLI contract | historical CI PASS | local 100 PASS |
| Static workflow command set + diff check | historical CI PASS | local PASS |

Wheel SHA256: `74638c337f432a146c4a6714f8cc84b5626d913ed2567eccec3aafa614b2b1f8`.
Report verification binds full source_commit 462c769210cdd46c50b035d151d8b7f9d6450391,
reviewed-wheel origin, hash chain, privacy and bounded schema repair.
Это pre-public installed harness, НЕ smoke разрешённого main merge-SHA.

Все локальные gates исполнены отдельно, включая шаги, которые CI пропускает
после FAIL. Ledger содержит точную команду, SHA, stdout/stderr, exit и elapsed.
Полный удалённый gate roster с run/job/attempt и статусами — `ci-gates.json`.
Pending/queued/skipped/NOT_RUN нигде не считаются PASS. Branch rules API вернул
пустой список; protection API 404 — не основание снимать требования workflows.

### Завершённый удалённый CI integration

Run **37310505012**, attempt **1**, checkout **97f6413554c43e816d623ad0e95d94be2d74bb4f**
(head 462c769210cdd46c50b035d151d8b7f9d6450391):

| Job | ID | Фактический результат |
|---|---|---|
| Core 3.11 | 111764458971 | FAIL |
| Core 3.12 | 111764458925 | FAIL |
| Core 3.13 | 111764459270 | FAIL |
| Advanced contract | 111764458887 | FAIL на последующем lineage gate |
| Installed MCP harness | 111764458848 | PASS |
| Windows smoke | 111764459162 | PASS |
| macOS smoke | 111764458986 | PASS |
| Static | 111764458999 | PASS |
| Docs/CLI | 111764459015 | PASS |
| Installer | 111764459016 | PASS |
| Retrieval evidence | 111764458873 | PASS |
| required-ci | 111768116192 | FAIL |

Release validation run **37310504880**, attempt **1**: `required-release`
job **111766346049 PASS**; build, wheels 3.11/3.12/3.13 и sdist/installer PASS.
Publication jobs skipped, НЕ PASS и НЕ release. P1.6 run **37310504917**,
attempt **1**, job **111764457745 FAIL**. Оставшиеся checks P1-stack и прочих
workflows не подменяются этим CI; полный их snapshot в `ci-gates.json`.

Base-fix run **37310499558**, attempt **1** тоже содержит реальные core FAIL
и advanced FAIL; его remaining running check не объявлен PASS.
Base-fix release run **37310499436**, attempt **1**, required-release
job **111766300119 PASS**. Технического общего допуска ни у #208, ни у #209 нет.

## Конкретные оставшиеся блокеры

1. Frozen active-document hashes не совпадают с **README.md** и
   **docs/project-docs-mcp-workflow.md** внутри самого exact main. Expected/actual
   SHA256 и lock path сохранены. Validator не ослаблен; lock/gold не обновлялись.
   Нужен owner-reviewed способ согласовать frozen corpus с документами;
   просто переписать hashes ради PASS запрещено данным заданием.
2. После dependency fix остаются **22 воспроизведённых core failures**.
   Их node IDs, assertions/tracebacks и observed locals сохранены; для четырёх
   направлений дополнительно сохранены полные repr ответов в read-only hook.
   Полная причинная диагностика всех 22 не завершена; speculative parser/ranking,
   scope/applicability fix по названиям не делался.
3. Lineage, question surface и adversarial gates реально FAIL. Adversarial
   показывает module-scope status mismatch и 380 > 300 token projection;
   это результат действующего gate, не повтор старого отсутствующего node ID.
   Владеющий причиной слой не доказан достаточно для изменения guards.
4. Удалённые required checks конкретных PR не получены как общий PASS.
   Неисполненные/незавершённые checks на момент snapshot остаются такими.
5. Независимое review и разрешение владельца отсутствуют. Авторская проверка
   diff не названа независимым одобрением.

## Evidence и ограничения исполнения

Index: `EVIDENCE_INDEX.json`; remote CI: `ci-gates.json`.
`raw/main-source-manifest.json` содержит полный tracked manifest и SHA256;
runtime/environment manifests связывают actual imports с checkout.
`raw/main-observed-failures.jsonl` содержит source hashes, fixtures, node IDs,
native observed locals и assertion одного исполнения. Hook hash в index:
он только наблюдает failure frames, не заменяет callable/fixture/result.
Отдельный неинструментированный прогон сохранён для сравнения.

Первый локальный full-core запуск прерван лимитом инструмента 120s; сохранён
как TIMEOUT, не FAIL алгоритма. Второй завершён без смены revision/зависимостей.
Первый installed harness вызов ошибочно получил короткий SHA и был отклонён
до execution; исправлен только CLI аргумент, исходная ошибка сохранена.
CI meaningful failures не перезапускались до зелёного результата.

Pre/post полный manifest непосредственно для linked focused execution совпал.
Для первых collection/full-suite до первого запуска отдельный hash manifest
не записан; их runtime/test bytes затем сверены с неизменным Git tree.
Это ограничение не скрыто и не заменено выдуманным preflight.

Full product diff и git diff --check проверены. Изменений workflows, guards,
parser/ranking, public MCP schema/API, 800/3, 32000, caller limits, frozen labels
и expectations нет. N10, PR-2, retention и модельные эксперименты не запускались.
Новые PR — draft #208 и #209; #207 остаётся только диагностическим контролем.

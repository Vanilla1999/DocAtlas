# 02. Один владелец read-решения

Статус: REJECTED для простого удаления `no_new_direction` (изолированная ablation
по дополнительному запросу пользователя). Общее решение остаётся BLOCKED.
Миграция и runtime patch не выполнены.

## Уже сделано

`152a4c7b`: original-read больше не зависит от proof-qualification reasons.
80/80 final payloads совпали, 49 → 49 supported claims; recall gain 0.
120 focused tests прошли; full suite имеет те же 130 failing nodes, что baseline.
Это не green rollout и не unseen validation.

## Цель и граница

Убрать конкурирующую read-обязанность, сохранив полезные facts. Source-policy,
identity/applicability, claim support и permissions сохраняются. Preferences
в целевом виде только сортируют уже admitted окна. Сам wrapper не упрощение.

## Этап 1 — выбрать одну обязанность для удаления

Использовать `EXACT_WINDOW_CONFLICT_RESULT_RU.md` и пример из плана 01.
На одних request/source/span показать: какое решение расходится, scope всего
вопроса или отдельного need, менялись ли bytes. Различать policy reject и
отсутствие proposal. 586 disagreements не считать 586 ошибками.

Выбрать **один** объект: competing read veto ИЛИ prefit/final proposal mismatch.
До кода записать: удаляемая ветка, оставшийся владелец, полезный positive,
wrong-subject/state и irrelevant negative, ожидаемый final результат.

**DONE:** правило сформулировано без OR fallback и без объединения всех veto через AND.
**STOP/BLOCKED:** общего правила нет. Сохранить конкретный контрпример; не писать
новый compiler. Завершённый анализ с BLOCKED — не выполненная миграция.

## Этап 2 — один изолированный patch

Удалить выбранную обязанность; не добавлять параллельную разрешающую ветку.
Не менять одновременно retrieval, compiler, thresholds и selection ordering.
Сохранить source/security/version/scope/freshness/span/request, literal/subject
и applicability guards. Unknown condition не считать applicable.
Повторная проверка после clipping обязательна и не является лишней политикой.

**DONE:** один read-владелец для выбранного участка; regression test воспроизводит
исходный конфликт и проверяет итоговые bytes/flags, а не только reason string.

## Этап 3 — приёмка и остановка

Один paired full-native replay с freshly measured baseline на том же inventory
и budget. Проверить baseline/partial facts, новые negative packets, guards и
proof/edit flags. Focused tests плюс baseline comparison при full-suite failures.
Frozen labels не менять ради результата; development controls не называть unseen.

**ЗАВЕРШЕНО:** удалена одна конкурирующая обязанность, нет новых измеренных потерь
или negative/guard regressions. Отдельно записать recall gain, включая нулевой.
Если цель была recovery конкретного факта — он должен появиться в final bytes.
**ОТКЛОНИТЬ:** потеря baseline fact, ослабление guard или необходимость case exception.
Не компенсировать результат новым fallback. Rollout — отдельное решение;
unseen validation и общий red suite остаются явными ограничениями.

## Результат

### Этап 1 — локализация выполнена, правило замены BLOCKED

Baseline: `3c2ef231`. Использованы both/partial/absent/wrong из плана 01 и
`EXACT_WINDOW_CONFLICT_RESULT_RU.md`. Старые 586 disagreements относятся к
другой read boundary и не объясняют этот selection отказ.

Research-only runner теперь наблюдает actual `ProjectionDecisionTrace.record`,
делегируя вызов unchanged original method. Дополнительные события содержат
source path и actual attempted snippet; runtime/defaults не меняются.

Команда: `PYTHONPATH=. .venv/bin/python v2plan/lookup_gap_probe.py --output
/tmp/opencode/lookup-gaps-02-decisions`. Восемь calls, один native index на пару.

**Конкретная ветка:** `_docs_context_projection_core.py`, selection condition
`if sources and not (new_components or ... same_origin_gain)` с reason
`no_new_direction` (на момент проверки строки 572–580).

| Exact attempted bytes | Без lookup | С focused lookup |
|---|---|---|
| `OrbitClient timeout configured in production is 12 seconds.` | rejected: no_new_direction | accepted; затем заменено heading-inclusive окном |
| `OrbitClient timeout configured in production is managed by the deployment owner.` | rejected: no_new_direction | accepted; затем заменено heading-inclusive окном |

И body-only, и heading-inclusive варианты без lookup получают тот же отказ.
Original question неизменен; attempted body bytes одинаковы в паре. Lookup
добавляет поисковую lane, не новые source facts. Deployment уже retrieved и
qualified до отказа. Это **selection novelty veto**, не original-read locality
refusal, не token clipping и не установленная prefit/final proposal mismatch.
Default сохраняется; foreign subject/environment и unrelated deployment text
не доставлены ни в одном arm. Proof/edit flags остаются false.

### Почему не удаляем ветку целиком

Эта же ветка отклоняет дополнительные варианты default-окна. Поэтому одинаковый
query ID не доказывает ни отсутствие нового факта, ни его наличие. Simple removal
разрешит и полезное дополнение, и дополнительные already-qualified окна без
установленного критерия их полезности; source guards не заменяют этот критерий.
Мы не измерили безопасность такого удаления и не объявляем его доказанно опасным.

Предполагаемый оставшийся владелец — existing read admission + budget/span/identity
guards — проверяет другое и сам по себе не устанавливает fact novelty. Использовать
host lookup как обязательный rescue означало бы сохранить конкурирующее решение.
Вводить новый two-word novelty threshold/compiler или case exception запрещено.

**Итог: BLOCKED, не DONE migration.** Этапы 2–3 не запускаются. Для возобновления
нужно согласовать общий selection контракт: допустимы ли несколько qualified
read windows одного вопроса без новых query IDs при прежнем budget, и по каким
existing основаниям выбирается дополнение вместо дубля. Это product/selection
решение, а не оправдание массового удаления admission gates.

Regression test фиксирует actual `no_new_direction` для обоих потерянных facts
и `accepted` после focused lookup. `.venv/bin/python -m pytest -q
tests/docs/test_lookup_gap_probe.py tests/docs/test_unified_read_admission_probe.py`:
**34 passed**. Это development controls, не unseen или full-suite приёмка.
На этом остановка по правилу этапа 1; новые маршруты автоматически не начинаем.

### Дополнительная проверка мнения: простое удаление — REJECTED

Пользователь попросил обосновать решение экспериментом. Гипотеза: query-ID novelty
не равна fact novelty, а existing dedup/guards/budget могут быть достаточны без
`no_new_direction`. Проверили только удаление этой ветки в памяти процесса.
Другие guards, replacement checks, budgets, ranking code и runtime files не менялись.
Actual selection order может измениться вследствие нового состава selected set.

Runner: `selection_direction_ablation.py`; command:
`PYTHONPATH=. .venv/bin/python v2plan/selection_direction_ablation.py --output
/tmp/opencode/no-new-direction-ablation-01`.
Fresh paired native calls: 80 frozen cases + 4 development controls; same index
и question на пару, без focused lookup. Expected labels не менялись.

- **84 pairs; 61 identical payloads, 23 changed.**
- Both/partial: без lookup восстановлены production 12 и owner sentence,
  known default сохранился. Absent/wrong: чужие/отсутствующие факты не появились.
- Frozen supported required claims: **49 → 45**, gains 0, losses 4:
  `fastapi-01`, `fastapi-02`, `fastapi-07`, `httpx-03`.
- Negative packets: 0 → 0; answer/edit/support/coverage flags без изменений.
- Synthetic recovery не суммируется с frozen supported claims.

Проверка actual bytes подтверждает потери annotated witnesses:
`fastapi-01` теряет `You can define background tasks to be run *after* returning
a response.`; вместо него появляются другие абзацы, включая CORS middleware.
`httpx-03` теряет intact explanation connect/read/write/pool timeouts, оставляя
code example, client default и отдельный pool fragment. Оценщик помечает результаты
`needs_review`, а не доказывает полную семантическую бесполезность нового packet.
Но сохранение baseline witness — обязательное условие, оно нарушено.

**Вывод:** query ID не является фактом, что доказано recovery двух разных missing
facts в controls. Однако existing selection без этой ветки не сохраняет качество
пакета при прежних ограничениях. Поэтому удалять её сейчас нельзя. Ветка выполняет
полезную ограничивающую функцию с ошибочным proxy; замена требует решения selection,
а не очередного ослабления read admission. Нет оснований придумывать lexical threshold.

Следующий разумный контракт для отдельного согласования: дополнительные окна
того же вопроса допустимы, но не должны вытеснять baseline witnesses или заменять
информативное окно меньшим без подтверждённой пользы. Это требование, не готовый
model-free алгоритм. Автоматический semantic gap detector не реализован.
Практически сейчас existing focused lookup остаётся проверенным способом спросить
missing part в этих четырёх controls; его универсальная надёжность не доказана.

Runtime patch отклонён, full-suite ablation не запускался после обнаружения
приёмочного failure. Raw payloads/traces/results/provenance сохранены в output;
короткий summary — `artifacts/selection-direction-ablation/summary.json`.

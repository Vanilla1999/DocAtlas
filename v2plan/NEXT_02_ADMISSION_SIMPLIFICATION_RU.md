# 02. Один владелец read-решения

Статус: TODO. Начать после диагностики плана 01. Не повторять весь research цикл.

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

Пока не выполнено. Здесь записать выбранную обязанность, patch/коммит, проверки
и DONE/BLOCKED/REJECTED. После исхода остановиться, не начинать следующую ветку автоматически.

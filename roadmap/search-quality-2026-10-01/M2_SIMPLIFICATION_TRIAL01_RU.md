# Первый эксперимент упрощения: объединение candidate inventory

2026-10-02. Checkpoint до эксперимента: `3b23701d`.

## Результат

**Наивное объединение typed/read admission отклонено для production.**

Пробная реализация использовала один iterator: все уже проверенные typed
alternatives, затем original-read alternatives. Prefit и final fallback
использовали один inventory. Thresholds, budgets, queries и source guards
не менялись; parent diversity в production сохранялась.

В существующем диагностическом `--no-parent-diversity` запуске нужный witness
`mkdocs-05` стал видимым: 2 sources, 3 projector candidates; independent scorer
признал required claim supported. Public `answer_supported=False`,
`edit_ready=False` сохранились. Raw:
[m2_shared_admission_trial01.json](m2_shared_admission_trial01.json).

Но targeted suite выявил **6 новых недопустимых admissions** в существующих
negative controls: вопрос-эхо, heading/scattered terms, только два topic terms,
разрозненные предложения, переставленные слова, декларативное эхо.
Typed topical route был менее строгим, чем original-read route, и раньше
prefit скрывал это расхождение. Объединение маршрутов без общего locality
contract расширило выдачу, а не только упростило orchestration.

Итого пробный suite: 22 passed / 7 failed. Шесть failures — existing negative
controls. Седьмой — новый positive test на минимальном искусственном документе:
он не получил typed variants; этот fixture не является подтверждённым
эквивалентом frozen MkDocs. Его нельзя считать доказательством восстановления.

Пробные production изменения и новые tests удалены автором после проверки.
Исходное checkpoint-поведение восстановлено; существующие tests не переписаны
ради зелёного результата. Это rejected experiment, не готовый fix.

## Уточнённый следующий шаг

1. Сначала специфицировать общий локальный read-relevance contract с сохранением
   heading-only, question echo, scattered terms и condition/identity negatives.
   Простое объединение разрешений разных маршрутов недостаточно.
2. Проверять candidate retention и final delivery отдельно; снять parent-first
   promotion только в сравнительном arm, не смешивать с admission policy.
3. Вариант «большой блок → маленькое окно» проверить как отдельный arm:
   bounded section-sized retrieval unit сохраняет anchors вокруг правила;
   final exact-span window ограничивается прежним DTO budget.
4. Не наследовать proof/permission от большого блока и не допускать вопрос-эхо
   только из-за его lexical score. Окно должно сохранять локальный содержательный
   факт и его applicability; source/hash/version guards повторяются по bytes.
5. Сравнить на exposed regression cases и independent negatives, затем held-out
   panel. Если выигрывает только MkDocs, production решение не принято.

Таким образом, направление остаётся **упрощение решений**, а не снижение
thresholds. Эксперимент уже показал, какую простую замену делать нельзя.
M2 остаётся открытым. Полный regression suite не запускался.

После снятия trial production diff относительно checkpoint пуст.
Повторный baseline boundary suite: **23 passed**. Предупреждение окружения:
pytest runner без pytest-asyncio не распознаёт `asyncio_mode`; эти тесты sync.

# P1: утверждение и freeze

**P1 DONE. P2 NOT STARTED.** Дата: 2026-10-06.

## Основание

На вопрос об утверждении пакета behavior/TD/TM, freeze 224 cases, переносе
архивного хвоста P0 и численных лимитах владелец выбрал:
**«Да, утвердить и закрыть».**

Одобрены ровно следующие решения:

- Behavior contract из `P1_CONTRACT_RU.md`: сохранение полезного RU/EN и partial
  context, честная attribution, scope/freshness/provenance/budget guards,
  отсутствие ложного proof; existing typed-proof positive controls обязательны.
- TD01–TD06 в указанных границах. TD03: существующая number normalization —
  временная изолированная dependency до доказанной замены, не постоянное
  разрешение смысловых таблиц. TD06: explicit scope contract; конкретный public
  DTO diff согласовывается при реализации. Blanket approval 1209 candidates нет.
- TM01–TM06 как процесс миграции. Разрешения удалить/ослабить 159 assertions нет;
  каждый будущий diff требует replacement evidence/review/approval. Старые
  coverage thresholds, README sidecar и release gates остаются обязательными.
- Freeze exact independently reviewed development/holdout bytes. Holdout
  family-disjoint, но не blind/source-disjoint; это известное ограничение.
- P0 archival provenance gap разрешено оставить отдельным долгом. Только
  требование P0 DONE как предварительного условия P1 freeze/P2 entry заменено
  этим явным решением. Сам P0 не DONE; baseline/required checks не стали green.

## Утверждённый ресурсный профиль

| Ограничение будущей реализации | Предел |
|---|---:|
| Платные внешние API | $0 |
| Внешние вызовы replacement во время обработки запроса | 0 |
| Дополнительное постоянное хранилище replacement | ≤2 GiB (2147483648 bytes) |
| Прирост warm p95 к baseline на том же окружении | ≤1 с |
| Прирост cold p95 к baseline на том же окружении | ≤5 с |
| Увеличение текущих output/search budgets | 0 |

Это ceilings, не измеренные результаты. Дополнительное хранилище включает
replacement model/index/cache assets; измерять дельту на одинаковом corpus.
Latency сравнивать paired baseline/candidate на одинаковом environment/config/
corpus и cold/warm режиме. До candidate execution закрепить serializer,
tokenizer, sample protocol, config/model/prompt/index/environment versions;
не выбирать protocol по полученным результатам. Model-dependent final holdout:
минимум 3 повтора, диапазон и worst run, не best-of.
Утверждение не инициирует установку/загрузку модели или выбор нового backend.

## Авторитет статусов и неизменность evidence

`archives/p1-approved-freeze-manifest.json` — текущая approval/freeze запись.
Она связывает approval, independent review и original reviewed inputs по SHA256.
Старые draft/reference файлы содержат исторические PENDING/NOT APPROVED statuses:
их bytes сохранены, а статусы superseded только этим approval и новым manifest.
Это относится также к прежним P0-DONE freeze prerequisites в draft/exit plan.

Проверка: `python3 v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06/p1_approve_freeze.py`.
Runner проверяет review/source/split/ledger hashes и отказывается перезаписывать
freeze с другими bytes. Изменение контракта/корпуса после freeze — новая версия
с сохранением старого отчёта и новым approval.

Следующий этап — P2 implementation в этих пределах. Existing red gates и
wheel portability defect остаются отдельными задачами; merge не разрешён.

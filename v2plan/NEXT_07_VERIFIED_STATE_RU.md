# 07. Проверенное состояние и следующая узкая правка

Дата: 2026-10-04. Ветка: `next07-feasibility-audit`.
Этот документ уточняет актуальный статус плана 07. Старые NOT_RUN/BLOCKED в исторических отчётах не являются очередью повторных работ.

## Закрытые технические задачи — не переписывать

Основание: настоящий GitHub Actions run [37231552540](https://github.com/Vanilla1999/DocAtlas/actions/runs/37231552540), commit `ea7eef380eb2b0a11b0216063939b2b8ae1773de`.
Artifact ID `11314256764`, SHA-256 ZIP `3c963d4579149a73a76c7ca16a7d93ba84d50f3402cb47799f0fe38bbf19fe7d`.

| Задача | Статус и предел подтверждения |
|---|---|
| Typed wiring | OK: реальные вызовы проходят handler/projector/validator; hooks восстанавливаются |
| Scope transport | OK для проверенных current project/all/module_path read-сценариев; неподдержанные assisted/historical/change lanes не объявлены реализованными |
| Empty DTO | OK: пустая выдача оформляется как insufficient_evidence, не успешный пустой packet |
| Line-range audit | OK на этом прогоне: N и C без audit errors; точные LF/CRLF bytes проверяются отдельно |
| Снятие 800/3 | OK в явно включённом compact-read: C реально выдаёт более 800 tokens и более 3 источников; production defaults не переключены |
| LeaseClient delivery | OK: P1 — 17 seconds + LeaseExpired, 611 tokens/3 sources; P2 — 29 seconds + WaitExpired, 618/3; P3 — default без выдуманной exception, 454/2 |
| Диагностический harness | OK: 80/80 валидно оценённых N/C пар, 160 настоящих public calls, frozen inputs неизменны |

Это закрытие конкретных технических задач, не доказательство безошибочности на любых входах, не общий guard acceptance и не разрешение rollout. Регрессионный запуск допустим; переписывать эти ответственности ради очередного эксперимента не нужно.

## Качество ещё не принято

В этом baseline fresh assessor-only retained/lost/gained = 23/27/3.
Historical 49 retained/lost/UNKNOWN = 22/15/12.
Из 28 наблюдённых событий по поддерживавшим строки потерянных фактов: 26 имеют reason hidden_structural_dependency, 2 — missing_visible_exact_or_subject. Это причины наблюдённых строк, не доказательство единственной причины каждого claim.

## Разрешённая следующая работа

Пользователь: зафиксировать закрытые части, сделать structural-owner fix, затем review, затем запуск **без N10**.

Меняется только ответственность формирования и проверки read-unit: BM25 hit находит исходный диапазон, до source rebind материализуется целиком пересекаемый parser-owned section/sections; потребитель повторно выводит ту же границу из проверенного snapshot. Не требуется новый parser смысла вопроса.

Не менять rank_rows, FTS query, BM25 weights, splitter, first_fit, scope wiring, guards, budgets proof/edit, corpus/labels. Не делать post-reject rescue, дополнительных чтений/lookup или semantic compression. Увеличенный диапазон заново проходит существующую подготовку источника, current-catalog и read guards.

N10 в этой задаче **NOT_RUN / EXCLUDED_BY_USER**. Его прежний REJECTED остаётся историческим фактом; не удалять test/gold и не добавлять allowlist. Непредвзятый frozen corpus 80 не сокращается. Нельзя назвать общую продуктовую приёмку выполненной за счёт исключения N10.

Перед native run обязателен сохранённый review diff и checks; затем native LeaseClient, structural positives/negatives и те же 80 N/C. Не повышать общий verdict по зелёному workflow. Дальнейшие исправления после содержательного провала не добавлять автоматически.

Подробный протокол до реализации: [owner-delivery protocol](artifacts/next07/owner-delivery-20261004/PROTOCOL_RU.md).

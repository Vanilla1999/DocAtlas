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

## Качество baseline ещё не принято

В baseline fresh assessor-only retained/lost/gained = 23/27/3.
Historical49 retained/lost/UNKNOWN = 22/15/12.
Из28 наблюдённых событий по поддерживавшим строки потерянных фактов:26 имеют reason hidden_structural_dependency,2 — missing_visible_exact_or_subject. Это причины наблюдённых строк, не доказательство единственной причины каждого claim.

## Выполненная owner-delivery работа

Пользователь запросил: зафиксировать закрытые части, source-owner fix → review → запуск **без N10**.

Код реализован в5f982a56; review сохранён до исполнения в4dfd4e75. Один новый test precondition исправлен отдельно; алгоритм в79534699 тот же.
[Настоящий run37233045584](https://github.com/Vanilla1999/DocAtlas/actions/runs/37233045584):173 PASS, LeaseClient P1/P2/P3 PASS,80/80 N/C исполнены. Production/wiring/first_fit/guards/evaluator не изменялись.

**Итог: REJECTED_SOURCE_INTEGRITY**, а не DONE. Hidden_structural_dependency больше не встречается. Fresh assessor-only46/3/6, historical49:40/0/9UNKNOWN. Но17 C packets испорчены transport-compactor ПОСЛЕ чистого handler validator;115 цитат обрезаны. Отмена800/3 была проверена, но это не доказывало отсутствия отдельного порога32 000 bytes на следующих стадиях. Этот порог и lossy-compaction теперь наблюдены напрямую.

[Полный отчёт и конкретный новый blocker](artifacts/next07/owner-delivery-20261004/SUMMARY_RU.md).
[Machine-readable result](artifacts/next07/owner-delivery-20261004/result.json).

Следующий отдельный контракт — неизменность validated citations при terminal serialization/transport. Это не исправление parser/BM25 и не повод переписывать закрытые обязанности. После полученного meaningful failure transport в этой попытке не менялся, правила автоматически не расширялись.

N10 **NOT_RUN / EXCLUDED_BY_USER**. Его прежний REJECTED остаётся историческим фактом; test/gold и allowlist не менялись. Frozen corpus80 не сокращался. Общая продуктовая приёмка и rollout не разрешены.

Подробный протокол до реализации: [owner-delivery protocol](artifacts/next07/owner-delivery-20261004/PROTOCOL_RU.md).
Авторское ревью: [review](artifacts/next07/owner-delivery-20261004/REVIEW_RU.md), [test-precondition amendment](artifacts/next07/owner-delivery-20261004/REVIEW_AMENDMENT_RU.md).

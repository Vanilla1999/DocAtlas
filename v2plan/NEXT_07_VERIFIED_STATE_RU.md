# 07. Проверенное состояние — читать до старых шагов плана

Дата: 2026-10-04. Ветка next07-feasibility-audit, не main.
Это текущая запись состояния; исторические NOT_RUN/BLOCKED/REJECTED в отчётах
не являются командами начать прошлую попытку заново.

## Последнее завершение: TRANSPORT_VALIDATED

Пользователь попросил повторный анализ и правильный transport fix, затем
обсуждение N10. Реализовано4b37ba3a, review2d5ad6f7 до исполнения,
нативный run [37235320731](https://github.com/Vanilla1999/DocAtlas/actions/runs/37235320731)
на5f878b206b18ca8e5bc97624744fe78e00124680.
[Отчёт](artifacts/next07/transport-integrity-20261004/SUMMARY_RU.md),
[точные результаты и ID](artifacts/next07/transport-integrity-20261004/result.json),
[review](artifacts/next07/transport-integrity-20261004/REVIEW_RU.md).

212 PASS research/native +13 PASS existing product tests.80/80 N/C пар валидны,
оба source audit чистые.160 packets дополнительно сериализованы настоящим SDK
в2 формах каждый; все320 результатов равны исходным final payload и audit чистый.
Это handler+SDK execution, не отдельная live stdio/network session.

Canonical projections больше не подвергаются lossy compaction. Две существующие
terminal границы используют один consumer. Без caller override32KB остаётся
finite limit с явной ошибкой; COMPACT_READ_LIMITS явно снимает transport byte cap.
Explicit finite max_bytes приоритетен. Source metadata не выбирает policy.
Ни одной новой relevance-эвристики, LLM или ослабления guard не добавлено.

## Закрытые технические обязанности — не переписывать

| Обязанность | Проверенное состояние |
|---|---|
| Typed wiring | OK: real handler/projector/validator и восстановление hooks |
| Scope transport | OK для current project/all/module_path; не обещает assisted/historical/change |
| Empty DTO | OK: insufficient_evidence вместо успешной пустой выдачи |
| Line-range audit | OK: final источники и координаты, LF/CRLF checks, не normalizing fake quote |
| Снятие800/3 | OK в явном compact-read; production defaults не переключены |
| LeaseClient P1/P2/P3 | OK:17/LeaseExpired,29/WaitExpired,partial без выдуманной exception |
| Harness80/80 | OK:160 real calls, frozen inputs unchanged, review queues сохраняются |
| Owner materialization | OK в измеренных tests/corpus: search chunks дают exact source owners до admission |
| Terminal transport | OK: whole projection or explicit failure; нет обрезанных quotes с прежними hashes |

Regression допустима. Эти результаты не доказывают безошибочность на любых
источниках, полный guard acceptance, достаточность контекста или rollout.

## Качество: что осталось открытым

Текущий fresh retained / lost recognized support / gained =48/1/6.
Historical49:48 source-valid retained,0 definite lost,1 UNKNOWN — fastapi-02.
В fastapi-02 supporting input [1095,1610] background-tasks.md отказан
missing_visible_exact_or_subject ДО transport; итог needs_review. Guard не снят.
Все52 recognized C IDs предыдущего owner-run сохранены; добавились ruff-06/uv-05.
Selected source sets до transport совпадают с прошлым run во всех80 случаях;
N assessor statuses тоже совпадают.17 прежних transport-damaged cases теперь чисты.

C median3386.5 tokens, max15294; max56937 UTF-8 JSON bytes и19 sources.
Отмена caps не означает смыслового сжатия. Краткость оптимизировать до фиксации
цитат, не разрушая готовый packet на транспорте.

N10 NOT_RUN_UNCHANGED: test/labels/allowlist не менялись. Только
[обсуждение](artifacts/next07/transport-integrity-20261004/N10_DISCUSSION_RU.md).
Не запускать новую эвристику/модель по этой записи автоматически. Общий candidate
acceptance пока не объявлен:48/49 не49/49, historical partial ledger/full suite/
reader evaluation ещё не закрыты. Rollout NOT_AUTHORIZED.

## История, не очередь повторных работ

Первоначальное техническое закрытие: run37231552540 наea7eef38, artifact11314256764,
SHA256 ZIP3c963d4579149a73a76c7ca16a7d93ba84d50f3402cb47799f0fe38bbf19fe7d.
Тогда wiring/scope/empty/audit/800/3/LeaseClient/80-pair harness работали на
измеренных входах, но это не выявляло32KB boundary на более длинных owners.

[Owner-run](artifacts/next07/owner-delivery-20261004/SUMMARY_RU.md):
37233045584 на79534699,173 PASS, fresh46/3/6, historical40/0/9UNKNOWN;
hidden_structural_dependency исчез, но17 packets/115 snippets повреждены после
validator. Тот замер остаётся REJECTED_SOURCE_INTEGRITY; новый результат его
не переименовывает. Transport исправлен отдельной следующей revision.

Первый transport-run37235135829 был invalid до тестов из-за смешанной pytest
collection; исправлены только команды запуска, не код/guards/ожидания.
История сохранена в REVIEW_AMENDMENT_RU.md. Старый compiler-only BLOCKED,
исторический N10 REJECTED и прежние outputs не переписываются.

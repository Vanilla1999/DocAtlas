# MiniLM: оставлен опционально, ТРЕБУЕТ ПРОВЕРКИ

Решение владельца2026-10-13: оставить испытанный MiniLM reranker с пометкой
проверить. Не включать по умолчанию; не добавлять большую вторую модель.

Модель: `cross-encoder/ms-marco-MiniLM-L6-v2`, revision
`233902d25c440f23af6f7d6e94d2946bac0bee0a`, pinned local ONNX.
Веса не входят в пакет/repository; ordinary query их не скачивает и не загружает.
Host-only opt-in полный permutation допущенных окон, без новых lexical правил,
threshold, top-k или text truncation. Source checks/authority/budget сохранены.

## Зафиксированный результат, не исправленный PASS

- Pilot P03/E01,4 public calls: оба unchanged full-witness критерии FAIL.
- E01 список шести filenames поднят137→1 и доставлен; continuation не доставлен.
- P03 example опущен74→106, не доставлен; основное правило присутствует.
- Integrity/budget/read-only4/4 PASS; paired pools equal2/2.
- Full V40 paired reranker comparison НЕ исполнялся после pilot gate FAIL.
- Semantic sufficiency и answer correctness не установлены.

Первичные receipts и интерпретация:
`reports/docatlas-grounded-20261013/learned-order/RESULT_RU.md`.

## До возможного включения по умолчанию

- [ ] Отдельно утвердить новый bounded full-comparison protocol: прошлый full
      manifest был conditional и не исполнялся. Не менять его gate задним числом.
- [ ] Native versus learned: одинаковый admitted pool и полный финальный DTO cap,
      исходные40 вопросы/gold без изменений, отдельный учёт времени/model batches.
- [ ] Проверить потери любого прежде доставленного documented claim, а не только
      aggregate PASS или успех E01. Negative/partial оставить отдельными метриками.
- [ ] Проверить реальные публичные ошибки host callback/invalid permutation,
      oversized model inputs, отсутствие silent fallback и authority escalation.
- [ ] Проверить installed stdio/client путь; in-process PASS не переносить на него.
- [ ] Проверить на независимом holdout без training/tuning на exposed V40.

Это список будущих проверок, НЕ разрешение повторять benchmark сейчас.
При неуспехе не компенсировать ручными boosts/соседством/порогами и не снимать cap.
Large sufficiency model не подключена; диагностический observer остаётся отдельным
отключённым host hook. Reranker не является классификатором достаточности.

# P1: результат и решения владельца

**P1 DONE / APPROVED FREEZE; scope уточнён владельцем. P2 ACTIVE.**
Текущий language contract: [вопрос на языке документации](P1_SAME_LANGUAGE_AMENDMENT_RU.md).
Исходные hashed approval/review/corpus остаются v1 evidence; поправка меняет
обязательные language lanes, не их bytes и не результаты тестов.
Владелец явно подтвердил пакет: **«Да, утвердить и закрыть».**
Решения и границы: [P1_APPROVAL_RU.md](P1_APPROVAL_RU.md).
Текущая запись: `archives/p1-approved-freeze-manifest.json`.
P0 archival gap принят отдельным долгом; P0 не объявлен green.

## Сделано

- [Контракт](P1_CONTRACT_RU.md): RU/EN fact delivery, partial context, honest
  original/lookup attribution, scope/freshness/provenance, budgets, hostile/offline,
  сохранение existing typed-proof positives и release thresholds.
- 224 cases / 28 families / 8 lanes; 88 development и 136 held-out-family cases.
  176 primary spans; explicit forbidden relations и actual fixture metadata faults.
- Independent review сначала нашёл R1–R5; они исправлены и повторно проверены.
  [Review v2](P1_INDEPENDENT_REVIEW_V2_RU.md): REVIEW PASSED для reference pin,
  9/9 corruption probes rejected. Это не runtime acceptance.
- Bytes зафиксированы в `archives/p1-development-reference-v1.json` и
  `archives/p1-holdout-reference-v1.json`; hashes, reviewer и dependencies в
  `archives/p1-reviewed-reference-manifest.json`. Pin runner отказывается
  перезаписывать существующий reference другими bytes.
- Все 159 старых assertions перенесены в `archives/p1-test-migration-ledger.json`
  с individual IDs; NO CHANGE / NOT AUTHORIZED. Точный replacement mapping и
  evidence добавляются перед конкретной миграцией, не выдаются за сделанные.

Holdout не blind и не source-disjoint: quantum negative намеренно использует
development Pebble source. Это проверка distinct obligations, не независимая
оценка unseen generalization. Existing real Pebble/Pydantic/trust/typed-proof
и release controls обязательны отдельно; synthetic cases их не заменяют.

## Утверждено владельцем

1. Behavior contract и TD01–TD06 proposals. Особенно TD03: существующая number
   normalization — временная pending dependency, новые таблицы запрещены;
   TD06 explicit scope DTO — отдельное согласование до удаления inference.
2. TM process, **не blanket permission удалить 159 asserts**. Coverage metric и
   README hash — отдельные approvals после evidence.
3. Reviewed snapshot как approved freeze и разрешение оставить archival
   P0 gap отдельным долгом (явный waiver только prerequisite, не сам P0 DONE).
4. $0 внешних API, 0 внешних replacement request calls; дополнительное storage
   ≤2 GiB; delta p95 warm ≤1 с / cold ≤5 с к baseline на том же окружении.
   Текущие output/search budgets не увеличиваются. Actual config/serializer/
   tokenizer и measurement protocol pin — перед execution.

P1 закрыт, P2 entry готов. Исторические PENDING внутри hashed review/reference
superseded approval manifest, их bytes не переписываются. Product implementation,
downloads, existing test/gold edits, commit/push/merge здесь не выполнялись.

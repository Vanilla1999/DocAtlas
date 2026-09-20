# PR #194 — финальный TDD/question gate

Дата: 2026-09-19  
Gate: Actions run `35448191809`, artifact `10585477554`  
Artifact SHA-256: `105c6a30dec7bae396019c0b9469be302c7ec83e7a991fd67fb805393f13206e`

## Итог

План завершён в его заданных границах: структурный defect-fix принят; reader-view не прошёл независимый rollout gate и остаётся eval-only; после финальных contract/refactor изменений выполнен отдельный вопросный regression gate без новых production tuning rules.

### Deterministic gate

- **215 passed**
- `compileall`: success
- публичный лимит не расширялся: <=800 admission tokens, <=3 sources.

### Targeted V13/V15 — 30 вопросов

Текущий runtime дал те же visible packets, что и post-structural reference `f1113045...`: **0/30 packet changes**.

Ручная source-sufficiency оценка: **27/30 sufficient**. Остались:
- `DR30-12` — truncated vs insufficient evidence: безопасного сравнительного evidence нет;
- `DR30-26` — packet формально `ok`/covered, но видимый текст не содержит прямого правила «comparison alone does not trigger a split before the first packet», поэтому coverage metadata не принимается за semantic answer score;
- `DR30-30` — вместо stop-policy виден нерелевантный retrieval configuration fragment.

То есть V13/V15 остаются исправленными, но набор не объявляется 30/30.

### Generic30

На exact frozen corpus относительно принятого retrieval reference `8cecc0e...` технически изменились только 5 из 60 visible packets:

| Case | Lane | Семантика |
|---|---|---|
| G03 | root | miss -> miss |
| G17 | lookup | sufficient -> sufficient |
| G22 | lookup | miss -> miss |
| G28 | lookup | sufficient -> sufficient |
| G29 | lookup | sufficient -> sufficient |

Итоговая ручная рубрика не изменилась:
- root-only: **9 sufficient / 2 partial / 19 miss**;
- с project-blind lookups: **21 sufficient / 3 partial / 6 miss**.

Относительно принятого reference: **0 semantic wins / 0 semantic losses**. G17 стал тяжелее по пакету (580 -> 757 tokens), но остался ниже 800 и сохраняет достаточный authority witness; это записано как cost noise, а не как quality gain.

### external80

На том же frozen fixture:
- within-budget answerable: 48;
- sufficient: **31/48 -> 31/48**;
- wins: **0**;
- losses: **0**;
- changed A-current payload IDs: **0**;
- source-integrity/contract violations: **0**;
- safety errors: **0 -> 0**;
- A-current token p50/p95: **404 / 797**.

Это регрессионное подтверждение, а не новый claim об общем качестве.

### Reader-view

Новый inference не запускался намеренно. Независимая validation уже была открыта и не прошла rollout gate; повторять/подкручивать candidate после результата запрещено исходным планом. Финальные renderer contract fixes сохраняют **180/180** frozen renderings побайтно.

Decision остаётся: **`presentation_not_supported_for_product_rollout`**. Public MCP DTO/host rendering не меняются.

## Repository-wide CI

Dedicated final question gate зелёный. Обычный CI репозитория остаётся красным на историческом долге; в текущем Python 3.12 core run наблюдается **22 failed / 4103 passed / 10 skipped / 622 deselected**. Static contract по-прежнему падает на старом `_project_docs_service_part03.py` (1147 строк). Это не скрывается и не выдаётся за global-green состояние.

## Финальный статус

`structural_fix_validated_reader_view_rejected_question_regressions_passed`

Временный question-gate workflow после сохранения этого результата удаляется из итогового дерева PR. Merge в `main` этим циклом не выполняется.

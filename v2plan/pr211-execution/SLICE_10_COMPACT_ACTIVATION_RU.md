# PR211: активация compact после сравнения в CI

На `2199002b96253fdaa538515056969713876993a6` обе baseline прошли без FAIL/ERROR/SKIP: historical — 702, compact — 82. Все 51 production mutants обнаружены обоими наборами: 102 отдельных mutation runs с точными ожидаемыми assertion guards. Root независимо сверил raw JUnit, rosters, SHA изменённых модулей, фактические импорты в том же pytest процессе и отсутствие ошибок.

[CI run 37963786931](https://github.com/Vanilla1999/DocAtlas/actions/runs/37963786931), artifact `11631624539`, ZIP SHA256 `eafd9b4d52616e713d7fcb1492ac257b152f85d8ad79761c9549db0a8173f3b4`. Полная сверка в [LITERAL_REDUCTION_EVIDENCE.json](LITERAL_REDUCTION_EVIDENCE.json).

По принятому плану default case mode теперь compact: 33 span + 49 compiler cases вместо 303 + 399. Все 24 test functions сохранены; historical 702 доступен через `DOCATLAS_LITERAL_CONTRACT_MODE=historical`. Comparison runner явно задаёт оба режима, поэтому смена default сохраняет исполнение исторической baseline.

Измерение на этом runner: baseline process wall time 0.969 → 0.602 секунды; JUnit testcase time 0.014 → 0.009 секунды. Это узкое измерение двух семей. Частота полного mutation comparison пока не меняется; source/security/transaction families сохранены.

После этой активации обязательный core должен подтвердить 82 реальных исполнения на новом SHA. Остальные core/downstream failures остаются самостоятельными блокерами merge.

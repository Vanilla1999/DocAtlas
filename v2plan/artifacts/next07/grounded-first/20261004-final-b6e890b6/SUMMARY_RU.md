# BLOCKED: технически invalid I.4 wiring

- Branch: `next07-feasibility-audit`.
- Baseline/candidate: `b6e890b615fcb3ad0745510648ae2d2584878bd5` + полный
  `baseline.patch`. Предсуществующая dirty работа сохранена.
- 53 PASS: проверены JUnit (53 tests, 0 failures) и input hashes в
  `../read-repair-JYWxAH/`; повторного run не было. Exit 0 подтверждён прежним
  tool execution, отдельного machine-readable exit record нет.
- Реализован research prototype: scoped facade/imported projection caller,
  prepared inventory→unchanged proposals→real catalog DTO→whole-span read decision
  и first-fit whole-DTO packing. **Canary/public acceptance не пройдены**;
  замена competing selectors не доказана. Production не менялась.
- Candidate, splitter, FTS и read guards byte-identical: `integrity.json`.
- G: не повторялся; используется прежнее evidence, новый integrity audit G в
  этом замере не выполнен.
- Первый invalid run (`0/`, `1/`): MCP C вернул TypeError до projection.
  Исправлена dataclass conversion. Подробный traceback handler не вернул.
- Единственный retry (`retry/0/`): MCP C вернул AttributeError до projection.
  Точный источник не установлен. Scoped replacements восстановлены.
  Это незавершённая наша интеграция, не содержательный algorithm failure и не
  доказательство выхода за allowed scope.
- C P1/P2/P3: snippets отсутствуют; P1 NOT_REACHED, P2/P3 NOT_RUN в retry.
- C whole-DTO cost: NOT_MEASURED; 0 sources error packet не является admission.
- Final validator: NOT_REACHED; projection attempts пусты.
- P1–P5/N1–N10: public acceptance NOT_RUN; controls frozen в protocol.
- Fresh retained/lost/gained IDs: NOT_RUN, множества не вычислялись.
- Historical 49 / partial facts: NOT_RUN, preservation не подтверждена.
- Focused/gates/full: NOT_RUN — нет валидного C, retry-limit исчерпан.
- Предсуществующие failures 06 не измерялись заново и не исправлялись.
- Новые failures: две технически invalid integration attempts, не новые
  regression-test failures; содержательного candidate verdict нет.
- I.4 BLOCKED; I.5 NOT_RUN; I.6 итог текущей попытки BLOCKED.
- Часть II NOT_RUN. Rollout **NOT_AUTHORIZED**.

Retry argv: `.venv/bin/python -m v2plan.next07_grounded_final_run --out
v2plan/artifacts/next07/grounded-first/20261004-final-b6e890b6/retry`.
Environment: `DOCATLAS_OFFLINE=1` (runner). Process exit 0 означает запись
результата, не PASS: verdict `BLOCKED_INVALID`. Stdout отражён в `retry/result.json`.
Первый run был inline Python; отдельный script/command log не сохранён.
Packets и traces сохранены; этот недостаток provenance не скрывается.

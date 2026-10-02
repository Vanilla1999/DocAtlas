# M2: общий bounded read-context admission

## Изменение

`docmancer/docs/application/read_context_admission.py` вводит общий pure
контракт для prefit и final projection. Он не добавляет generated query/need rows
или aliases в planner, не создаёт coverage или semantic witnesses и не выполняет
source I/O.

Ранкер сохраняет дополнительный candidate только после проверки допустимого
visible window этим контрактом. При пустом answer packet projector повторяет
те же проверки на финальных clipped bytes после существующего typed fallback.
Это отдельный read-only маршрут, не снятие всех qualification veto.

Проверяются исходный question/reference plan, project identity, hash полного
prepared source, точное совпадение visible char span с source bytes, текущие
source/reference guards, explicit literals/subjects, security flags и lifecycle.
Исключение разрешено только для lexical qualification outcome
`insufficient_visible_match`/`visible_fields`; остальные причины fail closed.
Существующая интерпретация constraint spans используется только как veto:
неизвестные условия не открывают маршрут и не порождают retrieval probes.

Независимый критерий context relevance намеренно консервативен: минимум три
различных original-query body terms в одном substantive sentence, включая
adjacent lexical pair из original question. Heading/path-only, разнесённые
terms и question echo не дают локальный witness. Это новый ограниченный
context-locality policy, не универсальное semantic relevance решение. Глобальные
qualification ratios не меняются; подход не гарантирует delivery любых
paraphrases или cross-language questions.

Finite alternatives остаются ограниченными: 24 candidates, 16 windows на
candidate, 640 chars; полная стоимость DTO проверяется в прежнем token budget.
Финальный дополнительный fallback доставляет один source без qualified query
IDs и без присвоения public coverage. Candidate без stable chunk identity не
может получить prefit exemption через совпадение `None`.

## Проверки

- Новые boundary controls: **23 passed** — Unicode original, missing exact
  identity/condition, snapshot/source identity forgery, stale/index/lifecycle,
  risk/instruction flags, clipping, tiny budget, heading/setext/echo/scattered
  terms, отсутствие answer/edit escalation.
- Новый набор вместе с ranking/anchor controls: **54 passed**.
- Module-budget/structural controls вместе с новым набором: **44 passed**.
- Дополнительные reference/admission/query-block/completion checks:
  **126 passed / 3 failed**; все три failing IDs уже присутствуют в stable
  baseline. Это не зелёный safety suite.
- Последний полный `tests/docs`: **3382 passed / 104 failed**.
  Новых failing IDs относительно `m2_cross_stage_stable_docs.log` нет.
  Восстановлены четыре теста: native partial delivery pydantic/ruff и два
  corresponding need-composition controls. Новых parameterized cases — 23.

Native captures: `m2_read_context_admission_native.json`.
На исходных requests required facts для `httpx-07`, `pydantic-07`, `ruff-07`
supported по evaluator, при этом `answer_supported=False`, `edit_ready=False`.
Для `mkdocs-05` required fact остаётся missing: discovery cap здесь не изменён.

Полный log: `m2_read_context_admission_docs.log`.
Промежуточные превышения module-size budget устранены без изменения лимита;
итоговый полный прогон выполнен после исправления.

## Статус

Общий prefit/read-context boundary исправлен для подтверждённой lexical-local
группы. Не менялись regression questions, corpus fixtures, acceptance assertions,
generated inference planner или qualification thresholds. M2 остаётся открытым:
104 failures требуют дальнейшей классификации, отдельная discovery-loss группа
не устранена. M3/M4 не объявляются завершёнными. Commit/push/merge не выполнялись.

# PR211: fidelity полного insufficient DTO вместо terminal display cap

Дата: 2026-10-08. База: `3be9c34afa49dcf4278d2910ec29ed37c305225c`.
Scope: только существующий parametrized test `test_oversized_insufficient_projection_uses_a_valid_terminal_fallback` в `tests/docs/test_model_visible_projection.py`. Runtime нового slice **NOT RUN**; требуется independent review и совместный CI.

## Классификация границы

Этот test передаёт уже сформированный model-visible DTO в `bound_insufficient_projection`. Здесь нет источников для acquisition, поискового запроса, directory scan, работы provider, admission или дополнительного read. Current producer (`model_visible_projection.py:511`) обновляет только `estimated_tokens`, явно сохраняя accepted recovery data. Его внутренний estimate refresh остаётся с прежними тремя итерациями; никаких work bounds не меняется.

Прежние ожидания `estimate <= budget` и удаления `missing_requirement_ids` требовали потери готовых diagnostics ради representation size. Это не security/read/work limit. Разрешение на отдельную cap-test migration с fidelity controls дано в `V4_PRODUCT_DECISIONS_RU.md`, этап 1, и `NEXT_PARALLEL_IMPLEMENTATION_PROMPT_RU.md`, общий принцип и раздел B. Правило не переносится на frozen retrieval acceptance 800, source/work bounds или другие CI gates.

Полный DTO и его валидатор уже работают по текущему контракту; production не изменён. Не заменяется expectation новым наблюдаемым числом 7650 или увеличенным ceiling. Параметр `max_tokens=budget` по-прежнему передаётся **обоим** исходным calls.

## Что изменено

Сохранены четыре исходных parameter values и concrete node IDs: **256 / 300 / 1500 / 2000**. Историческое имя node оставлено ради неизменного roster; его successor проверяет fidelity, а не terminal truncation.

Все прежние payload values сохранены: большой missing text, большой action observation, 100 requirement IDs, qualification/selection/assignment/decision hashes и исходные status/kind/answer flags. Добавлены только явные guard sentinels: false edit/documentation authority, true hard_stop и confirmation, action confirmation reason и auto_execute=false. Это проверяемые состояния готового DTO, а не новые runtime grants или semantic claims.

Перед вызовом создаётся независимая `deepcopy` input. После вызова весь payload обязан совпасть с input, кроме единственного служебного `estimated_tokens`, который обязан соответствовать текущему измерению. Это обнаруживает удаление/усечение/замену missing data, любого из 100 requirement IDs, qualification hashes или action observations, а также добавление неожиданных полей. Пустой либо минимальный fallback не проходит.

Дополнительно явно сохраняются:

- Полные missing list, missing_requirement_ids и recommended action.
- `answer_supported is answer_available is False` и `edit_ready is documentation_supported is False`.
- `hard_stop is requires_confirmation is True`, action confirmation true и auto_execute false. Identity assertions различают bool и числовые 0/1, чего одной dict equality недостаточно.
- Прежнее отсутствие `support_envelope`; при исходном direct DTO не появляется opaque substitute.
- Прежний `validate_model_visible_projection(payload, snapshot={}, max_tokens=budget) == []`, без замены на более высокий бюджет или отключение валидатора.

Условие `measured_tokens > budget` доказывает, что эти же четыре cases действительно покрывают результат больше прежних display budgets. Оно не вводит новый output ceiling. Уже исходный missing text содержит 14 000 ASCII characters; это не пустой и не подобранный под фактический ответ positive.

## Контрпримеры и сохранённая validation boundary

Внутри каждого из тех же четырёх nodes добавлены восемь targeted mutations готового valid DTO: invalid kind, invalid status, answer_supported=true, answer_available=true, support_status=ok, edit_ready=true, непустая implementation guidance и forbidden internal diagnostics. Каждый вариант требует **свой конкретный error label**, а не произвольный непустой errors list. После изменения value обновляется estimated_tokens, чтобы проверять смысловой guard, а не использовать stale estimate как причину отказа.

Таким образом, отмена representation cap не отключает format, disclosure или fail-closed authority validation. Это **32 authored negative iterations**, не новые test nodes и не утверждение о выполненном runtime PASS.

Qualification в этом slice означает сохранение уже переданных requirement/eligibility/candidate/selection/assignment/decision bindings. Он не выдаёт fabricated canonical evidence и не объявляет input hashes независимым semantic proof; реальная qualification/admission и snapshot validators остаются в неизменённых соседних tests/production.

## Статическая проверка и границы

- Current file SHA256: **`ccc0958f996d3ecd74a6429bfda643eb0388d5799edcccbf2205f23414608cf7`**.
- Baseline file SHA256: `4a020909a6e8d84bc9659b25cdd26228672a32a5b1f413a0284e9ef81d82bab0`.
- Production `docmancer/docs/application/model_visible_projection.py` unchanged: `f78f41fb46f3ff57222b3e95837024fc36dbe82100d14fee89c56785e89a271a`.

Read-only Git/stdlib AST comparison подтверждает неизменные function signature и parameter decorator, **31 прочую test function** и **38 остальных module nodes**. Prefix и suffix вне единственного изменённого function body побайтно прежние. В исходном test было четыре assertions: две representation-loss assertions получили fidelity successors, две исходные non-cap assertions сохранены AST-exact. Новый body содержит 13 Assert nodes, включая targeted negative loop.

`git diff --check` чист. Не менялись imports, shared helper, соседние cap tests, tests inventory, production, retrieval, schema, corpus/gold, thresholds, CI selectors, skip/xfail. Удаление/изменение других caps этим slice не обосновывается. Production imports, pytest, provider/client/server runs локально не выполнялись.

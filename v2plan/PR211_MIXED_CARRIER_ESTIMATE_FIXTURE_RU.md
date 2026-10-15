# PR #211: подготовка detached class-carrier controls

## Фактический первый отказ на 113

Проверяемая ветка: `441cdefd2b251d63f716bfa75b053413bbe09c76`.
CI использовал merge checkout `ceea2571e9847a71515feda4e1e1441fafdede44`.

[Main CI](https://github.com/Vanilla1999/DocAtlas/actions/runs/38017123447)
и [acceptance reader](https://github.com/Vanilla1999/DocAtlas/actions/runs/38017123447/job/114111640263)
зафиксировали critical baseline: **53 PASS / 1 FAIL**.
Первый guard единственного mixed test — `critical_mixed_class_control_healthy`,
control `metadata_only`, исходная строка 463. До него выполнены существующие
четыре native чтения и 28 detached replay controls. Class-carrier loop остановился
на первом healthy input; оставшиеся class controls и следующий collision control
этот прогон не подтвердил. Directed mutation proof без зелёного baseline не выдан.

Это отдельная проверка от [P1.5 quality job](https://github.com/Vanilla1999/DocAtlas/actions/runs/38017123532/job/114109779239):
там фактически PASS 7/7, full facts 6/6 и oracle controls 6/6.
Успех P1.5 не заменяет critical proof.

## Причина по текущим исходникам

1. `observe_composition` сохраняет deepcopy аргументов **до** вызова настоящего
   `retain_mixed_project_context` (test, строки 108–111).
2. `project_docs_answer` создаёт payload с `estimated_tokens=0`, передаёт его
   helper и вызывает финальный `_refresh_estimate` только после возврата helper
   (model_visible_projection `3c377e64bf104b598bb68a0d062625c4fc83f5ef`,
   строки 438–462).
3. Настоящий helper сначала копирует этот payload и пересчитывает оценку,
   затем валидирует копию (mixed_context_projection
   `0007dbe25be2b629661fa82be4101858910f495d`, строки 175–178).
4. Новый carrier loop валидировал сохранённый вход напрямую, до этого пересчёта.
   Validator добавляет `projection estimate mismatch`, если оценка не равна
   вычисленной; `estimate_projection_tokens` возвращает минимум 1
   (model_visible_projection, строки 667–669;
   model_visible_projection_helpers `7518c6d44ac30368a4e9005e6f456d0af5300547`,
   строки 201–203).

Actual reader сообщает имя guard и label, но прежний detail не содержал списка
ошибок validator. Конкретный estimate mismatch установлен по порядку вызовов и
явным значениям в исходниках; он не выдается за уже напечатанный runtime detail.
Существующий collision control уже готовит такой пакет через
`_refresh_estimate` перед healthy validation.

## Узкая правка

В каждом из прежних 15 class-carrier controls пересчитывается только
`carrier["payload"]["estimated_tokens"]` перед тем же healthy guard.
Guard теперь включает `validation_errors` в диагностический detail.

Полезные bytes, SQL child identity, generation, hash, raw/UTF-8 spans,
exact version, module/root binding, исходные вопросы и ожидаемые source facts
сохранены. Все 15 вариантов class carriers и их положительные/отрицательные
ожидания остаются прежними. Production helper и validator не меняются.

Одна существующая test function, четыре native чтения, 28 replay controls,
15 carrier controls и collision control остаются тем же составом.
Это исправление подготовки внутри функции; оно не сокращает число её итераций
и не добавляет retrieval, HTTP, SQLite calls или новых обычных тестов.
Critical runner и его directed faults не изменены.

## Manifest и проверка

| Путь | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| tests/docs/test_mixed_context_projection_contract.py | 99f4543092c3af0323bb511faba23c464fa95260 | a6119106b1971ffd5d2097db19d708b40572abef | 100644 |
| v2plan/PR211_MIXED_CARRIER_ESTIMATE_FIXTURE_RU.md | новый файл | этот документ | 100644 |

Единственный code hunk заменяет две строки на семь. Обратная замена
восстанавливает исходный файл побайтно; полный test roster и diagnostic shard
не меняются. Проверка выполнена чтением исходников и exact GitHub blobs,
без локального исполнения.

На базе 113 состав critical runner — **54 cases / 27 mutations**; этот срез
его не меняет. Для следующего общего пакета отдельно запланировано
**54 cases / 29 mutations**. Повторный critical gate остаётся **PENDING**
до CI на конечном опубликованном SHA; эта правка не заявляет новый PASS.

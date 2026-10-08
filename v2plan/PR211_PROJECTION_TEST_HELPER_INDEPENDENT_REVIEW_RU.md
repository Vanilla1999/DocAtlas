# PR211: независимый review переноса fidelity test body

Дата: 2026-10-08. Base `4320a6841cb5a04b3c817c4f61595987c11d8f7c`.
**Вердикт: APPROVE** для следующих bytes:

- `tests/docs/test_model_visible_projection.py`: SHA-256
  `88d2ae9f6669b68e0600c7d5d9ef88385744477878f68ec940589bdfa2073db8`.
- `tests/docs/_shared_test_model_visible_projection.py`: SHA-256
  `48f20039b6b2c8630a892469d240b3b0d9fdabdd94dd535a5abe6ad999d5a6bb`.

Независимо прочитаны полный diff, авторский
`PR211_PROJECTION_TEST_HELPER_REVIEW_RU.md`, существующий shared import mechanism
и module-size gate. Исправление сохраняет прежний предел 1000 строк: основной
test module сокращён с 1039 до 974, существующий shared module вырос с 77 до 146.
Новый module, framework или collection selector не вводится.

Stdlib AST сравнение против base подтвердило полное равенство перенесённого body:
последовательность `ast.dump` без locations имеет SHA-256
`67e0e170a35a5c260d1cde2f981caf04188b345b3cfc0dd1987864abbbc44ae8`.
Сохранены все 13 Assert nodes, исходный большой payload, deepcopy-before-call,
exact DTO fidelity, bool identity guards, восемь invalid variants и настоящие
producer/estimator/validator calls. Нет пропущенных assertions или новых
условий, способных обходить их.

Исходная test function остаётся на прежнем пути с прежним именем, аргументом
`budget` и decorator `[256, 300, 1500, 2000]`; её единственный statement —
безусловный вызов helper с тем же `budget`. Остальные AST nodes основного
module совпадают. Все старые AST nodes shared module совпадают, а прежний
файл сохранён побайтным prefix. Новая функция начинается с `_assert_`, поэтому
не является test node. Существующий `globals().update` исключает только
double-underscore names и корректно предоставляет этот helper wrapper.

В новом helper ровно четыре внешних имени помимо builtin `range`:
`deepcopy`, `bound_insufficient_projection`, `estimate_projection_tokens`,
`validate_model_visible_projection`. Все они уже импортировались в этот shared
module; прежний test получал те же function objects через globals update.
У перенесённого test нет monkeypatch fixture или локального override этих имён;
поиск test references не обнаружил patch именно этих bindings. Следовательно,
перенос не подменяет production вызовы и не создаёт зависимость от другого
test setup. Fixture scope/parametrization и диагностический roster не меняются.

Независимый stdlib scan с прочитанными ignored paths существующего gate охватил
1257 Python files: превышений 1000 нет, максимум 995 строк. Сам repository gate
не импортировался и не исполнялся. `git diff --check` чист. Product code,
thresholds, test selectors, skips, xfails и diagnostic manifests не менялись.

Это исправление новой module-size regression, а не waiver. Actual pytest,
collection, installed/client/server/provider runtime и новый CI здесь
**NOT RUN**. Нужен обычный CI опубликованного follow-up SHA; результаты run
`37829365750` относятся только к предыдущему `4320a684` и не переносятся на него.

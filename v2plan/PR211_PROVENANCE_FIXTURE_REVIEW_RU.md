# PR #211: migration вызова в отрицательном provenance control

База: `03583656617336a746e9192249467017d6131f29`. Узкий test-only slice,
без изменений production, retrieval, budgets, gold или CI selectors.

Изменён ровно один вызов в существующем node:
`tests/docs/test_evidence_selection_part02.py::test_evaluator_only_requirement_provenance_is_rejected`.

```diff
-            config=patch_selection_config(1500),
+            config=patch_selection_config(),
```

Текущий контракт обоснован source: `_evidence_selection_part01.py:453`
объявляет `patch_selection_config()` без аргументов; V4 patch selection сохраняет
целые admitted windows и не принимает representation budget. Проверяемый здесь
контракт — отказ принимать evaluator-only provenance, а не fitting по 1500 tokens.
`evidence_requirements.py:287–301` проверяет явно переданное
`public_provenance` по allowlist и бросает `ValueError` при
`hidden_test_answer`; `select_evidence` строит эти requirements до selection и
имеет дополнительную проверку provenance в `_evidence_selection_part03.py:73–79`.

| Старый guard | После migration |
| --- | --- |
| `pytest.raises(ValueError, match="unsupported evidence requirement provenance")` | Тот же AST и точный message matcher |
| `public_provenance="hidden_test_answer"` | Тот же отрицательный input |
| `text="hidden fact"`, authored candidate и question | Без изменений |
| Ошибка подготовки ABI `TypeError` | Убрана только передача запрещённого positional argument; `TypeError` по-прежнему не удовлетворяет `pytest.raises(ValueError)` |

Никаких catch/skip/xfail, broad exception match, новых pass expectations или
подмены provenance не добавлено. Остальные ABI/semantic failures этого файла
сохранены для отдельного contract review.

Статическая проверка stdlib AST: изменена только эта функция. Обратное удаление
единственного `Constant(1500)` из старого call даёт AST, полностью равный новому
module AST. Все 29 base test IDs, decorators, остальные тела и все 82 `assert`
сохранены. AST контекстного `pytest.raises` guard имеет SHA256
`8550ee70b7ec356e8f828642a095cb2fe4a3f492df743835b1e9ad6b8eb3c956`.
Diagnostic module inventory совпадает с существующим manifest:
`49a9a1d17f9107ce44dfb616be86e6c5dcb6200a6ad42c48096fd04cd39bd566`.

SHA256 test file до: `28279b66d83980b355cdb62b49a8ce29e2b1b5d4bb9fa8ccbda79840964dc5ea`.
После: `ffec1c6d0b0827aab9c1e88e3aea20530ebac49441ecf90c8bb5680a93f89601`.

`git diff --check` PASS. Локальные runtime/import/pytest/provider проверки и
установки не выполнялись. Это source-grounded migration, не утверждение runtime
PASS; после независимого review требуется обычный CI на опубликованном SHA.

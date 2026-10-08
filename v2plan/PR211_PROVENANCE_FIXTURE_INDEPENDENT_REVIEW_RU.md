# PR211: независимый review provenance fixture

Дата: 2026-10-08. Base `03583656617336a746e9192249467017d6131f29`.
Вердикт: **APPROVE** для `tests/docs/test_evidence_selection_part02.py`,
SHA256 `ffec1c6d0b0827aab9c1e88e3aea20530ebac49441ecf90c8bb5680a93f89601`.

Root независимо прочитал полный diff, исходный test, current config factory,
построение requirements и явный provenance reject в selector. Проверяется отказ
при `hidden_test_answer`, а не размер ответа. Текущая factory не принимает
representation budget; её вызов без аргумента соответствует разрешённому V4
контракту. Никакой runtime лимит или provenance allowlist не меняется.

Stdlib AST comparison подтвердил: удалён только `Constant(1500)` из единственного
`patch_selection_config` call этого test. Все остальные AST nodes, 29 test IDs,
decorators, candidate, question и `public_requirements` полностью совпадают.
В частности, `pytest.raises(ValueError, match="unsupported evidence requirement
provenance")` сохранён: другой exception, включая TypeError подготовки, не может
дать ложный PASS. Production requirements builder отклоняет этот явно запрещённый
provenance до selection, а selector дополнительно проверяет allowlist.

Статическая compile-проверка прошла без исполнения repository code. Runtime
результат пока **NOT RUN**; его должен подтвердить обычный CI опубликованного SHA.
Другие ABI/authority/display-cap conflicts файла этот review не разрешает менять.

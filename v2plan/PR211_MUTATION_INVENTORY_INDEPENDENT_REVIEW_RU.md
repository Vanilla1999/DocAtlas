# PR #211: независимый review diagnostic inventory mutation slice

Дата: 2026-10-08. Reviewer: `membership_fixtures`.
База сравнения: `df9b682fdd13d8f4d1c5bff6cc4bfc0286e5f8ce`.

**Вердикт: APPROVE.** Однострочное изменение inventory необходимо для двух
ранее проверенных integrity tests. Оно сохраняет действующий fail-closed
collection gate, labels и все остальные entries.

## Проверенный контракт

Прочитаны [`tests/diagnostic_labels.py`](../tests/diagnostic_labels.py) и
collection hook в [`tests/conftest.py`](../tests/conftest.py). Для каждого
полного module hook проверяет множество уникальных base node IDs: часть
`item.nodeid` до первого `[`. Digest вычисляется как
`sha256("\n".join(sorted(nodeids)).encode()).hexdigest()`.

Параметризованный test поэтому даёт один base node, а не отдельную hash entry
на каждый runtime variant. Количество исполненных concrete cases при этом
не уменьшается. Новый helper `_fixture_member_transaction.py` не является
collectable test module и не требует новой module label.

## Самостоятельно воспроизведённые hashes

| Версия | Unique base nodes | Inventory SHA256 |
|---|---:|---|
| Исходный `df9b682f` | 18 | `eaff9513762bd40ad6e4ac82de43d8682344b3916383813aadaf84853389ca76` |
| Reviewed source + два новых integrity tests | 20 | `893160586869bb120062a243c879b0a6c140243940eded52f6c9f0a729a22dd5` |

Старый hash независимо вычислен из исходного AST, полученного через
`git show df9b682f:tests/test_named_document_context_integration.py`, и из
21 фактического case в сохранённом `df9b682-core-3.12-cases.json`.
После удаления parameter suffix JUnit даёт ровно те же 18 base IDs.
Оба пути совпадают с исходной manifest entry.

Новый AST даёт те же 18 base nodes и ровно два добавленных:

- `tests/test_named_document_context_integration.py::test_named_document_fixture_requires_confirmed_hash_bound_members`
- `tests/test_named_document_context_integration.py::test_named_document_fixture_cas_preserves_unselected_source`

Удалённых nodes нет. Оба новых tests без parameter decorators. Новый digest
совпадает с обновлённой manifest entry. Реальный новый pytest collection ещё
должен выполниться в обычном CI; статический расчёт не объявлен его заменой.

## Ограничение diff

Проверен exact diff `tests/diagnostic_labels.json` и полное JSON-сравнение с
исходным manifest. Единственное изменение:

`module_node_hashes["tests/test_named_document_context_integration.py"]`.

Дополнительно проверено byte equality: замена одного старого 64-символьного
hash token новым даёт рабочий файл целиком. Следовательно, нет format churn,
изменённых labels, node overrides, schema_version или других hashes.
Все 259 module hash entries сохранены; label данного module — `behavioral`.
Collection validator, selectors и обязательные gates не менялись.

| Артефакт | SHA256 |
|---|---|
| Исходный `tests/diagnostic_labels.json` | `d60e88fa240673fb047e1a909beb64b7ed425a7e0f37c7e9b40a0adedb9e4793` |
| Новый `tests/diagnostic_labels.json` | `1ecf68c4c385a5d26c2b9d651e56a10e3ede2e548d49ba1c9cbbe1f56dcf3a00` |
| Author inventory review | `a74be26399646f3f08ad0279d191371871cf8cdbc93b5e3b484ab74c036ee594` |

Ранее одобренные implementation files повторно проверены по hashes и неизменны:

- `tests/_fixture_member_transaction.py`:
  `87260abcf397eb4493d62e50a9d043942e185a905a4156287a705a5c36fd46fe`.
- `tests/test_named_document_context_integration.py`:
  `0ecdcbdf0ed96cb76c80af3fc8c7f357ee64f9aed2fa86977b1bc6341a082f5a`.

## Проверки и предел вывода

Использованы stdlib AST/JSON/hashlib, чтение сохранённого JUnit, read-only git
diff/show и `git diff --check`. Repository imports, pytest, package installs,
runtime fixtures, providers и clients локально не запускались.

Approval подтверждает reviewed inventory двух добавленных tests и отсутствие
других изменений manifest. Оно не утверждает runtime PASS, не скрывает прежние
failures и не меняет результат [основного mutation review](PR211_MUTATION_FIXTURE_INDEPENDENT_REVIEW_RU.md).

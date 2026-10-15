# PR #211: diagnostic inventory для двух новых mutation controls

Дата: 2026-10-08. База: `df9b682fdd13d8f4d1c5bff6cc4bfc0286e5f8ce`.

## Обязательное изменение

`tests/conftest.py` вызывает `validate_diagnostic_inventory` для полных modules.
Алгоритм в `tests/diagnostic_labels.py` берёт уникальные base node IDs до первого
`[`, сортирует их и вычисляет `SHA256('\n'.join(sorted(nodeids)).encode())`.
Два новых integrity tests требуют обновить одну соответствующую hash entry.
Без этого collection намеренно отклонит непроверенный inventory.

Изменена только:

`tests/diagnostic_labels.json`
→ `module_node_hashes['tests/test_named_document_context_integration.py']`.

| Состав | Base nodes | SHA256 inventory |
|---|---:|---|
| Исходный df9b682f | 18 | `eaff9513762bd40ad6e4ac82de43d8682344b3916383813aadaf84853389ca76` |
| 18 прежних + 2 reviewed controls | 20 | `893160586869bb120062a243c879b0a6c140243940eded52f6c9f0a729a22dd5` |

Добавлены ровно следующие base IDs:

- `tests/test_named_document_context_integration.py::test_named_document_fixture_requires_confirmed_hash_bound_members`
- `tests/test_named_document_context_integration.py::test_named_document_fixture_cas_preserves_unselected_source`

## Проверка

Исходный hash независимо воспроизведён двумя stdlib путями: из AST исходного
module через `git show df9b682f:...` и из **21** фактического JUnit case в
`df9b682-core-3.12-cases.json` после deduplication parameter variants до **18**
base IDs. Оба набора и hash совпадают с прежней manifest entry.

Новый AST содержит **20** base functions; его digest равен новой entry.
Module classification остаётся `behavioral`. Все module labels, node overrides,
schema_version и прочие module hashes сохранены. Проверено полное JSON-равенство
после возврата одной entry к старому значению и byte equality после замены
одного hash token: постороннего format/map churn нет.

Ни test implementation, ни прежние approved author/independent reports здесь
не меняются. Селекторы, проверки inventory, CI gates и classification logic
остаются прежними. Runtime collection/pytest локально не выполнялись; следующий
normal CI должен выполнить настоящий collection validation.

Frozen SHA256 всего `tests/diagnostic_labels.json`:

`1ecf68c4c385a5d26c2b9d651e56a10e3ede2e548d49ba1c9cbbe1f56dcf3a00`.

Независимый reviewer должен подтвердить точный однострочный manifest diff перед
публикацией вместе с двумя уже reviewed control tests.

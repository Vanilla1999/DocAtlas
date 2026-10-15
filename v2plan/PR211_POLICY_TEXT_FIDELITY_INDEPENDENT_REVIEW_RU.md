# PR #211: independent review policy-text fidelity

2026-10-08. **APPROVE** для узкой migration одного node; runtime PASS не заявлен.
База `03583656617336a746e9192249467017d6131f29`.

Независимо сверены окончательные SHA256:

- `tests/docs/test_action_packet_semantic_density.py`:
  `61a441476a3382148ca6f0c9d120e78a774887c699f1fac9e9b837c6bbd0c0b9`.
- `v2plan/PR211_POLICY_TEXT_FIDELITY_REVIEW_RU.md`:
  `cbe80a5f1e1fe2284363c659943442c855c0c07ef8f955a6f45bb5381c88a511`.

Исходные candidate, helper, text, question, trust contract, project path и
authority metadata сохранены. AST вызова builder совпадает с базой после
удаления единственного retired `max_tokens=2000`. Новые requirements, qualifiers,
provenance/authority flags или production semantic rules не добавлены.

Замена visible container обоснована текущим контрактом. Публичный ActionPacket
facade использует V4 producer из part03, который возвращает целые admitted
`sources[].text` с SHA256 и identity, а не производные policy arrays.
`_with_canonical_policy_requirements` не создаёт obligation из нормативного
словаря. Сохранение текста здесь не требует возвращать эту inference.
Все три прежних exact sentence-containment assertions AST-identical;
полное равенство единственного source исходному display_text дополнительно
ловит потерю любого условия, перестановку или подмену текста.

Проверяются точный UTF-8 hash исходного текста, path и stable ID, data result,
instruction_trust=untrusted_data и строго edit_ready=False. Отсутствие legacy
policy containers и автоматически выведенного mutation_intent отделяет
сохранение цитаты от разрешения на изменение кода. Нормативные слова остаются
видимыми в source; они не переименованы и не удалены ради прохождения guard.
Не навязывается artificial supporting/canonical expectation: текущая authority
проверяется настоящим validator с теми же evidence_items и project_path.

Completeness не подменена разрешением на редактирование. Исходный вопрос
содержит технические identifiers; текущий selector вправе создать механические
literal assignments. Тест не удаляет их и не добавляет фиктивный obligation.
`validate_action_packet(...) == []` проверяет schema, estimate, source bindings,
assignments и действующее условие visible content assignment для complete.
Empty/failure packet не может пройти: обязательны data и ровно один source.

Независимая статическая проверка: изменена ровно указанная function, весь прочий
module AST и signature/decorators сохранены. Все три прежних Assert присутствуют
без изменения; node 3→13, module 38→48. Candidate assignment AST hash
`57fec131ebff110a69a5963559928e8fa79ef37f9f3e0d2aeb7f3926ac01ec0e`, новый node hash
`942487539a557f916dcc7403fce390e0150e26c8b5ad40cfc1e1b74d04aa708c` проверены.
Сохраняются 11 base test IDs и roster hash
`e73e5c2acb6be697456ad3c00a8bc12f404eeafb81782ba87be2d84e21235ede`, совпадающий
с неизменённым `tests/diagnostic_labels.semantic_density.json`.
Producer, selector, authority resolver, validator и schema byte-identical базе.
`ast.parse`, compile без исполнения и `git diff --check` — PASS.

Написан только этот independent report. Локальных repository imports, pytest,
runtime subprocesses, provider/client calls и installations не было. Production,
retrieval, frozen gold, work/security bounds и CI gates не изменялись.
Необходим обычный совместный CI на опубликованном SHA; открытых замечаний нет.

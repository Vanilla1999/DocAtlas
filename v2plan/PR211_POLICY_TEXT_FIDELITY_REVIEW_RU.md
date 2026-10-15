# PR #211: сохранение policy text в текущем V4 source container

База `03583656617336a746e9192249467017d6131f29`. Отдельный test-only slice
в `DocAtlas-collision-fixture`; другой файл с identity-collision migration
reviewed отдельно. Изменён ровно один существующий node:
`tests/docs/test_action_packet_semantic_density.py::test_every_safe_canonical_policy_fact_survives_packet_formatting`.

Исходный candidate, его три предложения, stable id, source path, authority,
helper metadata, вопрос, trust contract и `project_path="/repo"` не изменены.
Из `build_action_packet` удалён только retired `max_tokens=2_000`.
Текст читается из действующего `sources[].text` вместо удалённых
`required_invariants` / `forbidden_changes` / `implementation_guidance`.

Все три старых exact containment assertions сохранены без изменения AST:

- `PermissionService must own decisions.`
- `BrowserGate must delegate decisions.`
- `Do not bypass PermissionService.`

Добавлены независимые fidelity/binding guards: ровно один source, полный текст
равен исходному `display_text`, SHA256 совпадает с хешем этих UTF-8 bytes,
path и stable_id равны исходному candidate. Packet содержит data, source имеет
`instruction_trust="untrusted_data"`, `edit_ready` строго False. У packet нет
старых authorizing containers и нет автоматически выведенного `mutation_intent`.
Текущий `validate_action_packet(packet, evidence_items=[policy], project_path="/repo")`
должен вернуть пустой список; validator не заменён структурной имитацией.

Основание current contract: `_action_packet_part03.py::_candidate_source`
сериализует целый admitted display с SHA256, identity и untrusted-data trust;
`build_action_packet` не принимает representation cap и всегда оставляет
`edit_ready=False`. `_with_canonical_policy_requirements` больше не создаёт
obligation из нормативных слов. `_action_packet_part04.py::validate_action_packet`
проверяет source against bound retrieval window, hash, assignments и схему.
Так сохранён старый text-preservation смысл без приписывания prose edit authority.

Новое `public_requirements`, ручные provenance/authority flags и слова в source
не добавлены. Completeness здесь не используется как proxy для edit permission:
вопрос содержит технические identifiers, поэтому наличие assignments решается
существующим producer, а их корректность проверяет validator. У no-assignment
case selector сохраняет `visible_content_assignment_required` и partial state;
это не основание автоматически объявлять конкретный packet complete либо partial.
Тест не меняет и не обходит эту границу.

Статическая проверка stdlib AST: только указанная функция отличается от базы;
все остальные функции, decorators и module-level AST неизменны. После удаления
одного старого max_tokens keyword AST call полностью совпадает со старым.
Candidate assignment AST SHA256 неизменен:
`57fec131ebff110a69a5963559928e8fa79ef37f9f3e0d2aeb7f3926ac01ec0e`.
Все 11 base test IDs сохранены, roster SHA256
`e73e5c2acb6be697456ad3c00a8bc12f404eeafb81782ba87be2d84e21235ede`.
Этот hash совпадает с `module_node_hashes` в extension inventory
`tests/diagnostic_labels.semantic_density.json`; manifest не менялся.
В node 3 → 13 asserts, все 3 старых сохранены; module 38 → 48 asserts,
399 lines. Новый node AST SHA256
`942487539a557f916dcc7403fce390e0150e26c8b5ad40cfc1e1b74d04aa708c`.

SHA256 test file до: `f63dee723a0b3dcd0c1e6a048dd6bd2d206e9ac2fefded650227fc1b828e3f63`.
После: `61a441476a3382148ca6f0c9d120e78a774887c699f1fac9e9b837c6bbd0c0b9`.

`git diff --check` PASS. Production, retrieval, frozen corpus/gold, thresholds,
workflows и остальные tests не менялись. Локальные repo imports, runtime/pytest,
provider calls и installs не выполнялись. Это source-grounded migration;
runtime PASS должен подтвердить обычный CI после независимого review.

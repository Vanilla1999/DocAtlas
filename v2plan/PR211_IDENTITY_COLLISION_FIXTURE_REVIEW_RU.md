# PR #211: stable identity collision guard на V4 packet

База `03583656617336a746e9192249467017d6131f29`, отдельный worktree
`DocAtlas-collision-fixture`. Изменён только существующий node
`tests/docs/test_evidence_selection_part02.py::test_stable_identity_collision_fails_closed_before_action_packet_rendering`.
Одобренный provenance slice из другого worktree не включён и не изменён.

Оба старых `_candidate("same", ...)`, их разные строки preserve/disable isolation,
metadata из существующего helper и `question="Update worker"` сохранены.
У двух старых calls удалены только retired representation arguments:
`patch_selection_config(1500)` → `patch_selection_config()` и `max_tokens=1500`
у `build_action_packet`. Production, helpers, authority/provenance flags,
public requirements, gold, thresholds и retrieval не изменены.

| Guard | Текущий successor |
| --- | --- |
| Selector `status == insufficient_evidence` | Сохранён точный старый assert |
| Selector missing `stable_identity_collision:same` | Сохранён точный старый assert |
| Старый packet `status == insufficient_evidence` | V4 `result=failure`, `completeness=unavailable`, `edit_ready=False`, machine reasons collision и no_admitted_evidence, поле sources отсутствует |
| Не было положительного контроля | Две отдельные одинаковые копии первого исходного candidate; тот же question/config; выбран ровно stable_id same с исходным текстом, packet data с одним source, collision reason отсутствует, current validator возвращает пустой список |

Положительный packet не получает полноту или edit authority автоматически:
отдельно проверяются `completeness=partial`, `edit_ready=False` и
`missing` с `visible_content_assignment_required`. Никакого дополнительного
`public_requirements` не передаётся. Source text/stable_id проверяются явно;
`validate_action_packet(..., evidence_items=identical) == []` проверяет актуальную
схему, estimate и binding к тем же fixture bytes.

Основание: selector `_evidence_selection_part03.py:108–129` сравнивает полные
identity bindings, исключает обе конфликтующие строки до admission и сохраняет
`stable_identity_collision` в missing. `_evidence_selection_part02.py:147–160`
допускает exact duplicate без collision. `build_action_packet` в part03 сохраняет
выбранные целые windows и выводит failure/unavailable при отсутствии sources.
Хвост selector `_evidence_selection_part03.py:397–403` добавляет
`visible_content_assignment_required` при отсутствии unit assignment: поэтому
positive с прежним plain question имеет допустимый data/partial DTO.

Первоначальная read-only гипотеза о builder/validator conflict без explicit
requirements была исправлена после чтения этого хвоста: production bug здесь
не установлен. Validator не ослаблялся; positive не подменён фиктивным obligation.

Статическая проверка stdlib AST: изменена ровно одна функция, все 29 base test IDs
и decorators сохранены; остальные функции и module-level imports/AST равны базе.
В node 3 → 20 asserts: 2 старых selector guards сохранены, 1 retired status guard
получил V4 successor и положительный контроль. Module 82 → 99 asserts, 628 lines.
Candidate assignment AST неизменен, SHA256
`95cec22efcf45a63d1b2d9f777a90cb57426bc580da89c6c8518cece6d40b457`.
Новый node AST SHA256
`5bc860ad91285c25b2c493f51e9294d315b53d81aa007e28c79e05cd198936ec`.
Diagnostic module hash прежний:
`49a9a1d17f9107ce44dfb616be86e6c5dcb6200a6ad42c48096fd04cd39bd566`.

SHA256 test file до: `28279b66d83980b355cdb62b49a8ce29e2b1b5d4bb9fa8ccbda79840964dc5ea`.
После: `cac481ae88391c6855be0a1e2f5ca9b64180f42753b5ea9832b5dc9f742344a6`.

`git diff --check` PASS. Только stdlib AST/hash/source inspection; локальные
runtime/import/pytest/provider проверки и installs не выполнялись. Runtime PASS
не заявлен: independent review и обычный CI на опубликованном SHA обязательны.

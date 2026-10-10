# PR #211: independent review stable identity collision

2026-10-08. **APPROVE** для узкой test migration; runtime PASS не утверждается.
База `03583656617336a746e9192249467017d6131f29`.

Независимо проверены frozen hashes:

- `tests/docs/test_evidence_selection_part02.py`:
  `cac481ae88391c6855be0a1e2f5ca9b64180f42753b5ea9832b5dc9f742344a6`.
- `v2plan/PR211_IDENTITY_COLLISION_FIXTURE_REVIEW_RU.md`:
  `424d88b6df7624ea6cd39c33949f314be9c1b9f873705347fe0b0fc949ec5568`.

Оба исходных candidate имеют тот же stable ID `same`, общий source/parent из
неизменённого helper и разные строки preserve/disable isolation. Helper по-прежнему
вычисляет разные SHA256 из этих строк. Candidate assignment AST сохранён точно
(`95cec22efcf45a63d1b2d9f777a90cb57426bc580da89c6c8518cece6d40b457`), вопрос тот же.
Удалены только неподдерживаемые старые representation arguments: positional
1500 у patch config и max_tokens у builder. Новый cutoff не введён.

Текущий selector до admission сравнивает identity bindings с content hash и
исключает все строки конфликтующего stable ID. Оба прежних selector assertions
сохранены точно. Старый packet status получил действующий V4 successor:
failure/unavailable, edit_ready=False, machine reasons stable identity collision
и no_admitted_evidence, отсутствие sources. Это сохраняет отказ до выдачи
конфликтующего текста, а не заменяет старое expected фактическим значением.
Schema V4 прямо запрещает sources/assignments у failure и допускает только
edit_ready=False; producer использует тот же selector и передаёт его missing.

Новый положительный контроль — две отдельные одинаковые копии первого исходного
candidate. Вопрос и selection config те же, дополнительных requirements,
authority/provenance flags или изменения source bytes нет. Проверяются
единственный selected ID с точным текстом, отсутствие collision reason, один
packet source с тем же ID/text и успешная текущая schema/binding validation
с `evidence_items=identical`. Поэтому контроль не может пройти через пустую
выдачу или общий отказ всем дубликатам.

Положительный packet честно остаётся data/partial, edit_ready=False и содержит
visible_content_assignment_required. Это следует из действующего хвоста
selector: без visible unit assignment добавляется missing; builder сохраняет
source и этот missing. Validator требует visible content assignment только
для completeness=complete. Следовательно, здесь не установлен builder/validator
конфликт и не требуется выдавать positive искусственные obligations для PASS.

Независимый stdlib compare: изменена ровно одна function, её signature/decorators
сохранены; весь прочий module AST совпадает с базой. Node asserts 3→20, module
82→99; 29 base test IDs сохраняют hash
`49a9a1d17f9107ce44dfb616be86e6c5dcb6200a6ad42c48096fd04cd39bd566`, совпадающий с
неизменённым diagnostic manifest. Новый node AST hash
`5bc860ad91285c25b2c493f51e9294d315b53d81aa007e28c79e05cd198936ec` проверен отдельно.
Shared helper, selector, packet producer, validator и schema byte-identical базе.
`ast.parse`, compile без исполнения, `git diff --check` — PASS.

Локальных repository imports/runtime/pytest/provider/client/install действий
не было. Написан только этот independent report. Production, retrieval, gold,
действующие work/security bounds и CI gates не менялись. Замечаний до обычного
совместного CI на опубликованном SHA нет.

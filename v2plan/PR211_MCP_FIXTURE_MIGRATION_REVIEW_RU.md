# PR #211: четыре миграции MCP fixtures

Дата: 2026-10-08. Автор: acceptance-audit агент. Изменены только три test files
и этот отчёт. Production, остальные contract expectations, markers, selections,
gold и gates этим slice не меняются. Независимый review выполняет отдельный агент.

## Статус и воспроизводимая база

**Четыре миграции реализованы; проверены статически. Pytest и project imports
локально NOT RUN: необходимые зависимости отсутствуют.** Указанные ниже wide
positives и ограничения — assertions для следующего CI, не объявленные PASS.

Предыдущий реальный advanced run: [CI 37802068737, job 113396563670](https://github.com/Vanilla1999/DocAtlas/actions/runs/37802068737/job/113396563670).
PR HEAD — `b68759e65f52317928ba22166248e679098024ae`; проверенный merge SHA —
`964056442f67b0d913310d3f8a295deb3c90263e`. Результат — 622 executed:
513 PASS, 109 FAIL, 0 ERROR, 0 SKIP. В этих MCP группах было 19 FAIL;
четыре перечисленных ниже входят в точный failure roster JUnit и job log.
Извлечённый JUnit SHA256:
`db0976872c65925747cc1b370758b5e39d882eef8ea8952c96058e403f8aa378`.
Это evidence базы, не runtime evidence текущего diff.

Локальный Git HEAD остаётся `21fe472d983f394130849d6fd4e582043d58e9ba`:
предыдущая публикация выполнялась отдельно. Эти три test files до текущего slice
совпадали с данным HEAD; их baseline hashes приведены ниже. Поэтому AST comparison
с ним корректен именно для этих файлов, но не для всего рабочего дерева.

## Почему достаточно fixtures

В [SourceBoundary](../docmancer/docs/domain/source_boundary.py) доступ к source
требует конечного `catalog.code_files`; валидный путь или знакомое имя сами по себе
не разрешают обход дерева. В
[build_patch_plan_context](../docmancer/docs/_patch_plan_context_part02.py)
отсутствие membership даёт `unresolved_local_code_membership` до поиска.
При явно перечисленных files сохраняются локальная навигация, ограниченные refs
и порядок результатов.
[build_implementation_map](../docmancer/docs/_patch_plan_context_part01.py)
привязывает `current_behavior` к прочитанным bytes и оставляет confidence=unknown.
Это не доказательство поведения, отсутствия символа, policy или права на edits.

Для budget test текущие
[generated и fallback producers](../docmancer/docs/application/_patch_constraints_service_part02.py)
поддерживают advisory из явно переданных generated/lockfile paths. Они дают
достаточно реальных кандидатов для проверки caps без извлечения правил из prose
и без dependency metadata reads. При этом
[MCP handler](../docmancer/docs/interfaces/mcp/project_tools.py)
всегда сохраняет unresolved policy и отсутствие edit authority. Producers и этот
guard тесты не подменяют.

## Изменённые nodes и сохранённые guards

| Node ID | Миграция и положительный контроль | Исходный guard |
|---|---|---|
| `tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_normalizes_snake_case_and_pascal_case` | Два literal members: MenuIcon и TabIcon. Вопрос и snake_case symbol_queries сохранены. Требуются ровно оба файла, прежний порядок, refs и фактические чтения обоих selected sources. `Path.open` spy отклоняет чтение остальных fixture files и внешних Dart sources; локальные control files перечислены отдельно. | Прежние два assertions о порядке и наличии refs сохранены буквально. |
| `tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_compact_source_output_is_json_serializable_and_bounded` | Только пять существующих source files из прежнего fixture объявлены в catalog. Одинаковый запрос идёт через реальный handler с wide max_files=12 и прежним narrow max_files=3. Wide обязан вернуть все пять; narrow — первые три в том же порядке. | Прежние ровно 3 результата и JSON UTF-8 размер `< 32000` сохранены буквально. |
| `tests/test_mcp_patch_plan_context_output_contract.py::test_patch_plan_context_output_contract_shapes` | Исходный NBO fixture копируется в tmp_path; объявляется ровно существующий menu_line.dart. Реальный handler обязан вернуть этот файл и непустой source-bound current_behavior. Общий committed fixture не модифицируется. | Все пять прежних assertions, включая reason_code=None, token type и shape, сохранены буквально. Проверка shape пустого risks list остаётся прежней и не заявляется доказательством наличия policy. |
| `tests/test_mcp_patch_constraints_tool.py::test_mcp_tool_respects_max_constraints_and_max_tokens` | Explicit changed_files содержит generated path и pubspec.lock. Wide 12/1200 обязан иметь >2 constraints, token_estimate>180, отсутствие truncation, generated advisory с верными source/files/severity и lockfile check. Затем тот же запрос ограничивается прежними 2/180. | Все три прежних assertions: count≤2, token_estimate≤180, budget warning — сохранены буквально. Дополнительно проверяются 2/180 в token_budget и truncated=True. |

Общие source helpers используются только тремя разрешёнными plan nodes.
Они сохраняют исходные bytes до вызова producer и проверяют:

- непустые, уникальные `relevant_files`, каждый внутри literal membership;
- `action=read`, непустые refs, допустимые start/end и буквальное наличие
  locate_by_pattern внутри указанного диапазона исходного файла;
- единственный `current_behavior` на каждый из первых пяти relevant files,
  confidence=unknown и SHA256 исходных bytes;
- bounds и непустой literal evidence самого current_behavior;
- неизменность отображения path→bytes после вызова, а не только множества bytes.

В budget node положительный контроль использует generated **path advisory**, а
не предположение, что generated file уже существует или разрешён к чтению.
Lockfile path выбирает generic consistency check, не version/policy proof.
Для wide и narrow явно проверяются packet_available=True, policy_coverage=unresolved
и answer_available/answer_supported/mutation_authorized/edit_ready=False.
Исходный changed_files list должен остаться неизменным.

При 180 tokens final clamp вправе удалить все constraints после добавления
warnings. Поэтому narrow nonempty не навязывается: содержательный wide positive,
его превышение обоих narrow bounds, сохранённые caps и truncated warning уже
проверяют реальную работу ограничения. Ни потолки, ни failure expectations ради
этого не увеличены.

## Что проверено локально

Выполнены только read-only source/diff inspection и изолированный stdlib
AST/data analysis (`python3 -I -S`), без импорта repository modules:

- AST parse всех трёх файлов — PASS.
- Сравнение с baseline: ровно четыре разрешённые test functions изменены;
  все остальные top-level AST совпадают после удаления явно добавленных
  imports и двух private helpers. Общие `_source_fixture`, `_dependency_fixture`,
  `_workspace`, `_payload` не изменены.
- Все прежние 25 test node names этих трёх modules сохранены: 4 изменены,
  21 остался прежним. Ни один node не добавлен, не удалён и не переименован.
- Все 12 исходных assert AST четырёх nodes присутствуют в новых функциях
  без изменения (2 + 2 + 5 + 3).
- Literal membership списки из AST содержат 2 и 5 уникальных nongenerated files,
  действительно создаваемых прежним `_source_fixture`. Отдельный NBO member
  существует, является обычным file и содержит 989 bytes.
- `git diff --check` для трёх test files — PASS.

Не запускались pytest, source discovery, service constructors, Git/server test
subprocesses, provider/model downloads, user-index operations или clients.
Нет локального PASS четырёх runtime nodes. Следующий обязательный шаг —
независимый review, затем штатный joint CI на финальном SHA с JUnit evidence.

## Остальные 15 FAIL: blocked contract review

Ни одно из этих ожиданий не изменено. Добавление code_files не восстанавливает
намеренно отключённые dependency scans, symbol absence proof, rejection
certificates или edit plans. Для successors нужно отдельно определить
поддерживаемый producer/consumer contract и сохранить содержательные
positive/unknown/violated controls.

| Node ID | Причина отдельного review |
|---|---|
| `tests/test_mcp_patch_constraints_tool.py::test_mcp_return_shape` | Success/answer authority против unconditional unresolved MCP boundary. |
| `tests/test_mcp_patch_constraints_tool.py::test_mcp_tool_returns_grouped_constraints` | Ожидает dependency/source-of-truth groups из prose/metadata, которые текущие producers не сертифицируют. |
| `tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_handler_accepts_minimal_question` | Запрос без project membership; требуется честный no-membership contract. |
| `tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_wires_changed_files_design_context_and_rejected_sources` | Кроме локальной навигации ожидает rejected-source proof. |
| `tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_prioritizes_changed_files` | В node также ожидается непустой mutation plan; одной membership недостаточно. |
| `tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_builds_compact_implementation_map_for_flutter_fixture` | Ожидает policy/edit-plan/verification semantics сверх локального read context. |
| `tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_reports_missing_symbol_from_symbol_queries` | Пустое совпадение не даёт symbol absence certificate. |
| `tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_finds_requested_dart_dependency_apis` | Dependency source membership не определён. |
| `tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_does_not_report_project_root_as_dependency` | Положительный dependency API control требует явного поддерживаемого dependency contract. |
| `tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_does_not_scan_entire_pub_cache_for_dependency_symbols` | Нельзя заменить прежний положительный bounded lookup простым пустым результатом. |
| `tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_adds_dependency_api_as_missing_symbol_alternative` | Ожидает dependency lookup и absence/alternative inference. |
| `tests/test_mcp_patch_plan_context_dependency_lookup.py::test_patch_plan_context_resolves_dart_dependency_source_from_nbo_fixture` | Dependency lookup намеренно unresolved. |
| `tests/test_mcp_patch_plan_context_negative_symbols.py::test_patch_plan_context_negative_symbol_alternative_from_nbo_fixture` | Нужны обоснованные negative-symbol/alternative controls. |
| `tests/test_mcp_patch_plan_context_nbo_fixture.py::test_patch_plan_context_nbo_fixture_acceptance_smoke` | Общий NBO acceptance включает dependency/absence/edit semantics. |
| `tests/test_mcp_patch_plan_context_tool.py::test_get_patch_plan_context_nbo_menu_acceptance_fixture` | Общий NBO acceptance включает dependency/absence/edit semantics. |

Существующие finite-read/no-scan controls в
`tests/test_dictionary_exit_local_callers.py`, advisory boundary в
`tests/test_dictionary_exit_patch_boundary.py` и механические violated/unknown
controls в `tests/test_dictionary_exit_patch_validation.py` не менялись.
Footprint gate 7066>6144, retrieval 800-token gate и остальные required/downstream
failures не закрываются этим review и не объявляются отложенным PASS.

## Content hashes

Hashes относятся к содержимому test files, не к tested commit SHA.

| Файл | SHA256 baseline | SHA256 candidate |
|---|---|---|
| `tests/test_mcp_patch_plan_context_tool.py` | `b44b573308f21dd3c46532d40e9079fc3d82b04e2c745c8895883306e65506f4` | `430c3e0fde5c48e3b791a35120b01f9223347505d8bd440e541e141f74bc9dd2` |
| `tests/test_mcp_patch_plan_context_output_contract.py` | `ffc36fad314617d0b47e3324b91106887088d74f459870c43d0ea072d4a130f5` | `b0baf7c63851cfeb2eb25f9e58a3141b0202316ed7f0ef3eea0c999b72e5e997` |
| `tests/test_mcp_patch_constraints_tool.py` | `d7ac6b4148c1f945e1ba2e6c9c0b38b8953817f5198502d1b3bf89250f4f9d12` | `1ade00e62d47f508b3c36a3f4e34d01dafdfb1815da143941dafc267c17f6cd2` |

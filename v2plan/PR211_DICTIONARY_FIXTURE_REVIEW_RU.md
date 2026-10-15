# PR #211: literal source fixtures для dictionary-exit callers

Дата: 2026-10-08. Author review следующего узкого slice.
Исходная база: `df9b682fdd13d8f4d1c5bff6cc4bfc0286e5f8ce`.

Изменены только `tests/test_dictionary_exit_local_residuals.py` и
`tests/test_dictionary_exit_read_tails.py`: **11 согласованных test functions,
27 concrete исходных FAIL cases**. Все исходные assertions, test names и
parameter decorators сохранены. Production и ранее reviewed implementation
files не менялись. Runtime новой версии: **NOT RUN**, требуется независимый
review и следующий normal CI.

## Исходное evidence

Прочитан ledger `df9b682-core-3.12-cases.json` из
[core Python 3.12, CI 37811010878](https://github.com/Vanilla1999/DocAtlas/actions/runs/37811010878/job/113427539519).
HEAD: `df9b682f`; фактический merge checkout:
`4fe1bec2e96a211969676b7086e0d2e769f64981`.

| Module | Concrete cases | Исходный PASS | Исходный FAIL | Затронутый FAIL |
|---|---:|---:|---:|---:|
| `test_dictionary_exit_local_residuals` | 71 | 37 | 34 | 24 |
| `test_dictionary_exit_read_tails` | 58 | 29 | 29 | 3 |
| Итого | 129 | 66 | 63 | 27 |

Первый общий барьер выбранных cases — source fixture есть на диске, но finite
`code_files` membership не объявлена. Это не доказательство, что после
подготовки все старые semantic/output expectations пройдут. 27 — точный
allowlist для следующего runtime сравнения, не уже полученное число PASS.

## Контракт и границы

[`SourceBoundary`](../docmancer/docs/domain/source_boundary.py) допускает
только literal members. `source_roots`, query, наличие файла, suffix роли
и generated filename не дают такого разрешения.

[`source_map`](../docmancer/docs/domain/source_map.py) различает обычный
query-matched map и явно запрошенный `include_unmatched=True` structural
context. [`project_state._documentation_gap_evidence`](../docmancer/docs/domain/project_state.py)
использует последний вариант с исходным query, `max_files=6`, `token_budget=800`.
Source paths при этом не объявляют доказанными required documentation facts;
`evidence_complete`, answer support и edit readiness продолжают проверяться
как False в прежних tests.

Положительные fixtures теперь объявляют свои конкретные допустимые исходники.
Отрицательные controls отдельно объявляют forbidden member и проверяют
отказ всей декларации до source read. Это сохраняет whole-declaration
preflight: недопустимый member не превращается в silent partial filtering.

Generated permission в двух затронутых boundary tests уже была явной
`include_generated=True` и сохранена. Boolean/query semantics producer не
меняются. 34 параметризованных generated cases с другим контрактом исключены
из этого slice полностью.

## Реализованные fixture changes

Helper `_declare_code_files` записывает finite test-owned paths в
`docatlas.project-docs.yaml`, `schema_version: 1`, `documents: []`.
Он не вызывается автоматически из `_write`, не сканирует дерево и не расширяет
декларацию из текста вопроса. Поэтому несогласованные функции этих modules
сохраняют исходный setup. Для fixture на девять файлов используются ровно
те же девять имён из `range(9)`, которыми автор создаёт файлы.

### Snippet order, structural context и fidelity

В `test_real_snippet_budget_does_not_prefer_role_names` оба допустимых файла
объявлены явно. Существующий matching decoy `unlisted.dart` не входит в grant.
До catalog тот же реальный reader возвращает пустой результат без source read.
После catalog observer вокруг настоящего `Path.read_text` подтверждает чтение
ровно `a.dart` и `b.dart`, по одному разу, с ожидаемыми SHA256 fixture bytes.
Observer возвращает исходный прочитанный текст без изменения. Путь и line
bounds вложенного source совпадают с item; snippet совпадает с настоящей
строкой файла. Прежнее `max_items=1` и проверка первого literal requirement
перед role-suffixed именем сохранены для всех семи suffix variants.

Gap/original-query tests получили точную membership своих файлов. Вызов
`collect_project_source_facts` по-прежнему проверяется с исходным query и
прежними `max_files=6`, `token_budget=800`, `include_unmatched=True`.
Ни синтетические темы, ни NL aliases не добавлены.

Gap-cap fixture объявляет все девять созданных обычных файлов. Дополнительный
positive control сначала получает все девять с `max_files=9`, после чего
исходный gap assertion требует ровно первые шесть. Это подтверждает настоящий
output cap, а не декларацию, заранее суженную до шести members. Отдельный
mixed declaration с `other/out.py` проверяет, что загруженный `source_roots`
действительно ограничивает доступ.

CRLF/cache/span fixture получает membership `src/a.py`; все прежние assertions
про Python AST ranges, UTF-8/CRLF source bytes, неизменность SHA256 и изоляцию
копии `ProjectSourceFacts` сохранены. Хеш raw CRLF bytes не заменён hash
нормализованного read-text. Hash observer используется в другом LF fixture.

Read-tail structural test теперь читает объявленный `client.py` и сохраняет
проверку настоящих imports/symbols/string literals вместе с пустым
`status_like_tokens`. Значения `готово`/`active` не получают semantic authority.
Snippet redaction test читает объявленный `settings.py`; private value всё ещё
отсутствует в output, `[REDACTED]`, path, line bounds и `max_items=1` сохранены.

### Реальные denial controls

Для generated/root/exclude/gitignore/symlink test положительная декларация
содержит только `src/keep.py` и `src/generated/keep.py`. Затем каждый из шести
существующих запрещённых путей добавляется отдельно в смешанную декларацию:
excluded, ignored, outside-root, vendor, file symlink и directory symlink.
И facts, и snippets должны вернуть пустой результат. Observer охватывает весь
fixture `tmp_path`, включая соседний outside directory, и требует **ноль
source reads** для каждого отказа.

Extension-intersection test объявляет поддерживаемый Dart source, сохраняя
конфигурацию с `.dart` и `.unsupported`. Отдельный mixed declaration с
существующим `b.unsupported` отвергается целиком обоими collectors. Секретный
текст не выводится в положительном snippet.

В read-tail boundary test объявлен конкретный `src/allowed.g.dart` при уже
существующем literal generated opt-in. Новые mixed controls проверяют
excluded/oversized/outside/symlink members. Disabled boundary и нулевые output
budgets дополнительно проверяются с этой непустой допустимой membership;
прежние отрицательные assertions не удалены и не подменены.

## Точный allowlist

### `tests/test_dictionary_exit_local_residuals.py`

| Function | Исходные concrete FAIL |
|---|---:|
| `test_real_snippet_budget_does_not_prefer_role_names` | 7 |
| `test_gap_passes_original_query_and_explicit_unmatched_contract` | 6 |
| `test_empty_or_unmatched_gap_has_context_without_synthetic_topic` | 4 |
| `test_generated_consent_never_bypasses_roots_excludes_gitignore_or_symlinks` | 1 |
| `test_gap_honors_config_and_retains_six_file_deterministic_cap` | 1 |
| `test_ast_spans_original_bytes_and_new_unmatched_context_survive` | 1 |
| `test_supported_extension_intersection_and_secret_scrubbing_remain` | 1 |
| `test_default_inspection_conditional_gap_remains_context_only` | 3 |
| **Итого** | **24** |

### `tests/test_dictionary_exit_read_tails.py`

| Function | Исходные concrete FAIL |
|---|---:|
| `test_source_map_omits_semantic_status_summary_but_keeps_structural_facts` | 1 |
| `test_explicit_generated_opt_in_preserves_source_boundary_and_scan_limits` | 1 |
| `test_source_snippet_scrubbing_and_bounded_output_survive` | 1 |
| **Итого** | **3** |

Только эти 11 прежних test function AST изменены; остальные функции, включая
все parameter decorators, проверены на неизменность относительно `df9b682f`.

## Что явно исключено

- `test_generated_requires_boolean_true_even_for_explicit_path`: 10 FAIL cases.
- `test_only_explicit_generated_opt_in_authorizes_source_scanning`: 24 FAIL cases.

Эти две матрицы требуют сохранять normal member при одновременно запрещённом
generated member. Механическое объявление всех файлов приведёт к отказу всей
декларации; условное скрытие forbidden member только ради прежнего результата
сделало бы opt-in assertions неубедительными. Нужен отдельный contract review,
поэтому bodies/decorators обеих функций здесь не менялись.

- Два long-fragment recovery failures остаются без изменения.
- Старые ABI `max_tokens` и positional `patch_selection_config`, budget/cap
  expectations, NL planning/aliases и authority/admission не входят в slice.
- Deferred retrieval, production source maps, query/order logic и schema
  policy не изменяются этим test slice.

## Проверка inventory и frozen hashes

| Проверка | local_residuals | read_tails |
|---|---:|---:|
| Прежние test names сохранены | 16/16 | 12/12 |
| Изменены только allowlisted functions | 8 | 3 |
| Прежние assert AST сохранены | 57/57 | 55/55 |
| Assertions после slice | 71 | 58 |
| Удалённые assertions | 0 | 0 |
| Строк | 335 | 241 |

Новых nodes, decorators, skips/xfails и selector changes нет. Уникальные
base-node hashes совпадают с неизменёнными diagnostic shards:

- local_residuals: `7e6638ecd1837b5aef4258417def41888f0e275681e3c97daf962a8947cd9be2`.
- read_tails: `6f45004bf3b4b59b830fd5fa92cc324efafbc1ce1c9c3e5d135cd1b6afeaaa59`.

Diagnostic manifest обновлять для этого slice не требуется.

| Implementation file | SHA256 |
|---|---|
| `tests/test_dictionary_exit_local_residuals.py` | `aa9f9a53a46a3132e1d0ee1fed24b24f518697fe459549c283440d4a24eaac3c` |
| `tests/test_dictionary_exit_read_tails.py` | `46757bae94a36f5ef1303e915bc249fadf23a0664c6313e3e9853c4aacc793f4` |

AST parse/compile без imports, multiset сравнение старых assertions,
сравнение names/decorators, exact allowlist function diff и
`git diff --check`: PASS. Ранее approved code_graph/source_map и mutation
helper/named-document files проверены по frozen hashes: неизменны.

Pytest/runtime/imports repository, subprocess fixtures, package installs,
provider calls и clients локально не выполнялись. Следующий normal CI должен
проверить эти 27 исходных cases вместе с остальными и выявить реальные
последующие blockers без expected-to-actual подмены.

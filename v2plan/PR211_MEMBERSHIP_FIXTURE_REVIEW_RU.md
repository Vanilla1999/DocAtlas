# PR #211: finite source membership — fixture slice

Дата: 2026-10-08. Author review; исходный HEAD
`df9b682fdd13d8f4d1c5bff6cc4bfc0286e5f8ce`.

Изменены только `tests/docs/test_code_graph.py` и
`tests/docs/test_source_map.py`. Production retrieval/admission, package identity,
ranking, generated opt-in, budgets и обязательные gates этим slice не меняются.
Независимый review и новый совместный CI требуются до заявления о PASS.

## Evidence до изменений

Источник: [core Python 3.12, run 37811010878, job 113427539519](https://github.com/Vanilla1999/DocAtlas/actions/runs/37811010878/job/113427539519).
Фактический merge checkout: `4fe1bec2e96a211969676b7086e0d2e769f64981`.
JUnit artifact ID: `11564529466`.

- ZIP SHA256: `042379e673135f548796a8c2ffc65a3fa262f0a25a0194c55cba6f62b0f9363f`.
- XML SHA256: `a6d3627422890834da6c2e41ce7af93750c2ec57416e1a95ad014724bbc959c1`.
- Производный `df9b682-core-3.12-cases.json` SHA256:
  `2074907c9bc47469de0eb22199247531f64659df83f2c8f03a790ff3114aeba9`.

| Module | Cases | PASS до slice | FAIL до slice |
|---|---:|---:|---:|
| `tests.docs.test_code_graph` | 35 | 13 | 22 |
| `tests.docs.test_source_map` | 29 | 11 | 18 |
| Итого | 64 | 24 | 40 |

Это данные выполненного исходного CI, а не результаты изменённых fixtures.
В [историческом triage](PR211_CORE_FAILURE_TRIAGE_RU.md) эти две группы названы
кандидатами для проверки membership; документ не разрешает считать все
40 failures простой миграцией fixtures.

## Текущий контракт

[`SourceBoundary.from_project`](../docmancer/docs/domain/source_boundary.py)
получает `code_files` из валидного
[`docatlas.project-docs.yaml`](../docmancer/docs/project_docs_catalog.py).
`source_roots`, наличие файлов и query text не объявляют finite membership.
У graph отсутствие декларации означает `unresolved_membership`. У source
evidence отсутствие scan возвращает пустой результат и не доказывает отсутствие
запрошенного символа.

`iter_bounded_source_files` проверяет всю декларацию до выдачи первого пути.
Invalid, duplicate, excluded, generated без literal `True`, ignored, escaping
или symlinked member не даёт частичного разрешения для остальных members.
Предел количества объявленных файлов также проверяется до scan. Ограничения
по общей сумме байтов и deadline остаются runtime bounds.

Из этого следуют два разных действия в tests: положительный fixture объявляет
конкретные разрешённые файлы; отрицательный control явно объявляет запрещённый
путь и проверяет отказ. Простое исключение запрещённого файла из catalog не
заменяет проверку соответствующего guard.

## Что реализовано

### Положительные fixtures и наблюдение настоящих чтений

В каждом module добавлен небольшой helper, записывающий только test-owned
literal `code_files`, `schema_version: 1` и пустой `documents`. Он не обходит
дерево, не использует glob, не выводит membership из вопроса. Для теста на
25 файлов имена получаются из того же конечного диапазона `range(25)`, которым
fixture создаёт файлы; это не обнаружение файлов в repository.

Общие Dart/Python fixtures объявляют только свои существующие исходники.
Обычные runtime artifact и generated files в положительную декларацию не входят.
В тесте generic Cubit новый четвёртый исходник добавляется в явную декларацию
после создания; сохранён исходный вопрос и все ranking assertions.

Два representative positives дополнены observers вокруг настоящего
`Path.read_text`. Observer вызывает исходный reader, сохраняет SHA256 реально
прочитанного UTF-8 текста и возвращает его без подмены. Файлы небольшие, валидны
как UTF-8, поэтому ожидаемый hash вычисляется из созданных fixture bytes.

- `test_build_project_code_graph_links_python_local_import_and_reference`:
  до catalog — пустой graph, `unresolved_membership`, ни одного source read;
  после catalog — читаются ровно `app/api.py` и `app/service.py`, по одному разу,
  с ожидаемыми hashes. Существующий дополнительный `app/unlisted.py` с тем же
  именем символа не читается и не попадает в graph. Проверяются реальные
  file/symbol IDs, существование обеих сторон graph edges, line bounds,
  `line_count` и `char_count` против fixture bytes.
- `test_build_project_source_evidence_includes_match_type_and_confidence`:
  до membership — пустой результат и нет source reads; после membership
  читается только `lib/permission_service.dart`. Существующий matching decoy
  `lib/unlisted.dart` не читается. Путь и границы в item и вложенном source
  совпадают с реальным файлом; одна полная fixture line совпадает со snippet
  побайтно и по SHA256.

Низкоуровневые graph/map DTO сами не обещают отдельного поля `source_hash`.
Этот slice не придумывает такое поле: hashes доказывают реальный read,
а source paths, line ranges и graph references проверяются там, где они есть
в действующем контракте. MCP delivery и downstream authority этим unit slice
не сертифицируются.

### Отрицательные проверки стали невакуозными

Прежние assertions сохранены. Дополнительные controls проверяют:

- Generated graph/source members: публичный файл реально доступен;
  смешанная декларация публичного и generated файла отклоняется целиком.
  Для source-evidence и source-facts observer подтверждает ноль source reads
  у отклонённой декларации.
- Benchmark runtime artifact: положительный source-facts результат непустой;
  объявление runtime artifact из `uv-cache/archive-v0` вместе с обычным файлом
  не даёт частичного read. Observer также подтверждает ноль чтений.
- Excludes и gitignore: сначала разрешённый member даёт прежний ожидаемый путь;
  затем каждый excluded/ignored member добавляется явно, и декларация
  отклоняется. Anchored root negation проверяется отдельно от nested path.
- Anchored/nonanchored directory patterns: один и тот же объявленный nested
  member доступен только при anchored pattern; root member отклоняется.
- Manifest `source_roots`: валидный catalog позволяет прочитать `app/main.py`,
  фактически загружаются root и member. Явное добавление `other/ignored.py`
  блокирует декларацию. Positional `SourceBoundary(("src",), ...)` сохраняет
  compatibility первого аргумента и проверяет отдельный outside-root control.
- Invalid project config: источник теперь есть в валидном catalog, поэтому
  отказ не обеспечивается отсутствием membership.
- Generated opt-in в прямом boundary API: объявленный файл остаётся hidden
  по умолчанию, literal `include_generated=True` допускает его, строка `"true"`
  не является разрешением. Prose question не используется как разрешение.
- Symlink: объявлен настоящий `linked/secret.py`, и он отвергается;
  прежний пустой `code_files` больше не делает test тривиальным.
- Count/depth/bytes/deadline: положительный fixture имеет один явный member;
  oversubscribed declaration, слишком глубокий member, превышение file bytes
  и scanned bytes проверяются отдельно. Deadline также проверяется на непустой
  декларации. Старое ожидание, что traversal сам выберет первый из неизвестного
  дерева, не переносится в finite contract.
- `absent_in_source` теперь действительно создаётся после разрешённого scan;
  repo-map/facts compatibility сравнивает непустые результаты; graph depth
  имеет достижимый positive control на depth 2; unresolved-edge negative
  получает настоящий unresolved import; diagnostics cap проверяется на
  25 фактических file nodes.

## Точный затронутый roster

Все имена ниже остаются прежними. Общий helper учитывается как изменение
fixture соответствующих cases. Префиксы — пути двух указанных modules.

### `tests/docs/test_code_graph.py`: 24 cases

```text
test_build_project_code_graph_links_python_local_import_and_reference
test_build_project_code_graph_links_dart_relative_imports_and_references
test_build_project_code_graph_skips_generated_files
test_build_project_code_graph_marks_unresolved_external_import
test_build_code_graph_context_items_selects_screen_for_cubit_reference
test_build_code_graph_context_items_string_match_beats_connected_cubit
test_build_code_graph_context_items_external_import_does_not_dominate
test_build_code_graph_context_items_respects_small_token_budget_and_stays_compact
test_code_graph_context_diagnostics_summarizes_items
test_find_code_graph_paths_finds_screen_to_cubit_and_renders_edges
test_find_code_graph_paths_can_reach_service_with_target_terms_and_depth_two
test_find_code_graph_paths_respects_max_depth
test_find_code_graph_paths_ignores_unresolved_edges
test_build_code_graph_context_items_includes_likely_paths_for_high_score_file
test_build_project_code_graph_marks_dart_external_package_unresolved_with_metadata
test_build_project_code_graph_resolves_python_dotted_import_forms
test_build_project_code_graph_resolves_ts_extensionless_relative_import
test_build_project_code_graph_does_not_pick_random_basename_when_import_ambiguous
test_code_graph_diagnostics_reports_counts_unresolved_and_is_deterministic
test_code_graph_diagnostics_caps_lists_and_excludes_source_text
test_code_graph_context_diagnostics_includes_capped_score_reasons_by_path
test_code_graph_ranking_exact_string_beats_common_external_import_noise
test_code_graph_ranking_specific_symbol_beats_generic_cubit_match
test_code_graph_ranking_connected_service_appears_after_selected_screen_or_cubit_when_budget_allows
```

До slice: 21 FAIL + 3 PASS. Это не обещание 21 исправленного failure.

### `tests/docs/test_source_map.py`: 22 cases

```text
test_build_project_source_evidence_includes_match_type_and_confidence
test_named_gate_source_evidence_exposes_declaration_metadata
test_build_project_source_evidence_finds_camel_case_from_nl
test_build_project_source_evidence_absent_has_unknown_confidence
test_source_evidence_skips_generated_plugin_registrant
test_project_repo_map_extracts_static_source_facts_and_honors_budget
test_collect_project_source_facts_returns_python_and_dart_facts
test_collect_project_source_facts_keeps_repo_map_shape_compatible
test_collect_project_source_facts_skips_generated_files
test_collect_project_source_facts_skips_benchmark_runtime_artifacts
test_source_boundary_loads_project_manifest_and_limits_roots
test_source_boundary_applies_excludes_and_gitignore
test_source_boundary_gitignore_anchored_negation_only_reincludes_root_path
test_source_boundary_distinguishes_anchored_and_nonanchored_directories
test_source_boundary_preserves_legacy_positional_source_roots
test_source_boundary_invalid_project_manifest_fails_closed
test_source_boundary_generated_paths_require_explicit_opt_in
test_source_boundary_never_follows_symlink_outside_project
test_source_boundary_enforces_file_byte_depth_and_deadline_budgets
test_collect_project_source_facts_selection_score_favors_exact_question_term
test_source_facts_diagnostics_contains_counts
test_collect_project_source_facts_honors_token_budget
```

До slice: 17 FAIL + 5 PASS. Все 64 исходных test cases остаются в roster.
Новых test names, decorators, skip/xfail/parametrization или изменённых selectors нет.

## Что нельзя объявить закрытым этой миграцией

1. `test_build_project_code_graph_resolves_dart_package_self_import_with_metadata`
   оставлен без изменений. Он требует self-package identity из `pubspec.yaml`;
   текущий resolver возвращает `package_identity_unresolved` для package import.
   Объявление code files само по себе не даёт package identity.
2. `test_source_map_includes_generated_path_for_explicit_artifact_question`
   оставлен без изменений. Он требует generated opt-in из prose, а текущий
   API требует отдельный literal boolean. Подстановка `True` убрала бы саму
   спорную premise исходного test, поэтому здесь не выполнена.
3. В `test_build_project_code_graph_links_dart_relative_imports_and_references`
   объявлены настоящие исходники, но сохранено прежнее требование строки
   «Вернуть в работу» внутри `status_like_tokens`. Текущий source-map producer
   намеренно оставляет compatibility field пустым: source words не доказывают
   status facts. Поэтому после устранения membership barrier этот case должен
   рассматриваться как отдельный semantic contract conflict, а не как
   подтверждённый fixture PASS.
4. Ranking assertions всех затронутых cases сохранены буквально. Fixture
   membership может открыть дальнейшее расхождение score/order/connected
   selection. Ни ranking, ни ожидаемый порядок не подменялись ради зелёного CI.

## Выполненная локальная проверка

Использованы только stdlib AST/compile, чтение сохранённого JUnit ledger,
read-only `git show` и `git diff --check`. Pytest, repository imports, providers,
clients, package installs и runtime subprocess fixtures локально не запускались.
Runtime outcome изменённых tests: **NOT RUN**, ожидается обычный CI root-ветки.

| Проверка | code_graph | source_map |
|---|---:|---:|
| Старые test node names сохранены | 35/35 | 29/29 |
| Старые `assert` AST сохранены | 144/144 | 74/74 |
| Assertions после slice | 160 | 103 |
| Удалённые assertions | 0 | 0 |
| Строк в module | 830 | 634 |
| AST parse / compile | PASS | PASS |
| `git diff --check` | PASS | PASS |

SHA256 файлов на момент author review:

- `tests/docs/test_code_graph.py`:
  `fafe19b4e843573dfb5ea9e2b9bb8fd150c1c7ce2d13af0716259b4afb347332`.
- `tests/docs/test_source_map.py`:
  `6fd36d40f70f8eb2e7c485112e06875ea21674b9c133bcefb14bf04caa8b003e`.

Для сравнения assertions использован multiset
`ast.dump(assert_node, include_attributes=False)` из исходного `git show HEAD:path`
и рабочего файла; для names — упорядоченный список top-level `test_*` functions.
Это подтверждает сохранение прежних проверок, но не заменяет исполнение CI.

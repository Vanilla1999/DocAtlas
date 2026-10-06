# Read tails: bounded dictionary-exit implementation

Дата: 2026-10-06. Primary baseline
`adc9abf8cfc939ef1e44e8895c00b448b77033b3`.
**Реализован bounded slice; independent review ещё не выполнен; full exit NOT DONE.**

## Ownership / точный diff

Изменены только три согласованных production-файла:

1. `docmancer/docs/application/context_candidate_ranking.py`
2. `docmancer/docs/application/recovery.py`
3. `docmancer/docs/domain/source_map.py`

Новые файлы этого implementation slice:

4. `tests/test_dictionary_exit_read_tails.py`
5. `tests/diagnostic_labels.dictionary_exit_read_tails.json`
6. Этот `READ_TAILS_DICTIONARY_EXIT_RU.md`.

Предыдущий read-only audit `REMAINING_DICTIONARY_AUDIT_RU.md` сохранён как baseline
caller map; его live remaining sections 2/3/7 теперь superseded данным slice.
SDK patch shards, corpus fetchers, workflow/templates и их tests меняют другие
исполнители: их diff не reviewed этим агентом. Dormant compiler/proof files,
старые tests/gold/thresholds/freeze и historical manifests не менялись.
Network, commit, push не выполнялись.

## Что удалено и что осталось техническим

### Ranking

`_facet_aware_candidates` больше не импортирует/вызывает
`independent_sentence_spans` и не использует NL clause independence для ratio.
32-position sort key сохранён; бывший independent ratio slot равен `0.0`, nested
tail остаётся длиной 10. Остальные lexical/structural signals и fallback `key[:9]`
не переставлены. Это удаляет live parser execution даже в default projection,
где до slice effect уже был нулевым из-за пустых `need_query_ids`.

### Recovery

Удалены imperative verb vocabulary, leading-code-path stripping с NL connectors,
fixed English question wrappers, Cyrillic rephrase veto и wrapper-recognition
exhaustion logic. `build_recovery_diagnosis` больше не создаёт
`suggested_questions`/`rephrase_exhausted`; uncertain proof → typed
`search_local_source`. Исходный bounded `problem_spans` fragment сохраняется без
semantic clause splitting/operation/path удаления.

Private `_suggested_questions(question, requirements, evidence_path=...)` оставлен
как пустой compatibility adapter: старые direct imports не ломают collection,
но список всегда пуст. `recovery_action` отклоняет supplied legacy
`rephrase_question` diagnosis, вместо возврата question patch, claims о
`preserves_source_words` или повторного `get_docs_context`.

Сохранены operational reason enums/precedence, conflict hard stop,
`documentation_supported=False`, early return для supported decision, fragment
bounds и typed local inspection. Local handoff имеет `auto_execute=False`,
`repeat_docs_context=False`, не разрешает edit и не снимает source authorization.
Ноль synthesized retries удовлетворяет at-most-one ceiling; retry исходного
вопроса не объявлен equivalence/recovery автоматически.

### Source map

* Удалён status vocabulary regex и blanket Cyrillic literal classifier. Поле
  `status_like_tokens=[]` сохранено для code-graph/direct consumers; в rendered
  source-map content status summary не появляется. Нового semantic replacement
  нет. Обычные bounded raw string literals, imports и symbols остаются facts,
  не превращаются в status proof.
* Удалены EN/RU NL `_QUERY_STOPWORDS`; bounded literal token extraction и
  24-term ceiling сохранены. Обычные function words теперь могут занимать lexical
  budget/повлиять на recall; не добавлены aliases/topic weighting.
* Generated source scanning разрешает только явное boolean
  `include_generated is True`. `None`/False не разрешаются ни generated phrases,
  ни точным `.g.dart/.freezed.dart/.pb.go` spelling в question. Explicit path
  остаётся identity/search input, не снимает generated boundary.
* `_KEYWORDS`, AST/import/declaration grammar, suffix→language map, path extraction,
  SourceBoundary/config/exclusions/symlink guards, existing scan ceilings,
  secret scrubbing source snippets и line identities не изменены. Whole-file
  unbounded output не введён; capture по-прежнему проходит bounded file traversal.

## Tests / честный статус

Все запуски: normal repository conftest, `PYTHONDONTWRITEBYTECODE=1`,
`DOCATLAS_OFFLINE=1`, `.venv/bin/python -m pytest -p no:cacheprovider -q`.
Новый behavioral shard hash-bound; base manifest не переписывался.

| Запуск | Результат |
|---|---|
| Только `tests/test_dictionary_exit_read_tails.py` | **58 passed** |
| Read tails + literal needs + literal needs MCP + reference/ranking + indexed MCP + projection + public request | **289 passed** |
| Target security, content trust, reference hash domains, review source capabilities, finalized MCP output integrity, MCP boundary | **46 passed**, 1 existing dependency warning |
| Source map, request source facts, code graph, code graph golden, mixed-script recovery, source recovery targeting, agent recovery version guidance | **82 passed / 8 failed**, assertions сохранены |
| Context7-style project chat + source-search/edit readiness | **23 passed / 48 failed**, assertions сохранены |
| Scoped `git diff --check` | PASS |

Полный green CI/quality/release не заявлен. Stdio smoke не запускался: этот скрипт
создаёт fixture commits, а текущий slice запрещает commit. Новые indexed MCP
tests запускают локальный production path, но не заменяют stdio transport smoke.
Self-host quality не перезапускался; прежние red artifacts/floors не менялись.

Новые cases проверяют: forbidden NL ranking parser, tuple ABI, EN/RU original
diagnostics/no suggestions, supplied legacy retry rejection, все operational
reason codes, authoritative hard stop, projection recovery, generated phrases и
literal suffixes × None/False/True для трёх direct SDK collectors, stopword-free
literal extraction, empty status summary, AST line facts, explicit generated
permission при source-root/exclusion/file-byte/symlink restrictions, snippet
redaction/max-items и programming grammar preservation.

Первый new-only run: 48 passed / 10 failed из-за двух ошибок **новых test fixtures**:
nested tuple tail expectation 11 вместо baseline 10; source evidence ограничивает
один term двумя snippets, поэтому `Alpha` не гарантирует все четыре files.
Исправлены только новые tests: верная ABI длина и explicit per-file requirements,
без ослабления production ceilings. После этого 58 passed.
Один запуск ошибочно указал несуществующий `test_dictionary_exit_literal_needs_public.py`
и завершился до collection; повторный корректный список дал 289 passed.

### Red ledger и attribution boundary

Прямо соответствуют удалённому поведению четыре существующих assertions:

* `test_source_map.py::test_source_map_includes_generated_path_for_explicit_artifact_question`
  — прежде NL wording открывал generated scanning.
* `test_code_graph.py::test_build_project_code_graph_links_dart_relative_imports_and_references`
  и `test_code_graph_golden.py::test_code_graph_golden_source_facts_cover_dart_python_and_skip_generated`
  — ожидают Cyrillic text в `status_like_tokens`.
* `test_source_search_edit_readiness.py::test_rephrase_drops_imperative_and_code_path_from_subject`
  — ожидает synthesized rewritten question.

Остальные failures первого mixed run: NL code-graph routing (1), mixed-script
alias/coverage (2), supplied recovery assignment projection (1), template guidance
(1, concurrent owner). Второго: старые alias/answer-contract/disposition/index
positive assertions и completeness readiness expectations. Их причинная
baseline-vs-slice attribution отдельно не измерена; не считать все 48 новой
regression этого slice. Тесты не исключены из отчёта и не исправлены ради PASS.

## Риски / NEXT

* Честная coverage loss: нет status-derived/Cyrillic duplicate summary; generated
  files требуют отдельного explicit SDK opt-in; нет rephrase rescue. Для lexical
  term budgets без stopwords возможна меньшая полезность. Не компенсировать
  ручными aliases/prompts или ослаблением frozen quality floors.
* Source-map `_source_evidence_terms` по-прежнему prioritizes suffixes
  `Gate/Service/Repository/Controller/Manager/Policy/Adapter`; это отдельный
  remaining semantic/target-selection candidate, вне согласованного tail deletion.
  `_documentation_gap_evidence` в `project_state.py` имеет topic fallback
  `query or "architecture"` — NEXT отдельного owner slice.
* Dormant/direct-call `question_plan` sync API injection, public-tool/Python subject
  injection, semantic frame/composition и premise/governance proof vocab — NEXT,
  не очищены этим diff. Admission grammar/command-rule adapters уже fail-closed
  на baseline; enum/constants не удалять как словари.
* External SDK callers и delivered gap/source-map consumers требуют integration
  review; текущие empty compatibility fields/adapters не доказывают full exit.
  Concurrent SDK/corpus/template changes и final whole-tree tests должны быть
  reviewed интегратором отдельно, не по итогам этих scoped PASS.

## Scoped SHA-256 после implementation/tests

| Файл | SHA-256 |
|---|---|
| `context_candidate_ranking.py` | `5d1caa8e05a81de49754c5e0e7e88f0792b04287db5d9c33ca2bf33209730527` |
| `recovery.py` | `0b7b62ce676889206d8b902af357f89f142850f9d642c18938030809f8601e6b` |
| `source_map.py` | `1085cc4e6f0d3dea36d32ac44f9443d496c0b67004e29def4f306572d9955b3d` |
| `tests/test_dictionary_exit_read_tails.py` | `c2ef8c2cece35a9f6a06091125341f182ab53c932d715b2738c49dc9256408d6` |
| `tests/diagnostic_labels.dictionary_exit_read_tails.json` | `2740d80013bcf06a636ccf8269b102b7fc35728cf7ab6b7412c3a6c90df3b578` |

Это scoped provenance, не historical manifest update или frozen acceptance.

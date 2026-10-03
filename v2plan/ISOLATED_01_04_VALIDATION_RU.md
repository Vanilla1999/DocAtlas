# Закрепление изолированных результатов 01–04

2026-10-02. По запросу пользователя выбран вариант 1: проверить и сохранить
полезные результаты без подключения нового public route.

## Итог

**Новые API focused Green; в одинаковом legacy inventory новых failing nodes нет.**
Это не полный regression, не шаг 08, не Gate A approval и не приёмка public delivery.
Gate A и M2 остаются BLOCKED; stub шага 05 и research Reds сохранены.

Candidate snapshot: `3dc6a17b` (перед запуском working tree чистый).
Baseline: `30056be881cf99f085e6ff9a839c4e12f0c4ae28`, существующий чистый detached
worktree `/tmp/opencode/m2-step04-baseline`. Он использован только для baseline
commands, основная session directory не менялась.
Interpreter в обоих checkout: `/usr/bin/python3.12`.

## Новые API

```bash
/usr/bin/python3.12 -m pytest -q tests/docs/test_source_window_eligibility.py tests/test_retrieval_passages.py tests/test_retrieval_passage_index.py tests/test_lexical_passage_retrieval.py
```

**29 passed**, exit 0. Проверяются source-window bindings, deterministic contextual
passages, atomic generation/index lifecycle и bounded native BM25 retrieval.
Source eligibility не означает relevance/support; retrieval не означает delivery.

## Одинаковые legacy controls: baseline и candidate

Следующая команда выполнена в обоих checkout без изменения tests/expectations:

```bash
/usr/bin/python3.12 -m pytest -q tests/test_structured_chunking.py tests/test_parent_child_index.py tests/test_pre_hydration_source_policy.py tests/docs/test_evidence_qualification.py tests/docs/test_context_constraint_roles.py tests/docs/test_read_context_admission_boundary.py tests/docs/test_shared_context_proposals.py tests/docs/test_source_bound_subject_context.py tests/test_contextual_indexing.py tests/test_parent_child_vectors.py tests/test_clear_rebuild_lifecycle.py tests/test_index_storage_cleanup.py tests/test_sqlite_ranking_truth.py tests/test_retrieval_diversity_policy.py tests/test_public_vector_retrieval.py tests/test_vector_fallback.py
```

| Checkout | Passed | Failed | Exit |
|---|---:|---:|---:|
| Baseline `30056be8` | 195 | 3 | 1 |
| Candidate `3dc6a17b` | 195 | 3 | 1 |

Failed node IDs совпадают:

```text
tests/docs/test_shared_context_proposals.py::test_precedence_proposals_do_not_rescue_echo_or_heading[page title wins when navigation configuration and Markdown content define different titles.]
tests/test_public_vector_retrieval.py::test_public_project_docs_query_consumes_dense_vector_index
tests/test_public_vector_retrieval.py::test_public_library_query_consumes_dense_vector_index
```

Прежний precedence proposal failure и два прежних `vector_store_unavailable`
controls не объявлены PASS. Existing unknown `asyncio_mode` warning присутствует
во всех runs. Сравнение node IDs не доказывает полную output parity.

## Артефакты и сохранённые границы

В `/tmp/opencode/m2-model-free-execution-30056be8/`:

- `isolated-01-04-new-api.log`;
- `isolated-01-04-candidate-legacy.log`;
- `isolated-01-04-baseline-legacy.log`;
- `isolated-01-04-comparison.json` — summaries и разность failing node IDs.

Runtime, tests, gold, dependencies, public route, user storage и defaults в этой
проверке не менялись. Installed MCP, full regression и независимая reader evaluation
не выполнялись. B1/B2 research Reds не включены в legacy parity inventory: они
проверяют отдельно blocked prototype и остаются явными blockers, не исключены
из diagnostic inventory и не переклассифицированы в PASS.

## Следующий переход — требуется идентификация Gate B

Пользователь попросил дойти до Gate B. Поиск `Gate B` / `GATE_B` / `Gate.?B`
во всём `roadmap` не нашёл такого gate. В действующем плане есть Gate R, Gate A
и шаги 00–09. Новое название не трактуется как разрешение обхода Gate A.

Изолированная проверка 01–04 закончена. Для дальнейшего перехода нужен документ
или критерии Gate B от пользователя; gate не придуман и не объявлен пройденным.

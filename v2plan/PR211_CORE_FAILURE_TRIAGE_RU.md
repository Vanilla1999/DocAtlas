# PR #211: исторический core failure triage на b687

Дата: 2026-10-08. Read-only audit существующего JUnit и текущих source contracts.
Этот отчёт описывает **baseline до CI на `5bf3b004`**, не состояние нового HEAD.
Production/tests/gates этим audit не менялись; repository imports, pytest,
subprocess test harnesses и retrieval pilots не запускались.

## Evidence и границы выводов

- [CI run 37802068737, core Python 3.12 job 113396563098](https://github.com/Vanilla1999/DocAtlas/actions/runs/37802068737/job/113396563098).
- PR HEAD: `b68759e65f52317928ba22166248e679098024ae`.
- Выполненный checkout/merge SHA: `964056442f67b0d913310d3f8a295deb3c90263e`.
- JUnit artifact ID: `11561493464`; ZIP SHA256:
  `6177b77507924cc80c2582292199caaac3170f6865edbf5f3b7ce196aaba8432`.
- XML: `b687-core-3.12.xml`, SHA256
  `1c54a1cbdee6072a0446e3644c5595aaf5a4bfbcd9de94fafbe48a649834666e`.
- Workspace XML:
  `/workspace/scratch/5ecb5f548321/pr211-acceptance-artifacts/b687-core-3.12.xml`.
- Производный ledger, сохраняющий исходные classname/name/message/detail:
  `/workspace/scratch/5ecb5f548321/pr211-acceptance-artifacts/b687-core-3.12-cases.json`.

Итог XML: **8505 cases = 5983 PASS + 2451 FAIL + 61 ERROR + 10 SKIP**.
Статический разбор ниже выделяет непересекающиеся cohorts:
**1013 FAIL + все 61 ERROR**. Остальные **1438 FAIL** не получили индивидуальной
квалификации. Cohort count не равен количеству обещанных простых исправлений.
Это не полная автоматическая классификация причин всех 2451 failures.

У прочитанных question/query/alias/admission-local-binding, ingest/sync,
SourceBoundary, ActionPacket/selection producers и основных capture helpers
не было diff относительно локального `21fe472d983f394130849d6fd4e582043d58e9ba`.
Это подтверждает неизменность конкретных source files, **не доказывает**, что
все runtime failures были pre-existing. Полного сопоставимого executed roster
core на 21fe в этом audit нет.

## Непересекающийся accounting

| Группа | FAIL | ERROR | Правило отбора |
|---|---:|---:|---|
| Question planning / aliases | 509 | 0 | Восемь modules ниже; из исходных 512 исключены три mutation PermissionError. |
| Semantic admission | 195 | 0 | Восемь modules ниже; из исходных 199 исключены четыре exact capture-assert failures. |
| Ingest/sync без mutation grant | 146 | 0 | Точная PermissionError signature: 103 sync + 43 ingest. |
| Пустой captured projector | 62 | 61 | Exact failing location для 62 FAIL; отдельно все 61 setup ERROR. |
| Source membership candidates | 101 | 0 | Четыре modules ниже с явным исключением двух recovery-text failures. |
| **Итого** | **1013** | **61** | Union по исходным `(classname, name)`; пересечения исключены. |
| **FAIL без индивидуального разбора** | **1438** | — | `2451 - 1013`; не объявлены допустимыми или исправленными. |

### Восемь planner modules: raw cohort 512

| Исходный JUnit classname | FAIL до исключения overlap |
|---|---:|
| `tests.docs.test_context7_style_project_chat` | 45 |
| `tests.docs.test_direct_question_retrieval_intents` | 36 |
| `tests.docs.test_documentation_query_plan` | 47 |
| `tests.docs.test_hyphenated_query_identity` | 17 |
| `tests.docs.test_project_query_intent` | 27 |
| `tests.docs.test_question_plan_v4` | 26 |
| `tests.docs.test_question_span_coverage` | 302 |
| `tests.docs.test_russian_inquiry_intent` | 12 |

Один PermissionError в context7 и два в documentation_query_plan относятся к
mutation cohort. Поэтому непересекающееся число этой группы — **509**.
В question_span_coverage **288** случаев — параметризация одного
`test_known_frame_never_authorizes_an_unknown_tail`, который сначала требует
распознанного известного prefix; это не 288 независимых production дефектов.

### Восемь admission modules: raw cohort 199

| Исходный JUnit classname | FAIL до исключения overlap |
|---|---:|
| `tests.docs.test_admission_guard_composition` | 16 |
| `tests.docs.test_admission_local_binding` | 42 |
| `tests.docs.test_admission_mapping_assignments` | 17 |
| `tests.docs.test_admission_meaning` | 30 |
| `tests.docs.test_admission_relation_safety` | 24 |
| `tests.docs.test_admission_relation_witnesses` | 64 |
| `tests.docs.test_admission_role_boundaries` | 4 |
| `tests.docs.test_admission_subject_binding` | 2 |

Capture-assert overlap: guard_composition 1, relation_witnesses 2,
subject_binding 1. После исключения этих четырёх — **195**.

### Точные signatures и source cohort

Mutation signature: `message.startswith("PermissionError: Project docs ")`
и наличие `no explicit mutation grant` в message. Полные причины — отказ
synchronization без validated member transaction (103) и ingestion (43).

Projector FAIL signature:
`detail.rstrip().endswith("tests/docs/_reference_binding_fixtures.py:11: AssertionError")`.
Она даёт **62**, а не 67: простое наличие `projection_attempts` в detail
встречается у 67 FAIL, но пять заканчиваются на других assertions.

Все setup ERROR: 47 с message
`failed on setup with "IndexError: list index out of range"` и 14 с
`failed on setup with "AssertionError"`. Разбивка: context_completion_guards 24,
query_block_guards 23, admission_pipeline_invariants 10,
evidence_set_source_preparation 4. Первые 47 обращаются к отсутствующим
projector_inputs/outputs[0]; последние 14 требуют projection_attempts.

Source cohort: `tests.docs.test_code_graph` 22,
`tests.docs.test_source_map` 18,
`tests.test_dictionary_exit_local_residuals` 34,
`tests.test_dictionary_exit_read_tails` 27. Из read_tails исключаются оба FAIL,
чьи name начинаются с
`test_recovery_keeps_original_fragment_without_question_synthesis`:
они относятся к сохранению/сокращению текста, а не membership.

Для воспроизведения accounting из ledger без repository imports:

```python
import json
from pathlib import Path

data = json.loads(Path("b687-core-3.12-cases.json").read_text())
failed = [c for c in data["cases"] if c["state"] == "failure"]
key = lambda c: (c["classname"], c["name"])
projector = {key(c) for c in failed if c["detail"].rstrip().endswith(
    "tests/docs/_reference_binding_fixtures.py:11: AssertionError")}
mutation = {key(c) for c in failed if c["message"].startswith(
    "PermissionError: Project docs ") and "no explicit mutation grant" in c["message"]}
planner_suffixes = {
    "context7_style_project_chat", "direct_question_retrieval_intents",
    "documentation_query_plan", "hyphenated_query_identity", "project_query_intent",
    "question_plan_v4", "question_span_coverage", "russian_inquiry_intent",
}
planner_modules = {"tests.docs.test_" + name for name in planner_suffixes}
admission_suffixes = {
    "guard_composition", "local_binding", "mapping_assignments", "meaning",
    "relation_safety", "relation_witnesses", "role_boundaries", "subject_binding",
}
admission_modules = {"tests.docs.test_admission_" + name for name in admission_suffixes}
planner = {key(c) for c in failed if c["classname"] in planner_modules} - mutation - projector
admission = {key(c) for c in failed if c["classname"] in admission_modules} - mutation - projector - planner
source_modules = {
    "tests.docs.test_code_graph", "tests.docs.test_source_map",
    "tests.test_dictionary_exit_local_residuals", "tests.test_dictionary_exit_read_tails",
}
source = {key(c) for c in failed if c["classname"] in source_modules and not (
    c["classname"] == "tests.test_dictionary_exit_read_tails" and c["name"].startswith(
        "test_recovery_keeps_original_fragment_without_question_synthesis"))}
groups = [planner, admission, mutation, projector, source]
assert [len(g) for g in groups] == [509, 195, 146, 62, 101]
assert len(set().union(*groups)) == sum(map(len, groups)) == 1013
assert len(failed) - len(set().union(*groups)) == 1438
assert sum(c["state"] == "error" for c in data["cases"]) == 61
```

При построении pytest node IDs нельзя слепо заменять все точки classname на `/`:
в общем core roster есть class-qualified cases. Нужно взять наиболее длинный
prefix, существующий как repository `.py` file, а оставшиеся class names сохранить
через `::`. Accounting выше использует исходные classname/name без преобразований.

## Первые причины и допустимый следующий шаг

1. **Question semantics/aliases.**
   [QuestionPlan](../docmancer/docs/domain/question_plan.py) оставляет untyped
   вопрос unresolved; [query planner](../docmancer/docs/domain/documentation_query_plan.py)
   сохраняет original/explicit lookups, а
   [alias producer](../docmancer/docs/domain/project_retrieval_intent.py) не выводит
   поисковые aliases. Пример:
   `tests/docs/test_question_span_coverage.py::test_governance_question_models_scope_and_every_including_facet`.
   Нужны contract-based successors с явными входами и meaningful negatives.
   Возвращать словари, скрытые rewrites/paraphrases ради PASS нельзя.

2. **Semantic admission.**
   Часть cases не получает retrieval_need уже на planner boundary; другие требуют
   True/False от compatibility witness, который сохраняет неизвестность.
   [default_local_witness](../docmancer/docs/domain/admission_local_binding.py)
   возвращает `(None, ())`, а
   [choose_admission](../docmancer/docs/domain/admission_contract.py) не превращает
   неизвестный witness и legacy overlap в authority. Пример:
   `tests/docs/test_admission_local_binding.py::test_direct_default_statement_is_a_witness[RelayClient-7]`.
   Это не blanket fixture migration: нужны typed positive/absent/unknown controls.
   Восстановление qualification/admission полезных partial facts пересекается с
   явно отложенной retrieval работой.

3. **Mutation grants.**
   [Ingest](../docmancer/docs/application/_project_docs_service_part01.py) и
   [sync](../docmancer/docs/application/_project_docs_service_part02.py) имеют
   отдельный `mutation=...` путь через validated member transaction. Пример:
   `tests/docs/test_context7_style_project_chat.py::test_current_docatlas_index_persists_across_service_restart_without_resync`.
   Fixture-owned indexing для read tests может мигрировать на этот реальный
   контракт; прежние auto-sync, dedup/orphan deletion и обход consent не следуют
   из такого разрешения. Suppress PermissionError не является исправлением.

4. **Пустой captured projector.**
   Примеры:
   `tests/docs/test_admission_guard_composition.py::test_native_indexed_need_is_qualified_without_claiming_a_complete_answer`
   и ERROR
   `tests/docs/test_context_completion_guards.py::test_empty_packet_only_gains_inspection_not_support_or_source_quotes`.
   Подтверждена первая граница — нет captured attempts/stages. Observer патчит
   правильный `context_tools.project_docs_context`; handler также может вернуть
   explicit delivery veto до projector. Причина отсутствия вызова не доказана
   для каждого seed без фактического raw/public payload. Поэтому нельзя объявить
   monkeypatch устаревшим или заменить indexing/consent/source guards пустыми
   fallback arrays. Сначала нужна разрешённая диагностика причины veto.

5. **Finite source membership.**
   [SourceBoundary](../docmancer/docs/domain/source_boundary.py) требует literal
   `code_files`. Повторяющийся первый барьер — fixture создал source files,
   но не объявил их membership. Пример:
   `tests/docs/test_code_graph.py::test_build_project_code_graph_links_python_local_import_and_reference`.
   Это кандидат на узкие fixture slices с положительным реальным чтением,
   refs/hash/bounds и denied controls. **Не все 101 сертифицированы как чистые
   fixtures:** в cohort также есть ожидания generated opt-in из prose,
   dependency identity и semantic ranking. Их нельзя восстанавливать вместе
   с объявлением files.

## Отдельный ABI срез: неаддитивная заметка

Ещё одна точная signature selection даёт **30 FAIL**:

- 18: `TypeError: build_action_packet() got an unexpected keyword argument 'max_tokens'`;
- 12: `TypeError: patch_selection_config() takes 0 positional arguments but 1 was given`.

Это поперечный, потенциально пересекающийся с другими классификациями срез;
его нельзя прибавлять к 1013 без union по node identity. Он не является новой
обещанной группой полностью безопасных fixes. Устранение ABI TypeError может
открыть дальнейшие conflicts: старые DTO keys, удалённые output caps и inferred
mutation semantics. Нужны fidelity successors и сохранение no-edit-authority,
а не только удаление аргумента или expected→actual replacement.

## Открытые blockers

Остаются перечисленные contract families, неизвестная причина early delivery
veto в capture seeds, 1438 FAIL без индивидуальной квалификации, действующие
footprint/retrieval/downstream gates и совместный run на новом финальном SHA.
Исходный 800-token retrieval criterion и
[отложенные направления](after-merge/RETRIEVAL_DEFERRED_ANALYSIS_RU.md)
этим документом не изменяются. Ни отсутствие нового source diff, ни маленькие
успешные slices не превращают исторический core FAIL в merge/release readiness.

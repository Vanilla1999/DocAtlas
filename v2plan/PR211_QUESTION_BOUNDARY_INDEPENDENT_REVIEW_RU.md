# PR #211: независимый review question boundary migrations

Дата: 2026-10-08. Reviewer: отдельный agent, не автор этого test slice.
База: `df9b682fdd13d8f4d1c5bff6cc4bfc0286e5f8ce`.

**Вердикт: APPROVE** ограниченного producer-boundary slice для совместного CI.
Новые runtime outcomes **NOT RUN** в этом review; merge acceptance не утверждается.

## Что проверено независимо

Прочитан полный diff `tests/docs/test_question_span_coverage.py` относительно
базы, тела изменённых и оставшихся tests, а также реальные producers:
QuestionPlan/QuestionPlan DTO, RetrievalNeed, ProjectAnswerContract,
DocumentationQueryPlan, paragraph scanner, evidence_requirements и selector
wrapper. Файлы production ниже побайтно совпадают с базой.

Старый unsupported-clause reason больше не соответствует raw-question API:
`compile_question_plan` сохраняет полный исходный ввод в пределах существующих
4000 символов, возвращает generic unresolved semantics и не выводит facets.
`retrieval_needs` сохраняет весь вопрос в одном literal span, не назначает
subject/relation/context из prose. ProjectAnswerContract хеширует полный input,
не выводит obligations/hints/subjects, не авторизует answer certification.
Вопросы этого slice короче действующего input ceiling.

Поэтому требование old semantic reason или распознанного prefix нельзя считать
действующим security contract. Successor проверяет его полезный инвариант:
не потерять tail/wrapper/raw identity и не выдать части запроса самостоятельную
semantic/answer authority. Ни old vocabulary, ни hidden rewrite не восстановлены.

## Разбор шести migrations

| Existing test function | Concrete cases | Review |
|---|---:|---|
| `test_known_frame_never_authorizes_an_unknown_tail` | 288 | Все tails остаются в raw clause/need span и question hash. Нет facets/consumed spans/обязательств. Реальный explicit prefix lookup присутствует отдельно от mandatory original query, без parent coverage или component contract. |
| `test_unresolved_residue_reaches_the_requirements_gate` | 3 | Проверяется отсутствие inferred mandatory facets и сохранённая incomplete component scope. Положительный explicit evidence path остаётся mandatory с точным source/provenance; forged inferred provenance отклоняется реальным builder. |
| `test_legacy_behavior_usage_fallback_rejects_extra_compound_tail` | 1 | Проверяет общий raw/span/no-authority contract через helper, а не удалённый inferred behavior/usage parser. |
| `test_plan_retains_exact_source_spans_after_wrapper_and_whitespace_normalization` | 1 | Теперь весь исходный wrapper/whitespace сохраняется в need span/query и влияет на hash. Старое trimmed facet inference не восстанавливается. |
| `test_clause_scanner_preserves_original_offsets_and_noun_coordination` | 1 | Punctuation не превращается в semantic split; одновременно настоящий double-newline split имеет две строки с exact original offsets. |
| `test_russian_ambiguous_inventory_and_action_frames_fail_closed` | 1 | Для трёх прежних inputs нет facets/authority, полный raw span сохранён. Старая vocabulary-specific classification явно отсутствует. |

Всего **295** существующих concrete cases. Это не новые случаи и не сокращение
параметризации; слова, tails, questions и decorators исходного test inventory
сохранены. Positive controls препятствуют пустому facade, который просто
удаляет все inputs и всегда возвращает false: explicit lookup и evidence-path
должны существовать и иметь правильные provenance/coverage, paragraph split
должен вернуть настоящие exact spans.

## Граница старого requirements gate

`component_scope_complete=False` сам по себе **не является универсальным
селекторным veto**: прочитанный `select_evidence` не использует этот флаг напрямую
как запрет всех assignments. Поэтому этот slice нельзя описывать как доказанное
восстановление прежнего semantic entailment либо полного downstream answer gate.

Одобрение относится к producer boundary в текущем conservative contract:
полный raw request, отсутствие invented semantics, explicit requirement retention,
no parent coverage, отдельный answer-authorization API false. Настоящая
sufficiency/source/assignment validation остаётся в своих неизменённых suites и
обязательных gates; данные migrations её не ослабляют и не объявляют пройденной.

Этот предел не спрятан удалением конфликтующих тестов. Остались AST-exact:

- два governance-positive tests;
- один governance nested-tail negative, бывший PASS;
- полный compounds/paraphrases/premise/local-proof test;
- четыре legacy-fallback concrete cases и вызов `frozen_ownership_mismatches()`.

На базе это **7 FAIL + 1 PASS**. Семантический конфликт этих 7 cases остаётся
видимым в CI и требует отдельной contract qualification, без ожидания blanket PASS.

## Статическая проверка и inventory

Независимый stdlib AST comparison подтвердил:

- **11** исходных test functions сохранены, ровно **6** изменены;
- arguments и parameter decorators всех functions AST-identical;
- `_ADVERSARIAL_TAILS` и parameter grids не менялись;
- исходный JUnit содержит **303 = 302 FAIL + 1 PASS** для module;
- шесть changed functions соответствуют ровно **295** cases;
- оставшиеся пять function bodies AST-identical;
- module AST parse PASS, 376 строк, внутри ceiling 1000;
- imports/pytest/test subprocesses/provider/client calls/dependency installations
  в review не выполнялись.

Code, CI gate, selector, admission и retrieval producer не редактировались reviewer.
Review не заменяет фактический совместный CI на опубликованном HEAD.

## Frozen hashes

| Файл | SHA256 |
|---|---|
| `tests/docs/test_question_span_coverage.py` | `7e487c6927677f0bb0a4ad8a0a6424e51e97b1f11a6ad0d1f7f272a50a98d6b7` |
| `docmancer/docs/domain/question_plan.py` | `90588252e7a739061250df77f4ec79ccaa81d2342ab3f51e554f4170f1eb6831` |
| `docmancer/docs/domain/question_retrieval_needs.py` | `2542795f8826982fc83510e64e30de22127dec621f500ac851301672ba4e8b70` |
| `docmancer/docs/domain/_project_answer_contract_part02.py` | `8b881b07cdea5dbe6f078d0e70504b7d4aa20faa983bf46ffd5a67fc9e0e134a` |
| `docmancer/docs/domain/project_answer_contract.py` | `58667c5798abd763f1c2196829a683cc6a856b39cad1a6c5eda49e6d49fa2439` |
| `docmancer/docs/domain/documentation_query_plan.py` | `fa6d2990d3d5673b8396f7a1c0ab4cabe83f8e2dd5da185354fb5aefc0a95220` |
| `docmancer/docs/domain/question_frame_core.py` | `bab02ded393e11cbe51bdabbd5ae3fd405d7b383400d86244232693f80a6c571` |
| `docmancer/docs/application/evidence_requirements.py` | `d66cc76b248099c0d5dded1e1c973efd5be2103b33b949183534b6b1bdd87e57` |
| `docmancer/docs/application/_evidence_selection_shared.py` | `e91afef0a75513ad4ea38134999cd78d8bc3c72c07f8e36fb1d94d67c042ce8e` |
| `docmancer/docs/application/_evidence_selection_part03.py` | `dfba410e57597fc99d318aa87c1787418b1fee21f1cd4095485aac6fca8b6264` |

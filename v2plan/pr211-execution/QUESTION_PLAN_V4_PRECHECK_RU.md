# PR211: precheck сокращения question_plan_v4

Статус: **подготовлено для независимого review; runtime pending; 26 cases не удалены**.
База: опубликованный PR HEAD `0065ce62cacaa31a41e4567717e3c67d602f578b`,
tree `628bb7a2eb16f740ce84384925531040f7ec9f5e`.
Четыре owning source SHA перепроверены через exact-ref GitHub reads.

## Решение по семье

Старый модуль содержит26 локальных test functions и собирает ещё2 через
`_question_plan_clause_coverage.py`: всего28 cases. Исторический CI121 показывал26 FAIL/2 PASS;
это переданное root наблюдение, а не новый прогон этого slice.

Кандидаты на последующее удаление —24 локальные функции и2 reexports.
Они ожидают удалённую компиляцию NL в subjects, semantic relations, mandatory facets,
concept aliases, expected values, particular unresolved diagnostics и положительные
prose proofs. Текущий `build_project_answer_contract`54ab012 связывает полный исходный
question hash и input diagnostics, но не создаёт такие поля. Обе функции answer
authorization в073ddadc возвращаютFalse. Это смена контракта, не эквивалентное
исполнение архивированных вопросов.

Две действующие проверки остаются побайтно:

- `test_code_symbol_aliases_may_widen_retrieval_but_not_proof_shape`: prose spelling
  не заменяет точную форму code symbol.
- `test_code_block_units_preserve_exact_source_spans_for_projection`: source slice
  и materialized code block совпадают с исходными координатами.

Оба исходных файла архивируются целиком. Вопросы, тела, старые assertions и imports
не заменяются новым gold. Helpers `_rows`/`_unit` и остальные API imports сейчас не
меняются. Будущее удаление двух test reexports требует отдельной явной правки после
проверки consumers; обхода через `__test__` не предлагается.

## Уже существующие successors

| Обязательство | Существующее покрытие |
|---|---|
| Полный raw вопрос, неизвестный хвост, Unicode, offsets | compact question_span_coverage33 + dictionary_exit_legacy_compilers49 |
| Отсутствие inferred facets/semantic adapters/hidden delegation | текущие51 directed faults, включая отдельные API и Unicode branches |
| Original и explicit host lookup остаются раздельными | existing raw/hash/original-credit/parent-credit/path guards |
| Code-symbol форма и code-block spans | две сохраняемые функции исходного модуля |
| Явное literal equality, source identity/span/condition, отсутствие prose authority | весь существующий residual_proofs module остаётся без изменений |
| Явные host evidence-path requirements | существующая positive/negative проверка test_unresolved_residue_reaches_the_requirements_gate |

Manifest8f92ea6d содержит51 mutations,43 различных guard strings и15 различных
killer selectors. Полный minimal existing killer roster записан в crosswalk.
Имеющийся comparison запускает2 healthy baselines —historical303+399 иcompact33+49 —
и каждую mutation в обоих modes: **104 child reports**. Менять этот протокол или
добавлять новый обычный wrapper не нужно.

Root наблюдал SUCCESS шага16 на126, advanced job114127988180. Individual104 receipts
на момент подготовки не просмотрены. Summary `comparison.json` не содержит
всех cases/source_identity; он не заменяет отдельные evidence/inside-pytest import
records. Их отображением занимается отдельный read-only reader slice.

Эти51 faults не запускают residual_proofs и не доказывают source facts, retrieval
quality или успешность исходного вопроса. Сохранённые residual/source guards
не удаляются и не получают выдуманный mutation credit.

## Один конкретный пробел и один targeted fault

QuestionPlan и ProjectAnswerContract — разные производственные пути.
Existing `literal_inferred_facets` портит QuestionPlan; он не моделирует повторную
генерацию obligation непосредственно в независимом answer-contract builder.

В существующем `_assert_literal_context_boundary` добавлена только метка:

```python
assert not contract.proof_obligations, "critical_question_contract_no_inferred_obligations"
```

Выражение, порядок assertions, старые labels,11 definitions, все fixtures и
decorators остались прежними. Inverse одной замены восстановил исходник77efcc114
побайтно; exact blob roundtrip подтверждён. Обычные33/303 cases и diagnostic
node hash не меняются.

Предложенный critical fault `question_contract_does_not_infer_obligations`
меняет единственный return-конструктор в54ab012: локально импортирует существующий
`ProofObligation` и помещает в `proof_obligations` одну валидную definition
obligation с subject `shared browser` и полным исходным span
`[0, len(source_question)]`. Это намеренная ошибка только во временном mutant
checkout; production source основного дерева не изменяется.

DTO23ba467 проверен по исходнику: ID и subject допустимой длины; raw query span
непустой, положительный и согласован с тем же вопросом. Остальные query/contract
поля остаются прежними. Поэтому failure должен приходить от запрета inferred
obligation, а не от исключения конструктора.

Killer — уже существующий непараметризованный
`tests/docs/test_question_span_coverage.py::test_governance_question_models_scope_and_every_including_facet`.
Ожидание: **ровно1 intended assertion failure,0 errors/skips**.
Перед ним проходят прежние raw QuestionPlan/retrieval-need checks; следующее
`not contract.proof_obligations` первым видит fault. Новый pytest function не нужен.

Exact old/new anchor, base blob и hashes включены в crosswalk:

- before SHA256: `8b881b07cdea5dbe6f078d0e70504b7d4aa20faa983bf46ffd5a67fc9e0e134a`;
- after SHA256: `a53ba3b53663c5e827604585a4d19c1146dc3702ec8be1313377a624e3dd7543`;
- anchor matches:1.

Root владеет append в critical runner: текущая конфигурация60 cases/37 faults →
план61/38. Эти числа — **цель следующего CI**, не PASS. Literal51 manifest/helper и
исторический/compact protocol остаются без изменений.

## Consumers: проверено и не доказано

На exact refs прочитаны current CI, direct-question, Task33 и critical selectors;
прямых ссылок на удаляемые function names в них не найдено.
Workflow `pr174-review-cleanup.yml` выбирает весь `test_question_plan_v4.py`;
этот путь останется с двумя действующими тестами. Текущие pytest.ini, pyproject,
conftest и owning diagnostic labels также прочитаны.

Current main-module roster hash:
`ccd2869f6b9bc2c47499fde3ff5efb2fb806dfaa5daa6468e176ea29ad26c8a5`.
Он совпал с28 исходными collected names, включая два explicit reexports.
Здесь source spans и hashes проверялись обработкой текста/JSON; Python, AST,
imports и pytest локально не запускались.

Default-branch search использовался только для выявления кандидатов; содержимое
проверенных consumers читалось по текущему ref. Такой поиск не доказывает
отсутствие новых PR-only imports. Прежний118-file DQP/relation audit — смежная
история, а не автоматически полный audit этой семьи. Ограничение отражено в
crosswalk; helpers/imports и все26 candidates сейчас остаются нетронутыми.

## Exact manifest

Все файлы mode100644. Архивы используют исходные Git blobs без перекодирования.

| Path | Base → proposed blob |
|---|---|
| tests/docs/test_question_span_coverage.py | 77efcc114ba4f170f50bc8b9a4cd2bd41b68a846 → f8d5a10d8a251c1394b660c6e6e4cf9a6e96d72a |
| eval/task_level/contract_history/question_plan_v4_inputs.py.txt | NEW → a7cadec822a464a19bf917d69e28e9cc6b0b1496 |
| eval/task_level/contract_history/question_plan_v4_clause_inputs.py.txt | NEW → 4898e3459e2504cf07f9bacfae8fd6769bdd9c79 |
| eval/task_level/contract_history/question_plan_v4_retirement.json | NEW → 94d895ad0fb6d53144a99e7be0f012bd869ffe1f |
| v2plan/pr211-execution/QUESTION_PLAN_V4_PRECHECK_RU.md | NEW → этот файл |

Основной архив45553 UTF-8 bytes, SHA256
`85a0de4b9bb158bbc755272ae3dee387dd77c83f46c97c8a2895eabb26a3adf3`.
Shared архив2782 bytes, SHA256
`e691a185f11accce420caf16e5c013fb7cf629b1c466c51bda29ff2d4b25c31e`.

Перед удалением нужны собственный healthy critical baseline и intended kill,
individual reused literal evidence, завершённый consumer audit и проверка
сохранённых guards. После удаления — ordinary collection/required CI на
конечном SHA. Из статического сокращения cases не выводится измеренное ускорение
или полный PASS PR211.

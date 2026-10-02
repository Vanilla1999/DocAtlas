# M2: первый slice — Unicode query terms

В `documentation_query_terms` класс Latin/Cyrillic символов заменён на
Unicode `\w` с сохранением technical punctuation (`.:/+-`).
Испанские precomposed accents не обрезаются, JA/AR text не теряется
из-за whitelist алфавитов; mixed-script запросы сохраняют tokens.

Это намеренное изменение terms для ранее исключённых символов.
EN/RU request words, minimum length, casefold, лимит 32 terms и
enumeration rewrite пока **сохранены**. Полная M2 migration не выполнена.
`\w` не решает CJK segmentation, translation или combining-mark normalization.
Другие script-specific regex в pipeline ещё требуют миграции.

## Red → Green

Новый regression до правки: **1 failed, 43 passed** — `además` и
`documentación` обрезались. Тест также проверяет JA/AR и mixed-script запрос.
Technical literals проверяются отдельно.

Набор после правки: **274 passed**:

```text
tests/test_source_metadata_eligibility.py
tests/docs/test_documentation_query_plan.py
tests/docs/test_hyphenated_query_identity.py
tests/docs/test_independent_query_probes.py
tests/docs/test_cli_literal_query_binding.py
tests/docs/test_query_reference_roles.py
tests/docs/test_evidence_qualification.py
tests/docs/test_admission_guard_composition.py
```

Python соседнего `.venv`, production modules текущего worktree.
Installed MCP recall и host answer quality этим не измерены.
Guards, providers, caps, budgets и permissions не отключались.

## Дальше

### Продолжение: optional lookup vocabulary удалён

Удалён `_SUPPLEMENTAL_FUNCTION_WORDS` из `query_terms.py`. Optional probe
проверяется структурно: exact technical anchor либо token длиной >=4.
Это прежний lexical floor, не языковой словарь и не semantic-usefulness proof.
Он всё ещё ограничивает короткие NL слова; универсальный tokenizer не заявляется.

Первый новый тест до удаления: **1 failed, 49 passed**. После удаления существующий
budget regression выявил `happens` в optional slots (**1 failed, 169 passed**).
Не добавлен новый blacklist: при готовых relation groups planner пропускает
однотокенные нетехнические optional probes, сохраняя exact anchors. Это structural
prioritization; он может убрать полезный однотокенный hint, что требует quality
измерения, а не объявления универсальной семантики.

Planning набор: **208 passed**. Расширенный planning/projection/window/reference/
trust/patch набор: **475 passed**. После добавления multi-script structural-slot
controls focused набор: **66 passed**. Эти controls подтверждают одинаковое
правило для EN/RU/AR/JA и сохранение `ALPHA_KEY`, не cross-language recall.

Ручной `_REQUEST_FRAMING_TERMS` и enumeration rewriting ещё остаются: удалять их
без проверки downstream ratio/coverage опасно. Следующая broad migration должна
заменить эту mixed relevance/support границу, не отключить все constraints.

### Продолжение: удалён window stopword vocabulary

Из `context_windows` удалён `_QUERY_STOP_WORDS`: window-focus больше не
исключает `project/проект`, `работает` и другие слова по ручному EN/RU списку.
Minimum length и лимиты окна остаются прежними. Это изменяет scoring окна,
не eligibility источника или semantic support.

Regression до удаления: **1 failed, 47 passed**. После: **277 passed** —
предыдущий оконный/guard набор плюс context-ranking-regressions,
docs-context-budget-reserve и context-loss-boundaries.
Это локальные regressions, не holdout precision/recall измерение: добавление
ранее исключённых common words потенциально меняет фокус snippets и требует
общей quality проверки перед rollout. Остальные stopword vocabularies ещё остаются.

### Продолжение: source window focus

В `context_windows._query_terms` также заменён Latin/Cyrillic whitelist на
`[\w.-]{4,}`. EN/RU stopwords пока сохранены. Before regression:
**1 failed, 46 passed** — selector выбрал background вместо источникового
предложения с `documentación`. После правки тот же тест проверяет ES/JA/AR
witness, точное равенство source slice и прежний limit=100.

Оконный/guard набор: **198 passed** — source metadata module,
context-sentence-windows, context-span-growth, compact-context-blocks,
context-preservation, bound-table-qualification, independent-query-probes,
evidence-qualification, admission-guard-composition, context-trust-gates,
patch-context-public. Сохранность таблиц/списков и budgets не заменяет
многоязычную оценку смысловой полноты: здесь проверены локальные spans.

### Продолжение: downstream terms

Та же потеря script/accents устранена в fallback terms `qualify_evidence`
и distinctive terms `independent_query_probes`: `[\w.-]{4,}` вместо
Latin/Cyrillic whitelist. Набор technical punctuation и minimum length сохранены.
Lexical ratio, distinctive requirement и source guards не отключались.

Два новых regressions до правки: **2 failed, 44 passed**. После правки:
**310 passed** (предыдущие восемь модулей плюс discovery-independent,
bound-table, context-trust и patch-context-public).
Проверены accents, JA/AR body matching, independent host lookup и отрицательные
controls: общий term не создаёт distinctive lookup, unrelated body не проходит.
Это lexical matching при одинаковом языке term/body, не cross-language evidence.

Завершить карту script restrictions и callers, добавить regressions до удаления
ручных NL gates. Для multilingual recall нужен relevance path, не только Unicode
extraction. Шаг 07 открыт; шаг 08 не начат. Новые изменения пока без коммита.

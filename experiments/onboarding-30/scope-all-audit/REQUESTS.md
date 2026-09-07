# Whole-repository onboarding: explicit scope and 30 questions

## Scope correction

The public `get_docs_context` schema in `docmancer/mcp/_docs_server_tool_data.py` distinguishes:

- `project`: repository-level documents only;
- `module`: one module, with its exact `module_path`;
- `all`: repository-level and module documents when no module filter is supplied.

For the whole-repository questions below, use `scope="all"`, the same exact `project_path`, and no `module_path`. This does not authorize cross-project retrieval. Project identity, source ownership, freshness, risk flags, exact identifiers, source spans and hashes remain enforced.

A previous exploratory onboarding attempt used `scope="project"` and consequently excluded the module documents needed for architecture and internal-flow questions. That attempt cannot establish that the missing module documents were lost in selection. Do not repair correct scope filtering by weakening qualification or adding synonyms.

This is a separate exploratory request inventory, NOT a change to any frozen evaluator, corpus, threshold, or legacy gate. Do not relabel results from `project` as results from `all`; retain the original request arguments and revision with every payload.

## Interpretation and limits

Use one ordinary initial `get_docs_context` call per question. Preserve the original question. Any host-generated lookup strings must be recorded before the call; distinguish them from the original question and from later retries. The existing maximum is five lookup strings. Results remain bounded to three sources and 800 estimated tokens.

Record all responses, including `insufficient_evidence`, execution errors and unhelpful `status=ok` results. `covered_query_ids` is retrieval attribution, not semantic completeness. Do not synthesize missing facts, combine unrelated payloads into an apparent single response, or use successful unit tests as evidence of successful onboarding.

Qualitative review should distinguish sufficient, partial, and unhelpful context. It is not an independent weak-model answer benchmark. A coordinator-written example answer must be labeled separately from the actual MCP payload. These 30 questions are not the older natural 15/exposed 5 corpus; their scores must not replace that baseline.

## Questions

1. Что такое DocAtlas и какую проблему разработчика он решает?
2. С чего начать знакомство с репозиторием и какие документы прочитать первыми?
3. Какая версия Python нужна и как установить зависимости проекта?
4. Как установить DocAtlas локально и проверить запуск?
5. Как создать индекс, добавить документы и выполнить первый поиск?
6. Какие инструменты доступны в стандартном Docs MCP и зачем нужен каждый?
7. Что передавать в первый get_docs_context при знакомстве с проектом?
8. Когда следует вызывать prepare_docs, а когда не следует?
9. Когда нужен docs_status и что он показывает?
10. Чем docs_context отличается от подтверждённого ответа и разрешения менять код?
11. Как проходит get_docs_context от MCP-входа до выбранных источников?
12. За что отвечают application, domain, infrastructure и MCP adapter?
13. Кто ищет кандидатов, а кто проверяет пригодность доказательств?
14. Зачем нужен DocumentationQueryPlan и почему исходный вопрос нельзя менять?
15. Что такое lookup_queries, сколько их допускается и гарантируют ли они полный ответ?
16. Что означает covered_query_ids и чего он не доказывает?
17. Как настроить документацию в нестандартных каталогах?
18. Что происходит при ошибке в docatlas.project-docs.yaml?
19. Как обновлять индекс после изменения, переименования и удаления документа?
20. Как проверить актуальность индексированной документации?
21. Как изолируются данные разных репозиториев?
22. Что является источником истины: документы или индекс?
23. Как сначала посмотреть план очистки только производного индекса?
24. Как индексировать без сети и без загрузки векторных моделей?
25. Как документы делятся на родительские секции и дочерние фрагменты?
26. Какие ограничения на число источников и размер project docs_context?
27. Что делать, если контекст найден, но часть вопроса осталась без ответа?
28. Может ли найденный документ давать агенту команды или разрешения?
29. Что прочитать и какие тесты запустить перед первым PR?
30. Как добавить regression-тест retrieval, не меняя frozen corpus и thresholds?

## Publication boundary

This file records the request contract and questions; it does not claim any run result or that the branch passes its gates. Runtime changes and their test logs must be inspected separately. The query-anchor fix was published in `d03c4c6`; locally prepared table-window/span-retention changes must not be assumed published. In particular, the prior tool denial for writing `context_windows.py` is not permission to publish the same change by another route.

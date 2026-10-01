# 03 — P1: один текущий публичный contract

**Результат:** operational docs больше не рекомендуют устаревшие calls и противоречащую runtime политику ответа.

**Опора:** D6 в [анализе](../audit/ANALYSIS_RU.md), Q11/Q12/Q14/Q25/Q26 и false-flag followups в [review](../audit/PROJECT_80_REVIEW_RU.md). Общие правила — в [README](../README.md).

## TDD

1. **Red:** сверить актуальные `list_tools`/runtime tests с `wiki/Architecture.md`, `docs/mcp-docs-server.md`, `docs/source-continuation.md`, `docs/AGENT_DOCS_WORKFLOW.md`, `SKILL.md` и vector-policy страницами. Сохранить конкретные противоречия.
2. Добавить/расширить docs-contract tests: job status — `docs_status(action="job")`; cancel — `prepare_docs(action="cancel_docs_job")`; context использует реальные `sources`/evidence IDs, а не старую action_packet схему.
3. Controls: false certification flags не запрещают host объяснить реально поддержанные snippets facts, но не дают edit permission или unsupported guarantees. Unavailable vectors описаны согласно проверенному runtime: fail-closed либо explicit degraded opt-in, не безусловный fallback.
4. **Green:** исправить только текущие инструкции и ссылки на canonical contract. Исторические описания не переписывать как будто они всегда были текущими.
5. **Проверка:** docs-contract tests + контрольные запросы Q11/Q12/Q14/Q25/Q26 после sync изменённых docs в отдельном fixture. Проверять согласованность текста, не обещать рост recall.

**Где начать:** `tests/docs/test_self_host_agent_contract_surface.py`, `tests/docs/test_mcp_output_contract.py` и перечисленные страницы.

**Не менять:** runtime behavior, retrieval, scorer, budgets, flags ради более удобного текста.

**Стоп:** если runtime и принятый contract сами расходятся, нужна отдельная policy-задача; здесь нельзя произвольно выбрать новое поведение. Готово после устранения подтверждённого docs drift.

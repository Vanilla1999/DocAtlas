# Prompt 07 — Merged Execution Roadmap

Ты — principal product/engineering lead для devtools и AI coding agent infrastructure.

## Контекст

У нас есть Docmancer и несколько предварительных аналитических материалов:

1. Базовая выжимка по продукту (`DOCMANCER_PRODUCT_BRIEF.md`).
2. Аналитический roadmap от сильной модели.
3. Отдельные deep-dive ответы по направлениям:
   - Agent-proof MCP Docs UX;
   - Registry/source identity;
   - Product positioning;
   - Project-aware version resolution;
   - Retrieval quality/eval;
   - First-run DX/doctor.

## Задача

Собери из всех материалов единый **execution roadmap**, пригодный для превращения в GitHub issues, milestones и PR plan.

## Что нужно выдать

1. **Executive summary**
   - Главная стратегия.
   - Главный риск.
   - Главный first milestone.

2. **Prioritized epics**
   Для каждого epic:
   - name;
   - problem;
   - user value;
   - scope;
   - non-goals;
   - dependencies;
   - acceptance criteria;
   - risks;
   - estimated complexity;
   - suggested owner role.

3. **Milestones**
   - 30 days;
   - 60 days;
   - 90 days;
   - later.

4. **Must / Should / Could**
   - Продуктовые решения.
   - Engineering tasks.
   - DX/docs tasks.
   - Evaluation tasks.

5. **PR sequencing**
   - Какие PR делать первыми.
   - Какие changes должны быть isolated.
   - Где нужны migrations.
   - Где нужны tests до implementation.

6. **Technical dependencies map**
   - Registry model.
   - MCP docs server.
   - Query service.
   - Fetch/ingest pipeline.
   - Project metadata readers.
   - Eval harness.
   - CLI/doctor/docs.

7. **Quality gates**
   - Before merging.
   - Before beta.
   - Before GA.

8. **What to explicitly not do yet**
   - Чтобы избежать расползания scope.

9. **Open questions**
   - Что надо уточнить перед implementation.

10. **Final recommended next action**
    - Одна самая первая задача/PR.

## Ограничения

- Не повторяй все deep-dive ответы целиком.
- Не делай roadmap слишком PMBOK-heavy.
- Нужен engineering-actionable план.
- Приоритет: сначала закрыть agent-proof MCP docs UX и registry/source identity.

## Формат ответа

Дай roadmap в формате, который можно почти напрямую перенести в GitHub milestones/issues.

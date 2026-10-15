# Завершение оставшихся read-only веток

## Что изменено

- **Explicit lookup:** source-native режим теперь действует и при
  `lookup_queries`. Receipt разрешён только для оригинального вопроса либо
  явно переданного lookup, остаётся связан с исходным запросом, проектом,
  scope, поколением и raw span. Ни оригинальный вопрос, ни lookup не получают
  `qualified`/coverage credit только из факта retrieval.
- **Library:** удалены MMR, ручная сумма lexical/code relevance и diversity
  переранжирование из library postprocessing. В read-only `select_evidence`
  после проверки source/scope/version остаются acquisition order, точная
  identity-дедупликация и whole-item budget. Не используются semantic coverage
  ranking, near-duplicate/source caps, marginal utility и proof-completeness
  preferences. Каноническое решение остаётся context-only, answer/edit false.
- **Assembly:** удалён старый `_docs_context_projection_core.py`; публичный
  projector использует native windows, source continuation и финальную
  перепроверку. Удалены исполнявшиеся joint/query-block/recovery/parent-assembler
  модули. Без live source read выдача закрывается с `live_source_read_required`,
  а не переключается на старый эвристический renderer.
- **Candidate fallback:** удалены callback/learned selector fallback,
  category/qualification-first и повторная score/budget упаковка project
  candidates. Source/lifecycle ограничения сохранены.

Область изменения — read-only lexical documentation context. Авторизация
изменений (`patch_context`), явные source/access/lifecycle/version constraints
и отдельно настраиваемые vector/hybrid алгоритмы не объявляются эвристически
свободными и не включены в измерение. Полного удаления всех правил из всех
подсистем продукта этот отчёт не утверждает.

## Интеграция

Финальный запуск: **7 passed in 4.37s**, только:

```
tests/test_heuristic_removal_public_integration.py
tests/test_prepared_retrieval_integration.py
```

Расширен существующий lifecycle сценарий публичным запросом с explicit lookup:
проверяются исходные optics факты, provenance, отсутствие coverage/answer/edit
authority и read-only состояние. Добавлен один сценарий публичного MCP чтения
двух версий библиотеки. Setup использует настоящие registry/SQLite indexes,
поиск и selection не подменяются. Проверяются независимые version-specific
факты FIRST_ONLY/SECOND_ONLY, буквальные исходные тексты, source URLs,
exact_snapshot binding и неизменность обеих баз.

Сохраняются предыдущие интеграционные проверки scope/module/all, чужого
locator, project explicit-version отказа, stale/confirmed sync, ресурсов,
trace parity, prepared-parent parity, restart и конечного бюджета.
Это source-tree public integration, не новый installed-wheel/stdio прогон.

Unit не запускались и не добавлялись. Старые unit, импортирующие удалённые
приватные heuristic helpers, не мигрированы: весь исторический test suite
совместимым или зелёным не объявляется. Их ожидания нельзя использовать для
возврата удалённых rescue/qualification правил. `git diff --check` — PASS.

## Логи и исправления

- `remaining01.log`: 5 PASS / 1 FAIL. Факты lookup доставлены, но сохранился
  `covered_query_ids=[query-lookup-1]`. Исправлен продуктовый квалификатор:
  host_lookup имеет тот же unassessed source-only контракт, без query credit.
- `remaining02.log`: 2 PASS / 1 FAIL. Библиотечный факт, URL и версия доставлены;
  новый matcher ошибочно ожидал одно из угаданных имён version binding.
  По существующему контракту `evidence_candidates.version_rank` установлено
  точное `exact_snapshot`; исправлен только matcher. Oracle-тексты не менялись.
- `remaining03.log`: 7 PASS после замены projector и selector.
- `remaining-final.log`: 7 PASS после удаления неиспользуемых rescue модулей.

В финальном логе три включённых trace: project с 4 sources и две library
выдачи с 1 source каждая; везде answer_supported/edit_ready=false,
request status=success и trace_incomplete=false. Для library upstream
retrieved/qualification diagnostics в текущем trace отмечены missing — это
не доказательство отсутствия внутренних операций. Факты/version/read-only
доказывают assertions конечной публичной выдачи. `LOG_ANALYSIS.json` содержит
сводку и hashes сохранённых логов.

Новых benchmark/model/network/production прогонов не было; superiority и
скорость не измерялись. Изменения в рабочей ветке, без commit/push/deploy.

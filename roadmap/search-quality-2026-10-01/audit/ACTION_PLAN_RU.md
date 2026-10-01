# План действий: конечные задачи вместо бесконечного tuning

Это рекомендации по результатам аудита. Ни одна production правка этим отчётом не объявлена выполненной. Численные quality targets ниже — предлагаемые критерии следующего эксперимента, не текущие product guarantees.

## 1. P0: неиндексированный проект должен получить правильную подготовку

- Regression: новый committed clean repo, README обнаружен, индекс отсутствует.
- Public `get_docs_context` сохраняет reason `project_docs_found_not_indexed` и exact typed sync action.
- Clean Git state/HEAD и preflight digest проверяются до mutation.
- Dirty/no-Git/indeterminate state остаются confirmation-gated.
- Отдельные controls: no-docs, stale, invalid catalog, module-not-found и request to edit.
- **Готово:** воспроизведение `probe_clean_preflight.py` и installed stdio smoke проходят; generic code_search больше не заменяет подготовку доступных docs.

## 2. P0: clear → rebuild в одном процессе

- Invalidate/reinitialize только service/agent/dispatcher state данного storage identity.
- Не очищать references/agents других roots глобально.
- Проверить cached project service и default/explicit config service.
- Последовательность: sync → query → preview clear → confirm → sync → query.
- Guards: live writer lease, stale digest, unrelated storage, remote/unowned Qdrant сохраняются.
- **Готово:** нет OperationalError, schema restored, quoted source current; restart не является обязательным скрытым шагом.

## 3. P1: текущий corpus contract

- Router calls: убрать public-инструкции `get_docs_job_status`/direct `cancel_docs_job`; оставить `docs_status(action="job")` и `prepare_docs(action="cancel_docs_job")`.
- Согласовать `docs_context` false flags, host supported-part synthesis и evidence IDs.
- Согласовать unavailable vector retrieval: fail-closed versus explicit degraded mode.
- Проверить catalog authority/lifecycle для wiki, ADR, supporting analysis, plans, roadmap.
- Не удалять historical документы или user work; обозначить их роль и explicit history routing.
- **Готово:** Q11/Q12/Q14/Q25/Q26 и false-flag followups не получают противоречащие action names/answering policy.

## 4. P1: исправить измерение ДО настройки новых thresholds

- Scorer разрешает fact support несколькими проверенными citations, не синтетической склейкой нового contiguous span.
- Formatting-only equivalence не меняет числа, идентификаторы, polarity, conditions или version.
- Gold не требует незаказанные команды/примеры (uv06).
- `needs_review` не засчитывается автоматически ни в pass, ни в regression.
- Отдельный audit quote/source identity; не сравнивать evidence digest с file digest.
- **Готово:** MkDocs06/uv06 и rendered-list controls оцениваются корректно; mutation controls с неверными facts/negation по-прежнему отвергаются.

## 5. P1: candidate flow — один ограниченный эксперимент

### Протокол

1. Freeze current installed-main baseline и corpus bytes.
2. Отдельно сравнить question-only lexical, bilingual same-need lookup, multilingual dense/hybrid и reranker — не включать всё одним diff.
3. Исходный question сохраняется. Search proposals не содержат предполагаемого ответа; версии/negation/comparison sides не теряются.
4. Hard source/project/version/snapshot/stale guards одинаковы во всех lanes.
5. Saved-pool replay отдельно проверяет packing; retrieval experiment отдельно проверяет recall/caps.
6. First-loss boundary фиксируется на конкретном requested fact, а не на совпадении заголовка.

### Обязательные controls

- Q07: не создавать пустую выдачу после нахождения разрешённых relevant docs.
- Q14: current whole-JSON metadata fact не проигрывает unrelated CLI budget table.
- Q29: README instruction-trust query не превращается в generic README navigation.
- Q30: cross-project isolation не подменяется PyPI publishing checklist.
- Typer05: отрицательное имя и значимый пробел перед slash не теряются в generic boolean cap.
- Distractors: нужный exact identifier в unrelated paragraph, wrong version, stale/superseded doc, unsafe сосед, private configuration, unsupported guarantee.

### Предлагаемый stop gate

- На новой, независимо подготовленной панели — минимум 80% полного useful evidence и не менее 90% full-or-useful-partial, RU/EN gap до 10 п.п.
- Ноль hard identity/version/scope/permission regressions.
- Не менее двух других repository corpora; frozen-80 — регрессия, не главный success gate.
- Если эффекта нет или noise/unsupported admission выросло — **не активировать**; сохранить конкретную first-loss диагностику, не плодить очередной общий rewrite.

## 6. P1: уменьшить packet cost, не разрушая цитаты

- Сравнить full/lean retrieval-only DTO на одном pool, с budgets 800/1,600/2,400.
- Измерить semantic useful facts и citation entailment на whole serialized input, а не только snippet bytes.
- Не тратить slots на однотипные introductory sentences, если отсутствует requested fact.
- Сохранять source identity, exact text/spans и snapshot validation; host обязан видеть реальные concrete gaps.
- Reads только из релевантного выбранного источника для named missing fact; bounded attempts/total retained input.
- **Готово:** полезные facts растут без unsafe admissions; byte reduction отдельно от provider/task token claims.

## 7. Независимая end-to-end проверка

- Один answer/coding model и одинаковые budgets для DocAtlas/Context7/Grounded/control.
- Corpus/source/version parity либо явная категория unmatched.
- Задачи author/reviewer независимы от runtime implementation; вопросы не подправляются после первых failures.
- Метрики: answer/patch correctness, citation entailment, unsupported/wrong-version claims, total input/output/system tokens, tool calls, p50/p95 latency.
- Native server output и controlled budget lanes публикуются отдельно.
- **Готово:** реальная task usefulness установлена; тогда можно обсуждать product superiority/parity. До этого — только bounded diagnostic gains.

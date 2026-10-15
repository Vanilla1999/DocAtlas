# P0: read-path зависимости и статический baseline

Статус: **ACTIVE / частичный аудит**, 2026-10-06. Production/test contracts не изменены.
Это caller map по прочитанному source, не dynamic execution trace.

## Зафиксированная основа

- HEAD: `8d2381d8c9d18498483feaaab918d93dfee47969`.
- Branch: `integration/stage3-v2-identity-pr1`.
- Локальный `origin/main` и merge-base: `d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c`.
  Fetch не выполнялся: это не утверждение о текущем серверном main.
- Python аудита: `3.14.3`; это не утверждение об окружении прежних A/B.
- Сохраняется прежний локальный product diff удаления trust trigger; новый product diff отсутствует.
- Hashes всех 383 Python sources, `uv.lock`, `pyproject.toml` и product diff находятся
  в JSON manifest. Corpus/model hashes и installed-distribution audit ещё OPEN.

## Воспроизводимый scan

Runner: [p0_dictionary_audit.py](p0_dictionary_audit.py).
Он не импортирует product code, не делает network/model calls и не читает user config/env values.

```bash
python3 v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06/p0_dictionary_audit.py > /tmp/opencode/p0-dictionary-static-audit.json
```

Артефакт: [archives/p0-dictionary-static-audit.json.gz](archives/p0-dictionary-static-audit.json.gz).

- Uncompressed SHA256: `6d58bee512c63b4f26af4480643267283a6fd04037bf949c8da0b349b6131f76`.
- Gzip SHA256: `03e9683c736f38d146b462eed6d19bae4ffbfa36fb5bd26cdba0c5264abeb536`.
- 383 Python files, 0 parse errors.
- 5594 string-containing collection AST nodes, без прежнего threshold 8 strings.
- 2607 import statements; 1276 regex calls; 223 tracked text/config asset candidates.
- Nested collections учитываются отдельно; эти числа **не число словарей**.
  Candidate hits включают fixtures, docs и технические enums. Ручная классификация необходима.
- Snapshot включает tracked документы на момент запуска; изменение самих audit docs
  меняет report при повторном запуске. Source hashes позволяют сравнивать product независимо.

## Caller map: обязанности D01 распределены по цепочке

| Узел / source anchor | Словарная зависимость | Что сохранить независимо |
|---|---|---|
| `_project_context_service_part01.py:46–74` | `classify_project_query_intent`, `build_requirements`, `build_documentation_query_plan`, `scheduled_plan` до поиска | Явные mode/module/path, исходный вопрос, ограничения scope |
| `documentation_query_plan.py:387–412` | Aliases задают preferred/forbidden roles/terms и `force_context_only`; disposition повторно вызывает builder | Original query и явные exact references |
| `documentation_query_plan.py:463–545` | `host_policies` может наследовать original aliases; lookup получает audited parent и semantic rewrite | Caller lookup origin, собственная attribution, ограничение до 5 public lookups |
| `documentation_query_plan.py:546+` | Generated aliases и special RU installation equivalence | Shared resource ceiling; не прежнюю equivalence как обязательный результат |
| `need_query_schedule.py:69–133` | Optional allowance `min(optional_limit, len(legacy))`; `_COMPOSITION_FOCUS` влияет на proposal order | Integer validation 0–12, общий cap, priority explicit paths/lookups, exact spans |
| `_project_docs_service_part03.py:178–183,270–345` | Scheduled plan; `fail_closed_workflow` включает adjacent expansion и отдельный budget | Два root reads, project filters, tagging, отсутствие нового fan-out |
| `_project_docs_service_part03.py:347–364` | Candidate grouping по alias origins | Bounded pool selection; группы должны иметь независимое основание |
| `_project_context_service_part01.py:103–138` | Prefit `set_context_variants`; fallback `preserves_unresolved_context_candidate`; intent rerank | Проверка scope/body и retention до final projection |
| `context_hint_policy.py:5,19–31,63–74` | Fallback блокируется `_specific_contract_request(_tokens(question))` | Hard stop, exact-path/component ограничения требуют отдельного решения; source checks не удалять |
| `_docs_context_projection_core.py:113–188` | `intent-context:*` влияет на broad admission; canonical intents eligible; fallback снова использует D01 | Final visible windows, budget, source identity, lifecycle и честная attribution |

Следствие: monkeypatch одного builder не моделирует удаление всех словарей. Даже
без aliases остаются intent parser, proof/requirements, lexical quality и fallback policy.
Для P2 first-loss trace нужны отдельные снимки retrieval → qualification → prefit → projection.

## Новая группа D34: qualification содержит смысловые правила

`docmancer/docs/domain/evidence_qualification.py:17–37,184–187`:
`_COMPARISON_RELATION_MARKERS`, `_GENERAL_COMPARISON_RELATION_RE`,
`_PROOF_INSUFFICIENCY_RELATION_RE` распознают EN смысл relation через ручные формы
`different/separate`, `rather than`, `not enough ... prove` и другие.

Классификация **S / SPLIT / OPEN**, P5: эти правила нельзя оставлять вне реестра,
но их удаление без замены может снять relation guard. Требуются RU/EN paired positive/
negative controls. Markdown unit segmentation в этом же файле — отдельный технический parsing.

`evidence_policy_rejection_reason` смешивает независимые guards и proposal policies:
freshness/index synchronization (`218–220`) отделяются от forbidden role/term inputs
(`232–238`). Caller-supplied alias policies не являются тем же контрактом, что identity
или freshness. Перед правкой необходимо разнести происхождение policy inputs.

## D33: configuration bypass уточнён

`core/config.py:146–168`: `QueryRouter.match` — пользовательский regex, routers по
умолчанию пусты. `_dispatch_part01.py:91,556–577` действительно применяет первый match.
В фильтры используется **setdefault**, то есть router не перезаписывает уже заданный
ключ. Нельзя описывать это как доказанный обход project identity. Но отсутствующие
filters могут назначаться по смыслу вопроса: это активная configuration capability.

Решение пока **S / SPLIT / OPEN**: сохранить explicit filters; согласовать миграцию
regex inference, проверить consumers/config compatibility и default/fallback modes.
Scan нашёл router examples в `wiki/Architecture.md`, `wiki/Commands.md`,
`wiki/Configuration.md`. Отсутствие других keyword hits не доказывает отсутствие routers.

Также `EmbeddingsConfig.model` default — `BAAI/bge-base-en-v1.5` (`config.py:108–117`),
retrieval default mode — lexical. Включить существующие vectors не означает доказать
RU/EN качество. Нужен отдельный P2 backend experiment; модель/lock не менялись.

## Что ещё не закрыто

1. Symbol-level классификация всех C/REVIEW и найденных small-inline/regex candidates.
2. Dynamic bridge globals/re-exports, installed-package entry points и fallback reachability.
3. Полный config/template review (keyword scan не semantic audit).
4. Baseline corpus/index/model manifests и воспроизводимость предыдущих A/B на pinned окружении.
5. Утверждение P1 holdout/migrations и явных source-class/lifecycle контрактов.

Следующий slice: разобрать D20/D25/D28 и policy inputs D15/D34, затем зафиксировать
RU/EN case matrix. До этого **P0 не DONE**, P2 integration не начинается.

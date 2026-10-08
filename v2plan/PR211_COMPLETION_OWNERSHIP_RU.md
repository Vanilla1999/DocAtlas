# PR #211: ownership завершающей волны

База: `21fe472d983f394130849d6fd4e582043d58e9ba`.
Рабочая ветка: `implementation/pr211-merge-readiness`.

| Writer | Область |
| --- | --- |
| Координатор | Registration/unified вызов, scope test successors, docs-output fidelity test; интеграция и итоговый checkpoint |
| Trust reviewer/implementer | Trust-resource test в `tests/test_dictionary_exit_delivered_surfaces.py`, companion `tests/docs/test_trust_contract.py`, обоснование trust migration |
| Schema implementer | После review первого slice: compact advertised schema и её equivalence controls; без повышения byte ceilings |
| Acceptance reviewer | Сначала read-only CI/runtime audit; дополнительные harness paths назначаются отдельно |

Общий diagnostic manifest меняет только координатор. Существующие concrete node
names сохраняются. Upstream retrieval, gold, thresholds и required gates не меняются.
Новые dependency/model downloads, provider calls и реальные пользовательские
индексы не входят в локальные проверки. Разрешённый runtime — fixture-only
Git/server descendants, без изменения permissions или обходов guard controls.

Изменения рассматриваются узкими slices. Обычный push в существующий PR разрешён
решениями текущей волны; force-push, merge и release не выполняются.

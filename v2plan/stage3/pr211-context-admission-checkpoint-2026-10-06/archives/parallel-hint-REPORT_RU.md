# PR211 — независимый аудит C: hint / exact anchor / original admission-only

Дата: 2026-10-06. Baseline: **37bfd0668f819935dd9e027bd9d8bf767fcd185a**.
Изолированная ветка: `diagnostic/pr211-hint-20261006`, worktree:
`/tmp/opencode/pr211-parallel-hint`. Коммитов, push, merge и правок других worktree нет.

## Вердикт

**В проверенном сценарии продуктовый дефект публичной original-attribution не
подтверждён. Product patch не предлагается. Предлагается согласовать миграцию
старого representation-теста; без отдельного owner approval его assertions
оставлены неизменными и FAIL.** Это не разрешение обновить gold или принять весь PR.

Добавлены шесть supplemental behavioral checks через настоящий публичный
`call_docs_tool_payload`, indexed source и production dispatcher. Проверка не
ограничивается промежуточным `attributable_query_ids`.

## Основание контракта, а не принятие baseline за gold

- `CONTRIBUTING.md:36–38`, `docs/mcp-docs-server.md:42`: docs_context — retrieval-only;
  original retrieval hit не даёт answer/edit authority; traces остаются внутренними.
- ADR `docs/adr/0003-context-first-project-reads.md:29–38`: честный partial coverage,
  original/host/path/anchor направления; derived original допускается только для
  audited rewrite; metadata не заменяет пересчёт по видимому фрагменту.
- `docs/modules/project-context-retrieval.md:60–72`: exact anchors раньше aliases;
  generated canonical IDs не public coverage; final visible requalification;
  cross-project и unsafe источники невидимы.
- `git show d30aeec1:tests/test_docs_service_part02.py` подтверждает старые две
  assertions: hint ID и отсутствие original **в служебных qualified IDs**.
- `2facdba3` ввёл exact-anchor retrieval. `340759b4` явно отделил
  `qualified_query_ids` от `attributable_query_ids` в selection decision и добавил
  cross-lane body original check. Это объясняет representation drift, но не является
  самостоятельным одобрением смены теста.
- Более новый `tests/docs/test_discovery_independent_qualification.py` требует
  independent original qualification и identity guard; старый запрет original
  во всех internal IDs с этим несовместим. Public prohibition при этом сохраняется.

Прочитаны исходный review RU, adjacent evidence JSON и DEEP_ANALYSIS_RU.md.
Их вывод о недостаточности промежуточных metadata учтён: ниже новые final packets,
а не повторение сохранённой трассы.

## Новое финальное доказательство

Артефакт **`hint-public-final-v3.log`**: реальные публичные packets всех шести
сценариев. Вызов использует advertised arguments `question`, `project_path`,
`scope=project`; observer `capture_public_call` снимает результат после публичного
transport/validation. Dispatcher отдаёт кандидаты только для `NebulaLedger`;
остальные lanes пусты. Product qualification, source binding и projection настоящие.

| Сценарий | Final packet / проверенная граница |
|---|---|
| normal | `ok`, `docs_context`, `covered_query_ids=[query-anchor-1]`, `missing_query_ids=[query-original]`, partial retrieval/query coverage, SQLite в цитате |
| crop | Длинный исходник реально сокращён: длина final snippet меньше исходника; SQLite сохранён; original остаётся missing |
| merge | Дубли одного retrieved source поданы dispatcher; один final source, original missing; self-merge qualified traces не превращает admission-only в public attribution |
| foreign | Подмена candidate project_identity отклонена; `insufficient_evidence`, sources отсутствуют |
| unrelated | Текст candidate заменён unrelated body без NebulaLedger; отказ, sources отсутствуют |
| forged | Unrelated body плюс поддельный qualified original trace / lexical_score=99 / original ID; отказ, sources отсутствуют |

Во всех packets `answer_supported=false`; `edit_ready` false либо отсутствует в
отказе, никогда true. Для успешных packets flags явно присутствуют и false.
Final root coverage не наследуется от exact anchor.

Дополнительно из native projection capture взят источник; после requalification
original trace сохраняет `admission_only=true`. `merge_query_matches` одинаковых
qualified traces сохраняет запрет attribution. После удаления exact subject из
видимого snippet повторная qualification теряет все attributable IDs. Эти unit
assertions дополняют, но **не заменяют** final public проверки.

### Что действительно не доказано

Merge case проверяет duplicate-source deduplication и одинаковые admission-only
traces, а не все heterogeneous multi-window unions/continuations. Crop case
проверяет реальное сокращение native indexed source и отдельную потерю anchor при
visible-window substitution, но не exhaustive перебор crop offsets. Forged case
проверяет ложный trace на unrelated body, а не все возможные forged lineage fields.
Переход legitimately independently retrieved original + admission-only original
между двумя источниками не следует запрещать: genuine original body attribution
может быть правомерной. Нельзя глобально добавлять `admission_only` всем original
traces или менять merge winner rule без отдельного доказанного дефекта.

## Парные проверки, одно окружение

Python: `/home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python`, **3.13.12**.
Для всех валидных прогонов:

```sh
DOCATLAS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
PYTHONPATH=/tmp/opencode/pr211-parallel-hint \
/home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python -m pytest ... -q
```

Roster baseline:

```text
tests/test_docs_service_part02.py::test_query_project_docs_attributes_generic_retrieval_hints_without_covering_original
tests/docs/test_discovery_independent_qualification.py
tests/docs/test_reference_projection_retention.py
tests/docs/test_reference_behavior_matrix.py
tests/docs/test_language_packing_experiment.py
```

- `hint-paired-baseline.log`: **61 PASS / 1 прежний FAIL**, 13.74s.
- Тот же roster + `tests/docs/test_pr211_hint_public_audit.py`:
  `hint-paired-supplemental.log`: **67 PASS / 1 тот же FAIL**, 30.94s.
- Supplemental отдельно с `-q -s`: **6 PASS**, 8.35s,
  `hint-public-final-v3.log` содержит final bytes/поля.
- `git diff --check`: PASS. Production diff отсутствует.

Это paired baseline/supplemental, не baseline/product-candidate: продукт не менялся.
Full core, installed-package, matrix и mutation не запускались; результаты не
повышаются до полного CI или security proof.

### Ошибки диагностического стенда сохранены, не засчитаны

- `hint-public-run.log`: guard остановил новый module как unclassified. Добавлен
  отдельный hash-bound manifest shard с label behavioral, guard не отключался.
- `hint-public-run-v2.log`: monkeypatch agent.query не контролировал production
  dispatcher; four FAIL с root coverage относятся к неправильному стенду.
- `hint-public-run-v3.log`: временное отключение gateway сломало agent lookup;
  этот вариант удалён из итогового теста.
- `hint-public-run-v4.log`: правильный dispatcher seam; normal/foreign PASS,
  unrelated/forged FAIL только из-за отсутствующего edit_ready в отказе.
- `hint-public-final.log`: public transport отверг legacy internal arguments
  mode/delivery_strategy; это validation failure стенда, не retrieval evidence.
- `hint-public-final-v2.log`: корректные public arguments, 4 PASS до добавления
  crop/merge. Итоговая версия — v3, 6 PASS.

## Точное предложение миграции — НЕ применено, требуется согласование

В исходном `tests/test_docs_service_part02.py:782–783` заменить representation
ожидание **только после owner approval**, сохранив fixture/сценарий:

```diff
-    assert "query-hint-1" in chunks[0].metadata["retrieval_query_ids"]
-    assert "query-original" not in chunks[0].metadata["retrieval_query_ids"]
+    from docmancer.docs.application.context_selection import attributable_query_ids
+    metadata = chunks[0].metadata
+    anchor = metadata["retrieval_query_matches"]["query-anchor-1"]
+    assert anchor["qualified"] is True
+    assert anchor["relation"] == "exact_anchor"
+    original = metadata["retrieval_query_matches"]["query-original"]
+    assert original["qualified"] is True
+    assert original["qualification_route"] == "cross_lane_body"
+    assert original["lexical_score"] == 0.0
+    assert original["admission_only"] is True
+    assert "query-original" not in attributable_query_ids([metadata])
```

Здесь exact anchor ID всё ещё representation assertion, поэтому предпочтительнее
на owner review идентифицировать anchor по origin/relation/query_text, не вводить
новое имя ID как вечный контракт. Непременно оставить supplemental final-public
checks: промежуточная attributable assertion одна недостаточна. Предложенный diff
не исполнялся как изменённый старый тест; требуются approval и paired replay после
реального согласованного изменения.

## Изолированный diff

- `tests/docs/test_pr211_hint_public_audit.py`: дополнительные checks, старые tests
  не переписаны, нет skip/xfail, бюджет/guard/workflow неизменны.
- `tests/diagnostic_labels.pr211_hint_audit.json`: только новый module и его node hash.
- Настоящий отчёт и локальные диагностические logs.

Остальные направления A/B и их патчи не исследовались и не редактировались.

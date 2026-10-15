# Task B: REJECT — authority_duplicate при неполном parser

Дата: 2026-10-06. Worktree: `/tmp/opencode/pr211-parallel-authority`.
Ветка: `diagnostic/pr211-authority-20261006`.
Baseline/текущий HEAD: `37bfd0668f819935dd9e027bd9d8bf767fcd185a`.
Нового commit/SHA нет. **Продуктовый patch не реализован: кандидат B отклонён.**

## Причина решения

Удаление только `and query_plan.get("component_scope_complete", True)` из
`authority_duplicate` исправляет исходный distractor, но теряет полезное
дополнение при том же неполном плане и порядке authoritative-first.
Отсутствие component witness нельзя считать отсутствием полезного содержания.

Прочитаны первичный review, соседний `PR211_RED_EVIDENCE_20261006.json`,
`/tmp/opencode/pr211-red-analysis/DEEP_ANALYSIS_RU.md`, предыдущие authority probes,
а также инструкции CONTRIBUTING и обзорные документы репозитория. AGENTS.md в
доступном дереве `/tmp/opencode` не обнаружен. Другие worktrees только читались.

## Новая парная проверка

`authority_diagnostic.py` использует реальную ingestion/service/public-handler
fixture исходного notes test. Сохраняются manifest, 24 supporting notes, авторитетный
план, вопрос, budgets и bounded_direct. Для положительного случая в supporting note
добавлено **`A changed hash produces a red warning.`** Это дополнительное наблюдение
о presentation-only snippets и decision_hash: авторитетный план сообщает сохранение
hash/IDs, но не описывает визуальную реакцию на изменение hash. Supporting note
остаётся дополнительным описанием, а не новым нормативным acceptance contract.

Во всех основных парах `component_scope_complete=false`. Проверяется финальный
публичный snippet, не только status. Кандидат меняет ровно одну проверку в памяти;
FunctionType использует исходный module globals, сохраняя тестовые hooks.

| Случай | Baseline | Кандидат B |
|---|---|---|
| Бесполезный distractor | authoritative первым, затем note | только authoritative |
| Полезное supporting дополнение | authoritative первым, затем note; факт доставлен | только authoritative; **факт потерян** |
| Independent lookup о warning | факт доставлен | факт доставлен |
| Дополнение внутри authoritative источника | authoritative первым; факт доставлен | authoritative первым; факт доставлен |

Положительная пара и distractor отличаются только добавленной фразой в note.
В trace кандидата полезные варианты отклонены с `authority_duplicate` (5 событий),
после принятия authoritative варианта. Во всех восьми packets `answer_supported=false`
и `edit_ready=false`; потеря контекста не маскируется как изменение answer authority.
Детальные планы, публичные packets и decision traces сохранены в
`authority-paired-evidence.json`; краткий вывод — `authority-paired.log`.

В independent lookup случае supporting выбирается первым: этот дополнительный
контроль **не доказывает** безопасность исключения independent lookup после
authoritative. Same-source probe проверяет доставку дополненного тела, а не сам
механизм same_origin_gain. Его отдельные неизменённые unit/integration tests включены
в дополнительный парный roster. Эти ограничения не мешают отклонению B: нужный
authoritative-first контрпример уже воспроизведён без перестановки ranking.

Ранние поисковые варианты с явным повторением имён субъектов выбирали supporting
первым либо получали распознанное дополнение; они не использованы для решения.
Зафиксированный скрипт содержит окончательную минимальную пару. Имена note-NN могут
меняться между runs из-за равнозначных документов; проверяется порядок классов
источников и содержание, а не случайный номер note.

## Same-environment результаты неизменённых tests

Python 3.13.12, pytest 9.0.3, FastEmbed 0.8.0, pydantic 2.13.4.
Один interpreter, PYTHONPATH worktree, offline flags; B отдельно от A/C.

| Набор | Baseline | Runtime B |
|---|---|---|
| Исходные 85 tests | 83 PASS / 2 FAIL (20.58 s) | 84 PASS / 1 FAIL (21.68 s) |
| Дополнительные 117 tests | 114 PASS / 3 FAIL (63.23 s) | 114 PASS / 3 FAIL (67.81 s) |

В первом наборе исправлен только
`test_project_query_does_not_return_non_project_docs_with_same_terms`.
Сохранён FAIL
`test_visible_component_novelty_follows_exact_constraints_before_public_queries[projection_clip]`.

Во втором наборе сохранены все три прежних FAIL:

- `test_stale_health_live_status_sync_and_removal`;
- `test_first_session_live_query`;
- `test_remaining_live_workflow_witnesses[v2-natural-evidence-selection]`.

Полные логи и JUnit XML сохранены рядом. pytest завершился с exit 1 в каждом
baseline/candidate run; это честный красный результат, не green gate.
Диагностический скрипт exit 0 означает успешное воспроизведение **потери факта**,
а не принятие кандидата.

## Точные команды

Все команды выполнялись из `/tmp/opencode/pr211-parallel-authority`.

```bash
PYTHONPATH=/tmp/opencode/pr211-parallel-authority HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python authority_diagnostic.py > authority-paired.log 2>&1

PYTHONPATH=/tmp/opencode/pr211-parallel-authority HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python authority_test_replay.py -q tests/test_docs_service_part03.py tests/docs/test_context_completion_guards.py tests/docs/test_component_coverage.py tests/docs/test_discovery_independent_qualification.py --junitxml=authority-baseline.xml > authority-baseline.log 2>&1

PYTHONPATH=/tmp/opencode/pr211-parallel-authority HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 AUTHORITY_CANDIDATE=1 /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python authority_test_replay.py -q tests/test_docs_service_part03.py tests/docs/test_context_completion_guards.py tests/docs/test_component_coverage.py tests/docs/test_discovery_independent_qualification.py --junitxml=authority-candidate.xml > authority-candidate.log 2>&1

PYTHONPATH=/tmp/opencode/pr211-parallel-authority HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python authority_test_replay.py -q tests/docs/test_support_preserving_selection.py tests/docs/test_support_retention_integration.py tests/docs/test_context_loss_boundaries.py tests/docs/test_generic_context_workflows.py --junitxml=authority-complement-baseline.xml > authority-complement-baseline.log 2>&1

PYTHONPATH=/tmp/opencode/pr211-parallel-authority HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 AUTHORITY_CANDIDATE=1 /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python authority_test_replay.py -q tests/docs/test_support_preserving_selection.py tests/docs/test_support_retention_integration.py tests/docs/test_context_loss_boundaries.py tests/docs/test_generic_context_workflows.py --junitxml=authority-complement-candidate.xml > authority-complement-candidate.log 2>&1
```

## Diff и оставшиеся риски

Tracked product/test/gold/guards/limits/workflow diff: **пустой**. Новые isolated файлы:

- `REPORT_RU.md`;
- `authority_diagnostic.py`, `authority_test_replay.py`;
- `authority-paired-evidence.json`, `authority-paired.log`;
- `authority-baseline.log`, `authority-baseline.xml`;
- `authority-candidate.log`, `authority-candidate.xml`;
- `authority-complement-baseline.log`, `authority-complement-baseline.xml`;
- `authority-complement-candidate.log`, `authority-complement-candidate.xml`.

Нет новых эвристик, blacklists, weights, blanket supporting exclusion или изменения
существующих assertions. Нет commits/push/merge. Baseline distractor дефект остаётся;
безопасное общее исправление не найдено. Пробы синтетические и не являются holdout
или оценкой downstream ответов. Full CI, matrix, installed-package/security gates
не запускались. Это локальное основание **REJECT B**, не merge/full-CI readiness.

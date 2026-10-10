# P2: baseline / no-alias на реальном MCP handler

**Исторический diagnostic report.** Replacement-first next steps в конце файла
superseded owner decision: сначала dictionary exit, затем улучшение полноты.
Current status: [CONTINUE_HERE_RU.md](CONTINUE_HERE_RU.md).
Raw gzip evidence оставлен локально по решению владельца, не включён в Git;
публикуются этот отчёт и компактный analysis. Fresh clone не содержит полного
stage-trace archive; отдельное архивное хранилище пока не настроено.

**P2 ACTIVE, NOT DONE.** Same-language EN→EN original-only diagnostic,
не official Direct-15 frozen-blob gate и не installed stdio validation.

Команда:
`.venv/bin/python v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06/p2_mcp_alias_ablation.py`

Первый foreground запуск остановлен timeout 120 с без final report; завершённый
background запуск exit 0. Один sync и один actual SQLite index для всех 30 вызовов
public `get_docs_context` handler: baseline/no-alias pairs. 134 источника,
1 generation; non-FTS table hashes проверены до/после каждого вызова, digest один.
Три реальные builder bindings перехвачены в памяти; ablation достиг builder и
возвратил empty aliases. Published intent из `8d2381d8` загружен в памяти:
существующий локальный unaccepted trust diff не принят и не сброшен.

## Результаты

| Наблюдение | Published baseline | No-alias |
|---|---:|---:|
| Все назначенные fact groups доставлены | 11/15 | 9/15 |
| Доставленные fact groups | 34/48 | 29/48 |
| Citation integrity | 15/15 | 15/15 |
| Максимум источников | 3 | 3 |
| Максимум estimated final DTO tokens (штатный estimator) | 794 | 800 |

Socket attempts = 0; vectors выключены; модель не вызывалась.
Все final answer_supported/edit_ready false; это не проверка typed-proof positives.
В Q10 no-alias восстановил четыре отсутствовавшие baseline groups. Этот выигрыш
не компенсирует выпадение nine groups в Q03/Q07/Q13/Q15.

## Source-bound разбор потерь

`p2_ablation_analysis.py` сравнивает exact path/text witnesses в реальных stage
returns, не replay qualification. В no-alias:

| Case | Потеря | Наблюдаемая граница |
|---|---|---|
| Q03 workflow | prepare_only_when_needed | Witness не наблюдался в raw `_run` results; поиск |
| Q07 fail-closed | no_unsupported_claim_or_edit, safe_context_remains | README candidate найден; все его наблюдаемые query matches rejected `insufficient_visible_match` |
| Q13 location | server_location | PROJECT_MAP table candidate найден; original match rejected `insufficient_visible_match` |
| Q15 product claims | все 5 назначенных groups | PRODUCT_BRIEF candidate найден; original/hint matches rejected `insufficient_visible_match` |

`select_context_candidates` здесь объединяет **raw candidates**, это не final
approved admission. Поэтому потери Q07/Q13/Q15 нельзя описывать как установленный
budget/crop defect: наблюдаемые witness candidates не проходят relevance
qualification. Ослабление source/safety/proof guards этим не разрешено.
Source-bound absence относится к saved fields/branches, не ко всему возможному graph.

## Evidence и ограничения

- `archives/p2-real-mcp-alias-ablation-v1.json.gz`: обе final payload/snapshots,
  stage returns, aliases/query plans, actual index manifest, source/config/code
  provenance hashes, baseline diagnostics и errors сохранены.
- `archives/p2-real-mcp-ablation-analysis-v1.json`: witness candidates/stable IDs,
  metadata query rejection reasons и bounded first-loss intervals.
- Текущие source bytes, не frozen README blob acceptance. Sidecar не обновлялся.
- Baseline self-host report остаётся **red**: fact gaps, paths/attribution/packs
  controls и frozen thresholds. 11/15 — только fact-delivery metric, не green gate.
- Другие смысловые механизмы всё ещё действуют: builder ablation не равна полному
  dictionary exit. Candidate third arm, RU→RU, explicit-lookups, guard controls,
  frozen same-language holdout и actual resource SLA остаются pending.
- Baseline всегда первый, profiler имеет overhead: latency не production p95.

## Следующая реализация в P2

Отдельный dictionary-independent **context-only candidate**, который различает
source eligibility, relevance и answer proof; не возвращает intent coverage из
совпадения имени. Проверить на том же snapshot: улучшает ли поиск Q03 и допускает
ли полезные Q07/Q13/Q15 witnesses без ложных name-only/subject/negation claims.
Не исправлять потери отдельными query/topic/path rules. Не удалять old aliases,
не объявлять P2 DONE до candidate и обязательных P1/control проверок.

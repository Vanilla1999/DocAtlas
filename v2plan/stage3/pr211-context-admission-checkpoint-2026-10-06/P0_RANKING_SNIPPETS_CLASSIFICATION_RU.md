# P0: ranking/snippets classification и consumers

Прочитаны полностью `project_doc_ranking.py` (880 lines) и `snippets.py`
(624 lines). Решение для обоих mixed modules — **SPLIT**, не blanket removal
и не technical exception. Product bytes не менялись.

## D13 — project ranking

- `project_question_lane` / `source_lane_allowed`: RU/EN regex выводит разрешённый
  evaluation/planning/history lane; это eligibility, не только rank boost.
- `project_source_taxonomy`: filename/path lists выводят authority/source kind;
  migration не должна терять реальные source boundaries или приравнивать
  `README`/heading к доказательству.
- `condition_lead_priority`: NL permission/condition recognizers дают priority;
  сохранить whole-anchor binding и запрет negative→permission promotion отдельно.
- `source_weight_for_intent`, `source_requirement_boost`: hardcoded topics,
  product paths и weights, включая configure→configuration, pytest→testing.md,
  command→wiki/commands.md. Мигрировать без новой тематической таблицы.
- `ensure_broad_query_sources` / `find_replaceable_index`: forced architecture,
  README, contributing, Docs/Packs injection и preferential changelog replacement.
  Это отдельный consumer смысловых predicates, не generic diversity cap.
- `rerank_project_doc_chunks`: обычный путь, injection и два bounded backfill
  branches используют уже filtered/scored pool. Preserved guards: stale rejection,
  lifecycle contract, explicit failed qualification не rescue через boost,
  independent public query IDs, no root coverage from internal need witnesses,
  source quotas и stable ordering. NL lifecycle producer мигрируется отдельно D18.
- Reasons/metadata копируют guessed taxonomy и explanations; их нельзя оставить
  как будто evidence-derived после удаления boosts.

Resolved source callers: `_project_context_service_part01.py:131` вызывает rerank;
`trust_contract.py:26` и `_project_context_service_shared.py:181` отдельно вызывают
taxonomy. Следовательно removal только reranker не устраняет authority inference.

## D16 — snippet selection (смежные D17/D28/D33)

- `infer_snippet_query_intent`: hardcoded library→language mappings и invented
  symbols. Riverpod/autodispose добавляет `keepAlive`/`ref.watch`, даже если их
  нет в вопросе; Click/group добавляет decorator. **REMOVE semantic invention**.
- `_is_symbol_like`, `_intent_relevance_score`, `_infer_language`: library/topic
  recognition отдельно от shaped identifiers и actual source grammar; **SPLIT**.
- `_NOISE_TEXT`, cleaning/noisy predicates: lexical UI removal может менять
  cited bytes; не объявлять generic markup exception, сохранить provenance.
- `_LANGUAGE_ALIASES`: exact fence-label normalization — technical candidate,
  не основание сохранить library-derived expected language inference.
- `_FLOATING_VERSION_ALIASES` / `_exact_version_match`: version metadata policy
  отдельно от NL semantics; preserve non-exact fallback risk и snapshot source
  verification. Metadata booleans сами не доказывают freshness/exactness.
- Presentation/DTO helpers: caps/dedupe/truncation и untrusted document-data
  boundary сохранить; `complete` означает snippet completeness, не answer proof.
- `_snippet_metrics.primary_source_correct=True` выводится из наличия primary;
  это не source validation. При migration не использовать как proof signal.

Default callers: project context `:625`, library service part03 `:755`, unified
service part01 `:302` вызывают `build_snippet_presentation`. Unified part02 `:197`
повторно строит presentation; project-context shared `:636` вызывает
`best_context_pack_snippet` без question, но shared scoring/language inference
остаётся достижимым. Auto/evidence-first возвращает раннюю presentation;
snippet-first/auto-code проходит scoring/noise/dedupe/selection ветки.

Consumer map — source-level named edges, не заявление полного runtime trace.
Подтверждённые technical операции сохраняются отдельно от mixed-module scope.

# P0: source-bounded parallel closure assessment

**Вердикт: P0 остаётся ACTIVE.** Полный запрошенный union рассмотрен, но два
конкретных public semantic claim maps ещё не согласованы. Ноль local OPEN не
заменяет этого согласования. Общие/product/test/gold файлы не изменены; baseline
не перезапускался. Выход: `archives/p0-parallel-closure-assessment.json`.

## Покрытие и смысл dispositions

Union содержит **186 уникальных `(path, owner, source_sha256)`**: 176 исходных
`reachability=unresolved` и 10 explicit closure OPEN, пересечение — 0. Проверены
точное равенство keys, отсутствие duplicates и совпадение всех current source pins.

| Disposition | Rows | Значение |
|---|---:|---|
| technical-no-semantic-closure-needed | 96 | Локальная format/schema/storage/diagnostic операция; неизвестный внешний caller не создаёт semantic blocker |
| closed-source-bounded | 38 | Ограниченный default assembly/SDK contract установлен по source; не runtime proof |
| known-semantic-dependency-classified | 50 | Известный REMOVE/SPLIT механизм либо его transport; не technical exemption и не implemented removal |
| genuinely-open-semantic-gap | 2 | Остаточная сверка конечного public claim с конкретными semantic branches |

Каждая JSON row содержит исходные keys, disposition, actual qualified AST span и
hash исходного тела, именованные call references, local dependency expressions,
classification origin, reason и concrete remaining_gap. Qualified owner resolution
отличает одинаковые `__post_init__` разных classes. Call references для attributes
**не выдаются за resolved receiver binding**. Для default/facade критических цепочек
добавлены отдельно проверенные route maps. Полный список calls — вспомогательное
source evidence, не сертификат выполнения ветвей или универсального Python графа.

Technical выводы не сделаны из одного названия: проверены source spans и прежние
partition основания. DTO serialization/hash, SQL generation/IDs, exact formats,
Git transport, cache bytes, explicit status arithmetic не читают смысл вопроса.
PDF/DOCX/HTML callbacks и third-party storage internals не требуют собственного
P0 NL audit. Source metadata/currentness и upstream producer authority этим не
утверждены. SDK roots не объявлены dead code из-за отсутствия default callers.

## Десять explicit OPEN: что именно разрешено

1. **Core `project_docs_context` — genuinely open.** Default facade
   `docs_context_projection.py:198–222`, hint recursion и joint route установлены.
   `compile_need_contracts`/`classify_need_context`, hint/lifecycle/source rules
   классифицированы mixed/semantic. Неизвестный локальный механизм отсутствует.
   Остаток: единый map **original/lookup relation → audited rewrite producer →
   independent probes → final cropped `query_matches`**, включая hint fallback и
   joint replacement. `derived_parent_trace` проверяет supplied audited/qualified
   contract, но не доказывает независимо semantic equivalence. Byte lineage и
   false answer/edit flags не закрывают public original attribution.

2. **`select_evidence` — genuinely open.** Реальные profiles/callers:
   project-context `:410,568,602`, library part03 `:721`/part04 `:97`, action packet
   part03 `:125`, model-visible reselection `:226`. Eligibility, coverage и witness
   helpers классифицированы. Остаток — конечная таблица **source_fact/facet/
   code_group witness branches → canonical assignment → support** для этих
   docs/patch/library profiles и reselection. Это конечные family branches, не
   требование расследовать каждый сторонний callback. `proofability.py` объясняет
   supplied verdict, не independent authority; его diagnostic literals не blocker.

3. **`requirement_probe_query` — known semantic dependency classified.** Исправление
   SPLIT действительно интегрировано: part04 `:34–36` вставляет `result`, а
   `:13–21` переносит supplied aliases/expected value. Project rescue `:420–427`
   потребляет query. Это retrieval proposal, не самостоятельно parent proof;
   bounded exact serialization отдельно. Общий 320-char bound не заявляется.

4. **`get_patch_constraints` — known semantic dependency classified.** Actual
   `_safe_constraint_profile:621–636` читает normative text/authority/grounded owner;
   `_owner_from_line` part03 `:61–80` содержит owns/delegates/layer/suffix vocabulary.
   Они SPLIT, не скрытая technical grammar. Packet → validation → patch review
   source path назван. Source-map/code-graph producers отдельно mixed; unknown/manual
   результаты и nonautomatic advice не становятся edit authorization.

5. **`_symbol_from_line` — known semantic dependency classified.** D30 correction
   SPLIT присутствует. Part02 `:551–575` → `_symbol_candidates:407–443` →
   `_symbol_candidate_constraints:584–619`. Library blacklist, Future/Widget и
   last-call choice остаются semantic migration components; literal extraction отдельно.

6. **Project `get_project_context` — known semantic dependency classified.**
   Default requirements, patch-plan adapter, inferred dependency и source-map gap
   handoff имеют именованные producers и classifications. Legacy completeness
   сохраняет next actions: `derive_project_answer_completeness` →
   `recovery_handoff.py:13–31` → unified `:527–529`. MCP
   `docs/interfaces/mcp/context_tools.py:485–504` **заново** строит mutation packet
   с mutation contract; raw DTO `edit_ready` не copied permission. Selector public
   support branch reconciliation остаётся общим gap №2, не новым unknown owner.

7. **`inspect_project_docs` — known semantic dependency classified.** Overview
   `domain/project_state.py:243–255`, placeholder preflight part01 `:331–344`,
   default discovery `project.py:378–420,552–656` и gap/source-map handoff не
   technical exceptions. Explicit catalog invalidity, no-prune и confirmation
   отдельно preserved. Source callers inspection/bootstrap/project context известны.

8. **Unified `get_docs_context` — known semantic dependency classified.** Actual
   latest helper part02 `:118–177` требует explicit fallback и маркирует
   `match=False`; snippet helper `:179–232` вызывает classified REMOVE
   `_snippet_first_fallback_question`. Canonical mixed AND/support guards сохраняются.
   Public MCP `:326–331` отключает network/bootstrap, `:463–477` валидирует final
   projection; patch path строит action packet. Task/imperative recognizers не
   маскируются explicit-mode chooser. Gap №2 распространяется на этот consumer.

9. **`qualified_fragments` — known semantic dependency classified.** Core `:332–340`
   передаёт concrete requalifier. `context_selection:61–73` зовёт answer-unit proof,
   тогда как `:180–251` проверяет literal span/hash assignment. Semantic focus и
   proof producers classified отдельно от window/footprint logic. Gap №1 остаётся
   upstream/public attribution obligation; callback internals вне default не blocker.

10. **`packet_alternatives` — known semantic dependency classified.** Public projector
    `:285` → `select_joint_context:228`; `_draft_subsets:113–136` →
    `_finish:42–82` → `_finalize_quality:178–193` → component coverage. Snapshot
    replacement сохраняет byte occurrences, но не доказывает proposition.
    Default caller-lookups bypass `:215–217` сохранён. Gap №1 распространяется на
    inherited attribution после coalescing, №2 — на конечные support obligations.

Таким образом восемь старых explicit gaps больше не являются **незнанием local
mechanism/reachability**. Это не обещание, что их общий public support/attribution
graph закрыт: две указанные остаточные обязанности распространяются на consumers.

## Остальные unresolved rows: границы source evidence

- Public lazy exports и concrete class/function shard bridges установлены в actual
  module declarations; sync-before-call переносит public globals. Нельзя выдать
  private-shard patch за default implementation evidence.
- Loader class/load rows относятся к exact format adapters; configured dynamic
  parser identities уже проверены connector archive. Third-party extraction
  quality не заявлена и не добавлена в semantic blocker list.
- SQLite generations/parity/metadata/health и vector ownership rows — exact
  storage protocols. Их lifecycle/authority fields transport не одобряет semantic
  defaults `normalized_filter_metadata`, который остаётся SPLIT.
- Patch-review ranks/buckets/unknown triage, включая dogfood path/product symbol
  priors, классифицированы semantic/mixed и достигают summary/advisory outputs;
  это не hard permission. Validation UI safe-wiring/policy dictionaries остаются
  SPLIT/REMOVE, хотя результат называется validation.
- Default discovery, reference constructor/planning, corpus source targets,
  SourceBoundary config defaults и query-planning locator heuristics выделены
  как известные semantic dependencies. Ни explicit source containment, ни
  literal URL adapter не exempt весь source-policy producer.
- Four mutation operation constants имеют recorded declaration-only bounded scan;
  REMOVE не означает активный operation dispatch. Actual request-plan parser и
  target authorization классифицированы отдельно. Future reflective external
  access не требуется доказывать отсутствующим для P0.

## 1954 + 568 + 102 и assets consistency

Проверены все 15 artifact hashes из reconciliation и current source pins всех
2624 grouped units. `568 NODE-CLASSIFICATION-COMPLETE`, `102 OWNER-AUDIT-DECISION-RECORDED`
и 1954 parallel units образуют исходный grouped scope. Group node counts/unique
IDs дают **9874**, не потеряны кандидаты при grouping. Нельзя складывать эти числа
как количество словарей. Prior owner REMOVE при отдельных technical AST nodes не
обязательно contradiction: literal spans/bounds — mixed components. Prior 102
остаются pinned enclosing-symbol decisions, не approval каждого вложенного правила.

Сверены семь templates и 29 corpus assets transition manifest: missing/changed — 0.
Проверены hashes в stage-wheel и candidate-closure manifests: mismatch — 0. Это
consistency, не semantic exemption assets. Generated host/protocol fields technical;
`WORKFLOW_POLICY` и category→scope/tool instructions D33 SPLIT. `PUBLIC_EXAMPLES`
illustrative, но frozen D37 questions действительно участвуют в production
arbitration. D38 default corpus rules не одобрены узким retain ingestion scheduler.

## Baseline: red recorded не равно missing artifact

Все четыре trace hashes совпадают с `p0-trace-integrity.json`; integrity failures —
0. Сохранены 98 final rows и 134 indexed sources на lane, actual generation/config
identity, blob/citation checks. Useful counts 8/15, 12/15, 11/15; Direct-15 diagnostic
report имеет **FAIL**, 2/15 positive passed и 17 report errors. Trust lane не имеет
acceptance gold. Report failures нельзя объявить green, но их наличие **не** причина
заново запускать baseline ради audit. Wheel `eval` import defect уже записан, не
missing probe и не поручение чинить packaging в этом review.

Оригинальный gate `P0_TO_P1_GATE_RU.md:41,80–91` всё ещё различает diagnostic replay
и official frozen reproduction; exit plan `:180–182` требует pinned-tree baseline
reproducibility. Проверенная consistency четырёх diagnostic lanes не позволяет
самостоятельно снять **PARTIAL** для official frozen/required-control scope.
Конкретный остаток: связать frozen hash-precondition failure и необходимые recorded
controls с **точными archived logs/SHA/config/command**, либо явно показать, что
уже имеющиеся архивы закрывают этот пункт. Не требуется зелёный frozen suite для
P0; требуется воспроизводимое recorded состояние. Не утверждаю, что failure log
отсутствует во всех вложенных старых архивах: linkage в текущем gate не reconciled.
Только при обнаруженной конкретной отсутствующей записи оправдан новый run.

## Конечный gate, без расширения scope

P0 DONE сейчас не подтверждён по двум finite semantic claim maps выше и незавершённой
artifact-to-frozen-baseline gate reconciliation. Остальные 176 reachability labels
не являются самостоятельной обязанностью полного transitive/runtime graph.

Интегратору осталось: закрыть parent-attribution map и selector-family public-support
map; приложить baseline linkage; включить 568/102 и assets в окончательный общий
registry/gate с named narrow retained grounds. P1 exception approval, holdout freeze,
green release CI и dictionary-exit `REMOVED` — отдельные последующие obligations,
не искусственные P0 blockers. Этот отчёт не изменяет общий gate и не даёт merge approval.

# PR211 docs / catalog / quality implementation review

Base: `11489239ae0a5ff85c1f817f0650bea661e88ba1`.
Shared checkout: `/workspace/scratch/5ecb5f548321/DocAtlas-plan-execution`.
This is an implementation/review note, not a runtime PASS. No repository code,
pytest, imports, subprocess fixture runtime, model downloads or provider calls
were executed locally. Python stdlib only parsed/compiled source (without exec),
checked JSON, compared hashes/text and read baseline blobs with Git.

## Current contract and product reasons

The current public ToolSpec accepts original+explicit lookup requests and finite
literal membership. `prepare_docs` sync without mutation is read-only. Confirmed
member upserts bind exact catalog/document hashes, host-selected private storage
and generation; `_apply_project_members` returns `sources_deleted=0` and replaces
sections only for selected members. Current retrieval filters by member path,
content hash and catalog-entry hash. Free-form question-to-proof compilation and
answer authorization are retired. These facts, not current failing outputs,
justify the documentation and oracle migration.

Four exact documents added to the catalog (no recursive root or link following):

| Document | Product reason | Scope |
|---|---|---|
| wiki/Commands.md | Maintained CLI reference already linked by docs/INDEX; supported setup/ingest/query/doctor entry points | project |
| docs/index-cleanup.md | Maintained preview/apply cleanup runbook already linked by README; sources/config preservation | project |
| docs/modules/project-context-retrieval.md | Maintained application/gateway/qualification architecture, corrected to explicit requests | module: docmancer/docs |
| docs/modules/evidence-selection.md | Maintained eligibility/visible evidence boundary, corrected to retrieval-only decisions | module: docmancer/docs |

Both module paths exist in the original checkout and in the tracked-file self-host
mirror. `scope=all` includes their documented module facts; `scope=project` does
not silently receive module membership.

## Witness crosswalk: six changed obligations, all stable IDs retained

| Obligation | Previous promise | Current requirement / preserved user meaning |
|---|---|---|
| flow_selection | Compact witnesses then expansion under capacity | Explicit-query selection and requalification against final visible fields; original query still asks how sources are selected |
| selection_application | Exact anchor/original/host plus generated aliases | One opportunity per explicit lane before second candidates; no invented alias lane |
| selection_proof | Subject/relation/value lexical proof certifies facets | Current membership, scope, identity, freshness and visible support decide source eligibility; broad original question still requires a substantive selection rule |
| selection | Certified-answer decision | Current eligible candidates become source-bound retrieval-only context; original search-trust question still requires an explanation of assessment |
| stale | Sync physically removes stale sections | Changed hashes exclude stale versions from current retrieval; confirmed upsert replaces selected-member sections |
| orphans | Sync physically prunes orphaned sources | Deleted/no-longer-admitted sources cannot appear in current retrieval; physical deletion of unselected rows is explicitly no longer promised by current sync |

The physical deletion distinction is visible in docs and crosswalk; it is not
silently treated as equivalent persistence behavior. Separate clear-index
preview/apply safety remains intact; no deletion code or permission changed.

All 25 case objects retain ID, original question/lookup text, type, scope,
obligation references and negatives. Exactly one retired automatic inventory ID
`query-anchor-1` is removed from `v2-natural-request-flow`; `get_docs_context`
remains literally in that unchanged original request. All 41 obligation IDs and
accepted scope/authority requirements survive. Six witness sets are replaced;
55 accepted witnesses across 12 documents pass static source-text checks.

Frozen Legacy cases, cases.legacy, natural, paraphrases, protocol/lanes locks and
V2 diagnostic shard remain byte-identical. Legacy live path verdict remains
report-only; original-query floor 12 stays separate from lookup count.

## Evaluators and policy

- V2 identity uses only active explicit catalog rows. No docs/analysis/wiki path
  gains identity via broad roots. The catalog bytes are now independently locked.
- Hermetic quality contract checks exact original identity/hash, exact explicit
  lookup order/text/lineage, original-only required ID, no parent credit, no inferred
  aliases/obligations, and no completeness assertion. It explicitly says retrieval
  quality is a separate live check; empty output cannot be certified by planning.
- `_packs_contamination` no longer counts an incidental Packs mention/path. It
  detects actual Docs→Packs command/tool substitution, with explicit comparison
  and negative controls. Required Docs facts and relevance remain independently
  checked; an unrelated PROJECT_MAP paragraph is not thereby useful.
- Removed only full-DTO token-size failure from self-host/V2. V2 result schema3 /
  acceptance v2 replaces budget_compliance with preserved source-count compliance
  plus valid cost observation. Canonical public UTF-8 bytes and serialized token
  estimate remain visible; this is not actual installed-client token evidence.
- Retained existing source-count control 3, explicitly pending separate review.
  It is an existing final-source control, not a newly proven safety necessity.
  Input/source-read/work/acquisition limits are unchanged.
- All semantic usefulness, lookup, negative/control, false-full and source safety
  numeric requirements are identical. Legacy hard-zero list removes only
  token_budget_violation_count; original >=12 and remaining zero checks stay.
- Nonempty server `answer` cannot pass a retrieval-only/negative result merely
  because its token-size failure was removed: authorization denial checks meaning.

## Changed files and checks

24 files, listed with before/after SHA256 in `docs-quality-static-audit.json`:
README, project catalog, maintained docs (INDEX/PROJECT_MAP/Architecture/ADR/MCP/
project lifecycle/two module docs), V1/V2 evaluators, V2 docs/cases/crosswalk/locks,
self-host and V2 acceptance wrappers, four narrow test modules.

Static checks completed:

- Eight changed Python files parsed and compiled without execution.
- JSON files parse; protocol/corpus/crosswalk/diagnostic/catalog/doc hashes match.
- 25 inputs/case types/scopes/negatives unchanged; sole public-ID migration explicit.
- All 55 current witnesses exist in admitted documents with correct scope/authority.
- Frozen inputs and Legacy numeric floors unchanged; policy exception isolated.
- `git diff --check` passed.

Narrow verification changes preserve historical cases while adding independent
corrupted-original/extra-query controls and a large faithful source whose required
installer fact is then removed. Existing contamination tests now inject the actual
Packs command and preserve positive/negative comparison cases. Existing 800/801
edge checks are cost observations and still reject source/authorization failures.

## Remaining evidence and risks

Runtime is NOT RUN locally. Publish then execute the existing CI sequence; obtain
own complete V2 report, Hermetic report, Legacy lineage/safety report and narrowed
JUnit on the published SHA. The newly reachable V2 may expose real retrieval
losses; none is waived by corpus validation or changing documentation.

Legacy frozen path/fact diagnostics can remain red where the retired lifecycle
mechanism was required; they are historical report-only and cannot be called a
newly successful original task. V2 contains the reviewed current user-meaning
crosswalk. The physical prune promise is retired explicitly, not implemented.

`_packs_contamination` is a finite reviewed evaluator oracle, not a general NLP
claim that every possible command recommendation has been classified. Its golden
controls include real substitution, incidental mention, explicit refusal, and
same-line 'instead of' substitution. Missing required Docs-command evidence stays
an independent failure.

## Independent review correction

The reviewer identified two false negatives where a correct Docs command on the
same line masked a Packs substitution or inherited the negation. The shared
both-command exemption was removed. Exclusion now binds only to the exact matched
Packs occurrence, so negating Docs never exempts a later Packs command. Both
counterexamples are retained in the existing self-host control helper. Source
metadata in the static audit was refreshed; no runtime result is claimed.


## Independent reviewer record

# Независимый review: docs / catalog / quality migration

Reviewer: question_recovery_impl. Base: `11489239ae0a5ff85c1f817f0650bea661e88ba1`.
Только read-only source / JSON / AST / hash checks; repository runtime не исполнялся.

## Вывод

Source review одобряет миграцию текущих контрактов после исправления отмеченных
ниже oracle/catalog/docs несогласованностей. Это не утверждение, что V2 или
Legacy live проходят: собственные результаты на конечном SHA ещё обязательны.

## Независимо проверено

- Сохранились 25 case IDs, все исходные вопросы/lookups, типы случаев, scope,
  отрицательные ограничения и 41 obligation ID.
- Единственный case-level diff — obsolete `query-anchor-1` удалён из
  `expected_public_query_ids` одного request-flow case. Сам буквальный original
  query сохранён; production DocumentationQueryPlan создаёт original и explicit
  host lookups, не самостоятельную автоматическую anchor query.
- Все 55 witnesses находятся в 12 предусмотренных docs с formatting-only
  нормализацией. Сверены hashes cases/crosswalk/diagnostic/catalog и всех docs.
- Numeric quality и lineage thresholds сохранились. Старый budget metric
  разделён на retained source-count check и cost-observation completeness;
  удалён только фиксированный full-DTO 800 ceiling. Фактические сериализованные
  UTF-8 bytes и estimated tokens продолжают вычисляться независимо от поля
  reported_estimated_tokens. Это не tokenizer actual-client claim.
- Current catalog имеет четыре обоснованных явных дополнения. Два module docs
  остаются module scope `docmancer/docs`, а не получают project-wide scope ради
  прохождения source matcher. Recursive discovery удалён из evaluator identity.
- Hermetic legacy report честно маркирует `retrieval_executed=False`: original
  identity и query lineage не выдаются за retrieval quality. Source facts и
  original coverage требуют отдельного live report.

## Шесть reviewed witness migrations

| Obligation | Основание текущего смысла |
|---|---|
| `flow_selection` | Compound retrieval учитывает отдельные explicit queries и заново квалифицирует final visible fields. Обещание exact maximization/mandatory compact expansion больше не выдаётся за установленный контракт. |
| `selection_application` | `context_selection.select_context_candidates` даёт каждой query lane возможность до второго candidate; `DocumentationQueryPlan` теперь содержит только original/host inputs. |
| `selection_proof` | Current project reads проверяют membership/scope/freshness/source identity и visible support. NL lexical proof не может сертификатировать ответ. Исходный широкий вопрос о выборе evidence сохранён. |
| `selection` | Результат — source-bound retrieval-only context; отдельные `not_proof` и `project_context` обязанности в paraphrase case не удалены. |
| `stale` | `_project_context_service_part01` требует текущие file/catalog hashes. Выдача старых sections запрещена; confirmed upsert заменяет sections выбранных members. |
| `orphans` | Удалённый/исключённый из catalog документ больше не принадлежит current candidates. `_apply_project_members` явно возвращает `sources_deleted=0`: физическое prune не объявлено выполненным. Original question про отсутствие старых данных в поиске сохранён; crosswalk и docs явно раскрывают границу read exclusion / physical cleanup. |

Это осмысленная migration obsolete product facts, не доказательство, что новая
формулировка буквально равна старому обещанию physical deletion или proof.

## Найденные и закрытые замечания

1. **Contamination false negative.** Первый вариант освобождал от проверки любую
   строку, где одновременно встречались Docs и Packs commands, либо отрицание
   относилось к чужой Docs command. Поэтому пропускал:
   `Do not run doc-atlas mcp docs-serve; use doc-atlas mcp packs-serve for Docs.`
   и `For Docs use doc-atlas mcp packs-serve; doc-atlas mcp docs-serve is broken.`
   Автор убрал blanket exemption, проверяет каждый Packs occurrence и связывает
   отрицание с его непосредственным prefix. Оба counterexamples добавлены в
   существующий control test. Повторное чтение: замечание закрыто.
2. **Duplicate catalog paths.** Проверка только active dictionary пропускала
   inactive→active duplicate. Автор ввёл отдельный `seen_paths` до active filter.
   Повторное чтение: замечание закрыто; текущие 14 members не изменились.
3. **README action name.** В одной старой таблице оставалось `next_action` при
   текущем `recommended_next_action`. Автор исправил таблицу на `recommended_next_action`. Повторно
   проверены README bytes/hash и protocol→acceptance lock chain: замечание закрыто.

## Предел review

Полный source identity/snapshot correctness, runtime original coverage, V2
quality, MCP transport и настоящие клиенты этим source review не доказаны.
Новый live failure после устранения catalog barrier остаётся настоящим failure,
а не поводом ослаблять gold или засчитывать lookup как original coverage.

## Итоговый source review

**APPROVE** после закрытия всех трёх замечаний. Runtime evidence этим review
не заменяется.

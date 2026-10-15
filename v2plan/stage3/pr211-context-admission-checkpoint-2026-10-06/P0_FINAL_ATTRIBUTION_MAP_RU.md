# P0 gap 1 — конечная карта original/lookup attribution

**Gap 1 закрыт как source inventory/map (24 именованные ветви), не как acceptance
semantic equivalence или replacement.** Остаточных неизвестных механизмов в
перечисленных family branches нет. Общий P0 DONE, gap 2, baseline gate, P1 и
dictionary exit этим не меняются. Product/test/common файлы не изменены, новых
runtime probes нет. Машиночитаемый map и проверенные SHA/span pins:
`archives/p0-final-attribution-map.json`.

## Термины и граница доказательства

В assessment `query_matches` — сокращённое обозначение: actual production key
**`retrieval_query_matches`**. Public DTO его удаляет; наружу выходят
`covered_query_ids`, `missing_query_ids`, query/retrieval coverage и facets.
Snapshot содержит raw `source` и public `projected_source`; raw trace не следует
автоматически считать trace последнего видимого crop. Это существенно для joint,
context-only fallback и restored hint branches.

Все ссылки ниже относительно `docmancer/docs/`; JSON фиксирует полный путь,
inclusive source span, exact evidence substring и SHA256 **всего файла**.
Это source evidence, не universal Python graph и не подтверждение исполнения.

## Producer → relation → parent (исчерпывающие именованные семьи)

| ID | Producer / span | Решение и дальнейший маршрут |
|---|---|---|
| A01 | `domain/documentation_query_plan.py:405–412,75–118` | Original — `direct`; force-context-only может снять required, но origin остаётся public. Public membership определяется origin, не equivalence. |
| A02 | тот же файл `:512–527`; `_host_lookup_can_derive_original:209–248` | Первые пять supplied lookups: empty/exact original repeat пропускаются. Supported whole-question meaning → audited original parent; иначе reviewed single intent или conditional troubleshooting плюс guards, equal intent/canonical intersection; отрицательный исход — independent `host_lookup` без parent. |
| A03 | `domain/admission_meaning.py:20–65` | Supported audit: compile обеих сторон, unknown/context/uncovered meaningful residue запрещает; ordered needs сравниваются по operator и canonical role/argument/constraint signature. Это semantic authority producer, не доказательство истинности equivalence. |
| A04 | `domain/documentation_query_plan.py:174–187,546–573` | Canonical original rewrite: literal casefold equality ИЛИ single reviewed force-context intent без technical/negation/premise/novel-topic/conditional guards ИЛИ отдельная RU installation-verification fullmatch. Иначе canonical alias остаётся parentless host relation. |
| A05 | тот же файл `:250–280,528–545` | Host-parent rewrites (всего ≤6): positive boundary fullmatch для anchored `get_docs_context`; selection fullmatch → два literals; либо single testing_contribution/index_chunking/evidence_selection force-context intent. Empty/anchors/negation/qualifiers reject. Parent — lookup, не original; parent exact terms берутся из lookup. |
| A06 | тот же файл `:482–510` | Path/technical anchors имеют original parent, но relation `exact_anchor`, поэтому parent derivation не разрешён. Plain lexical compounds — optional parentless `host_lookup`, не точная public identity. |
| A07 | тот же файл `:413–460,598–672` | need/part/composed probes, relation groups (comparison, axis/slash, if/when), mixed script/clause/requirement hints, concept aliases, exact component rewrite span/field audit — parentless hypotheses. Component audit не `audited_rewrite`; optional shared cap 4. Не создают original parent. |

`DocumentationLookup.__post_init__:51–62` проверяет shape: audited требует parent;
direct/host запрещают parent. Он не проверяет semantics supplied audited relation.
Alias/grammar/reference/need producers — известные semantic dependencies, не
новые technical exemptions. Конечные allowlists/regex choices перечислены выше;
полный transitive graph их parser internals не является scope этого gap.

## Discovery → независимый probe → последний crop

| ID | Source span | Actual contract / отрицательная ветвь |
|---|---|---|
| A08 | `application/reference_query_tagging.py:11–90` | Discovery trace получает relation, parent, policies и exact terms; `qualify_evidence` проверяет chunk body; typed need witness применяется; `derived_parent_trace` может добавить parent. Incoming lexical score/metadata не самостоятельная authority. |
| A09 | `application/_project_docs_service_part03.py:106–134` | Cross-lane independent original/host/need только без parent и отсутствующий trace; genuine discovery trace не перезаписывается. Cross-lane original помечается `admission_only=True`, score=0. |
| A10 | `application/context_query_probes.py:13–50` | На crop добавляет отсутствующие parentless original/host/need. Original/need требуют qualification; original admission-only. Host дополнительно body term floor и distinctive term относительно других independent lanes. Existing trace не заменяется здесь; затем core requalifies его. |
| A11 | `application/_docs_context_projection_core.py:868–937` | На current path/section/snippet rebuild matches; supplied derived-parent trace с `derived_from_query_id` пропускается; aggregate lineage очищается. Original exact identifiers добавляются заново; qualifier и need witness пересчитываются; parent derive заново только для surviving child, present in query_text. Не происходит recursive transitive promotion lookup→original из уже derived parent. |
| A12 | `domain/evidence_qualification.py:202–239,271–504,520–539` | Scope/identity/currentness/risk/lifecycle, forbidden terms/roles, reference binding, substantive body, negation/comparison local relation, exact path, body/heading/table subject context, exact/parent-exact и lexical ratios, typed/legacy admission. Parent требует qualified audited relation, непустой parent и отсутствие missing_parent_exact. Parent-exact отсутствие блокирует parent, не обязательно child. Supplied audited contract не independently certified здесь. |
| A13 | `application/_project_docs_continuations.py:19–99`; core `:875–893`; `context_query_probes.py:78–93` | same atom/list-item contiguous provenance; structural derived canonical trace проверяется policy/reference на crop. Special route исключает `query-original`, не создаёт parent trace. Это structural retention, не proposition/equivalence proof. |
| A14 | core `:238–340,467–517,796–866`; `context_variant_retention.py:127–294` | Full candidate qualification, rolling-focus и exact block crops → injected requalifier. Required whole-block interiors удаляются; bounded contiguous union ≤640 requalifies и сохраняет обе directions; complete/coverage/component/assignment/cost ordering — отдельная preference. Same-ID replacement merge → requalify; no-lost query/component/command/mandatory guards. Disjoint new evidence ID только с independent novel direction. Expansion requalifies каждый принятый crop, retains public IDs/component/assignments и budget. |
| A15 | `application/context_selection.py:156–166,255–320` | `qualified_query_ids` включает admission-only; `attributable_query_ids` исключает его. Merge winner: qualified, direct, score; qualified lineage агрегируется. Это supplied-trace merge, не equivalence audit и не глобальный запрет genuine original discovery. |
| A16 | `application/_docs_context_payload.py:11–142`; core `:719–743` | Decision строит public covered/missing из attributable IDs; facets отдельно требуют canonical assignment для covered, broad-context остаётся unverified. Private matches удаляются, snapshots rebound. Answer/available/edit false и retrieval-only не удостоверяют корректность original attribution. |

## Fallback, facade и конечные replacement branches

| ID | Source span | Preservation и источник конечного claim |
|---|---|---|
| A17 | `domain/context_hint_policy.py:9–50`; core `:665–710` | Hint только unresolved broad без hard-stop/component/explicit path/specific contract; raw substring hint и body ≥2 floor — semantic choices. Empty primary retries hints один раз; после allowed/нет hints — need-context fallback; иначе insufficient без sources/coverage. Hints сами не derivation authority. |
| A18 | core `:744–791`; `visible_evidence_retention.py:8–53` | Partial primary rerun hints при spare source slot и missing directions/components. Accept только strict superset IDs, restore original visible rows и snapshots, snippet retention и budget. Coverage packet остаётся от hinted trial; restore не делает повторный attribution decision. Это конкретный consumer contract, не утверждение семантической корректности trial после overlay. |
| A19 | `need_context_projection.py:108–155,158–215`; core `:362–463` | `compile_need_contracts`/`classify_need_context`, precedence/list preferences допускают checked context без query matches; contextual empty fallback также no-credit. Raw snapshot original может содержать прежние discovery traces, но public covered из empty matches. Не принимать raw snapshot за final requalified trace. |
| A20 | `docs_context_projection.py:32–82,198–289` | Default facade injects dynamic public helper hooks (selection/coverage, fragments, focus/ranking/expansion/requalify); private shard patch сам по себе не default evidence. Final quality использует surviving public snippets. Read-next compaction на clone: IDs/snippets/covered queries/components retain; rejected trial не заменяет retained diagnostics. |
| A21 | `joint_context_candidates.py:19–82,104–140`; `joint_seed_envelopes.py:13–56`; `joint_context_lineage.py:12–64` | Original / complete_atom / containing_section / root prose intro / same-section seed envelope. Snapshot hash/path/project/reference проверены; intro clears matches; non-supplementary replacement intentionally retains seed attribution (не расширяет). Occurrence mapping требует unique same-identity containment; не semantic proposition proof. |
| A22 | `joint_context_selection.py:85–202,205–255` | Host-origin bypass, checked/empty/non-retrieval flags reject; full draft yield не проходит subset requalification. Proper subsets/coalescing inherit origins, policy check, per-origin requalify/merge, retain attributable coverage. Затем finish quality/read-next, budget/validator/covered IDs/components retain. Requalified matches пишутся в binding `source`, не public row; `covered_query_ids` trial inherited. Ranking gain closure/coalescing/intro, затем min-cost; containing/envelope fallback при no gain. Не выдаём branch guards за fresh final public attribution reconstruction. |
| A23 | `query_block_context.py:80–172`; `query_block_bridge.py:9–51` | После joint есть supplemental block (no matches/credit) либо adjacency bridge: только headings/whitespace gap, exact document span, requalify и no-lost qualified IDs. Host/checked/empty/cap bypass; finish/mapping/validator/reader retain. Bridge меняет binding trace, публичная coverage не пересобирается. BM25/subject-lead preference не semantic proof. |
| A24 | `query_block_recovery.py:22–128`; `interfaces/mcp/context_tools.py:394–480` | Последний recovery выбирает unissued inspection range (в empty case inspection seed), не credited source/coverage. Host/checked/requested-part target bypass; read-next/label/locator budget changes. MCP вызывает facade default hints=false, binds readers, validates final packet against snapshot, records bytes/observes и возвращает DTO. Validation format/lineage не independent rewrite authority. |

## Decisions и preservation: reconciliation, не approval

`archives/p0-parallel-closure-assessment.json` row core `project_docs_context`
оставлял OPEN final attribution map, одновременно уже классифицируя canonical
origins, parent/hint/lifecycle, authority/novelty/admission и need-context priorities
как semantic/mixed. Row `packet_alternatives` — known semantic dependency, не
technical exemption. Настоящий map конкретизирует эти решения A01–A24, не
переклассифицирует их в RETAIN и не заявляет implemented REMOVE/SPLIT.

`archives/parallel-hint-REPORT_RU.md:18–36,50–79` различает independent
admission-only representation от public attribution, genuine discovery original
от cross-lane original и duplicate self-merge от heterogeneous windows. Это
историческое bounded probe evidence (normal/crop/merge/foreign/unrelated/forged),
не новый run на этом tree и не blanket approval winner rule. Map не требует
запретить все internal original IDs или добавить всем `admission_only`.

Preserve separately: exact original/lookup text and scope; hard exact subjects,
conditions/negation and parent exact requirements; source project/currentness and
policy rejection; actual unique occurrence, snapshot/version/catalog identity;
crop-local assignment/components; mandatory direction/command retention; original
primary quotes under hint retries; unread obligations/issued reader boundaries;
packet budget/caps; public partial/no-credit distinction and false answer/edit flags.
Техническое сохранение этих контрактов **не** санкционирует semantic defaults,
alias equivalence, ranking priorities или parent relation producer.

## Итог gap 1

Именованные producer/probe/crop/hint/joint/facade/final consumer branches учтены,
включая no-credit и inherited-claim branches. **Inventory remaining gap = none.**
Проверка: 78 hash/span evidence checks, 24 unique branch IDs, все graph edges
разрешены; ошибок 0. Product tests/baseline не запускались.
Открытая будущая acceptance obligation: независимо обосновать semantic rewrite
authority и preservation конечного public attribution на inherited/overlay/coalesced
packets. Она не скрыта как technical exemption и не является причиной объявлять
конечный source map незавершённым. Gap 2 canonical support witness и baseline
reconciliation остаются вне этого exclusive output.

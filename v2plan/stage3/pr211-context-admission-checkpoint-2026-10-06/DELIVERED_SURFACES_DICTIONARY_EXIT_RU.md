# Delivered surfaces: второй disjoint dictionary-exit slice

2026-10-06, primary `/tmp/opencode/docatlas-stage3-integration-active`.
**Scoped implementation complete; full dictionary exit NOT DONE.**
Первый corpus/template/workflow slice находится на отдельном review и не изменялся
этим allocation. SDK/read-tail/audit changes соседних исполнителей не трогались.
Все четыре явно выделенных production paths существуют; guessed paths не использовались.

## Exact files / diff

Production changes только:

1. `docmancer/mcp/_docs_server_shared.py`
   - Удалён `_GET_DOCS_CONTEXT_SCOPE_GUIDANCE` topic→scope и его runtime replacement.
   - Lookup description: original unchanged + explicit same-question lookups ≤5;
     no inferred rewrite/translation/subquestion, lookup coverage не переносится.
2. `docmancer/mcp/_docs_server_tool_data.py`
   - Raw/public descriptions и lookup/schema **description strings** очищены от
     topic scope, obligatory semantic decomposition и module+policy split rules.
   - Advanced code/patch descriptions больше не выводят answer/edit authority
     из safe_to_answer flags, implementation map или retrieved constraints.
   - Public status явно read-only/not discovery; preparation сохраняет returned
     actions/explicit lifecycle, consent и retry only after success.
   - Schema properties/types/enums/defaults/required/limits/patterns не изменены.
3. `docmancer/mcp/_docs_server_resources.py`
   - Static quickstart/project/library/tool-selection texts: literal question,
     explicit lookups/cited context; no gapsplitting, inferred bridge questions,
     relation-specific proof, rephrase execution или hard_stop absence→edit.
   - Убрано inferred with_vectors selection по retrieval mode; exact returned
     preparation arguments и approval остаются authority.
   - Resource URIs/names/mime types, trust-contract JSON и URI templates сохранены.
4. `SKILL.md`
   - Нет unconditional scope=all examples, semantic translation/decomposition,
     CHANGELOG-by-topic authority, implied proof или edit readiness.
   - Original+explicit lookups ≤5+cited context; explicit scope/version/provenance,
     network consent, successful lifecycle retry и status nondiscovery сохранены.
   - CLI command/flag tables и Packs protocol не перенесены и не переформатированы.

New-only files:

- `tests/test_dictionary_exit_delivered_surfaces.py`
- `tests/diagnostic_labels.dictionary_exit_delivered_surfaces.json`
- Этот checkpoint report.

Не менялись first-slice fetchers/templates/workflow/tests, old tests, gold, frozen
artifacts, thresholds или source manifests. Network/commit/push не выполнялись.

## Technical table classification

| Сохранённый механизм | Основание / проверка |
|---|---|
| RAW/public input/output schemas | Exact wire/validation contract; все constraints без description strings совпадают с pre-slice SHA-256. |
| Tool names/order и ADMIN/ADVANCED/PUBLIC classifications | Feature flags и handler registration, не topic dictionary; 8 config combinations проверены. |
| scope enums / project_path / library / version / module_path | Explicit identity/scope inputs; никакого inferred authorization из question. |
| version description / lifecycle recovery | Current project omits version, explicit exact/historical binding, requery after lockfile change; terminal-success retries и returned job status preserved. |
| Resource URIs / names / mime types / templates | MCP protocol identifiers; unchanged static routes и bounded source template. |
| trust-contract JSON source_dimensions | Provenance/version/repository authority/instruction trust раздельны; cited data не lifecycle instruction. |
| source continuation template | Только issued source_uri, 600 tokens/read, 2 reads/chain, never construct reference; unchanged. |
| Canonical agent contract hashes | Existing first-slice producer продолжает hash-ить **actual runtime descriptions/input/output/tool records**; mutation test проверяет смену identity при смене actual description. |
| Input and output budgets | max5 unique lookups, nonempty item, max500 chars, invalid requests fail before handler; existing footprint floor не изменён. |

Schema constraint pins (canonical sorted compact Unicode JSON, descriptions removed):

- RAW schemas by tool name: `b1dcc4b386d8c6a9aeb2cbdb201ff59565a884f35d4baf73b4b800ddaafea201`
- Advertised input: `0cde87ff219c430fd9c74558d3db852869f88e7aba8ba4aaef6747b45f2b90fd`
- Advertised output: `76e20412ff93662d7379e912192ffd5f6c413507dc3e7e64c14e55335995aa23`

Measured default public tools catalog: **6126 bytes**, unchanged target ≤6144,
hard ceiling ≤10240. Небольшой запас не разрешает последующие silent budget expansions.
Actual agent identity этого snapshot:
`sha256:3268e3d9e5c16994905c23b23dc641a4733ec725067a8d0b7e067ee873e5046d`.
Это content identity, не full exit approval, release freeze или semantic proof.

## Tests: normal conftest / hash shard / honest mixed reds

Commands use `PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -p no:cacheprovider`.
Ни `--noconftest`, ни изменения old assertions не применялись.

| Проверка | Latest result |
|---|---|
| New delivered-surfaces module | **33 PASS**: 22 behavioral / 10 schema / 1 artifact instances; 11 base nodeids. |
| New + bounded technical modules | **82 PASS / 1 FAIL** (83 total), 1 existing multipart deprecation warning. |
| Combined new/technical/old mixed run | **146 PASS / 28 FAIL** (174 total), 1 warning; это RED, не acceptance. |
| Earlier technical run до additional 3 schema cases и concurrent patch-path change | **80 PASS**; historical result, не latest safety claim. |

New node hash shard:
`d0a7e775060906b20684e7c4e6a39cfe9e16f5fba2750167aa33f4e8704fe67c`.
Label maps reviewed separately: schema descriptions/pins and explicit examples
не выдаются за behavioral retrieval correctness; root guide check artifact-only.

Bounded technical modules:

- `tests/docs/test_mcp_token_footprint.py`
- `tests/docs/test_mcp_boundary.py`
- `tests/docs/test_finalized_mcp_output_integrity.py`
- `tests/test_support_surface_policy.py`

Последний technical red:
`tests/docs/test_mcp_boundary.py::test_patch_constraints_debug_compaction_preserves_contract_fields`
ожидает `answer_available is True`, получает False. Этот assertion проходил в
earlier run; failure относится к concurrently changed non-owned patch execution
path. Root cause / acceptance здесь не устанавливались; policy не восстанавливалась.

Old mixed modules (64 PASS / 27 FAIL внутри последнего combined run):

- `tests/docs/test_mcp_docs_tools_registration.py`
- `tests/docs/test_active_mcp_examples.py`
- `tests/docs/test_host_scope_contract.py`
- `tests/docs/test_host_scope_planning_contract.py`
- `tests/docs/test_agent_question_planning_contract.py`
- `tests/docs/test_agent_recovery_version_guidance.py`
- `tests/docs/test_bounded_response_docs_parity.py`
- `tests/docs/test_readme_mcp_keyword_contract.py`
- `tests/docs/test_tdd_documented_request.py`
- `tests/docs/test_self_host_agent_contract_surface.py`
- `tests/test_unified_docs_context_mcp.py`

Red categories: removed topic→scope/decomposition/gap/public proof compatibility;
first-slice rendered-template/field expectations; unavailable module/self-host
context; pre-existing Kotlin/project preflight recovery expectations. Это не
full-baseline attribution experiment: shared tree одновременно изменяется.
Source retrieval quality/full CI/MCP stdio smoke не переснимались, старые quality
reds и frozen gates не закрыты technical schema PASS.

## Source pins этого slice

| Path | SHA-256 |
|---|---|
| `docmancer/mcp/_docs_server_shared.py` | `d8dab26965217bb15f60bb779dece3fb8e5527b525d523c7ffff10e6b9b2d6b1` |
| `docmancer/mcp/_docs_server_tool_data.py` | `52f396b654ef1fe941967090ced33e2130adb454072143e8806100a28c626ca0` |
| `docmancer/mcp/_docs_server_resources.py` | `05f8520723f90d92c7cb78aeaac07967ba5b01febbfa9bf7628afde7a70130c0` |
| `SKILL.md` | `1a01d766b451869ffd16426c357afe2a62b4e74a2e0ab8630cb6f546aa9818c9` |

## Parent dependencies / OPEN

1. **Not owned:** `docmancer/mcp/_docs_server_part01.py:read_docs_resource` renders
   dynamic URI-template workflow bodies. Existing project example includes
   non-public `mode="auto"`; library example includes non-public `mode="library"`
   and `ecosystem` on `get_docs_context`. Existing retry guidance also lacks
   terminal-success/explicit returned-action guards. Не менять schema для этих
   examples: нужен отдельный allocation to renderer, не guessed API.
2. Static owned resource guidance и root guide теперь согласованы с first-slice
   literal policy, но остальные maintained docs, generated installs/release
   artifacts и source manifests не входят сюда. Parent должен проверить remaining
   packaged/generated surfaces и публиковать actual new identity без переписывания freeze.
3. Latest patch-boundary red передать SDK integrator/reviewer; не исправлять
   removed-policy compatibility восстановлением answer/proof authority.
4. Corpus locale/topic/generated discovery exclusions по-прежнему **BLOCKED**;
   удаление без explicit bounded corpus contract расширило бы authority.
   Full D32/D33/D38/all-runtime dictionary exit **NOT DONE**.

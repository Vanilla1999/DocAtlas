# Step10 installed full-scope performance diagnosis

## Result: dependency graph work dominates before MiniLM

One real installed public `get_docs_context` call was deliberately interrupted after **30.070 seconds** by a diagnostic SIGALRM. It did not finish retrieval/preparation, did not reach model scoring, and is **not a partial product success**. No product timeout/quota was added. No production code, source corpus, prepared store, wheel or ongoing Terra measurement was changed.

Unchanged original T01-ru request (no speculative lookups/translation/focus):
`Что от меня ожидается, когда я отправляю pull request в DocAtlas?`

The first interval identifies a general structural preparation defect, not topic relevance: full-document dependency graphs are rebuilt thousands of times for native windows whose source identities are interleaved. The installed `source_graph` cache holds only 16 documents, while the corpus has 489 documents. Candidate scan is ordered by hydration_id, not grouped by source. Cache churn makes a source-local operation effectively repeated per source window. Independent span validation then repeatedly hashes/scans full graph/document structures.

## Exact diagnostic setup

* Interpreter: `/tmp/opencode/step10-mini-py313/bin/python` (same server executable environment as runner config).
* Imported package: `/tmp/opencode/step10-mini-py313/lib/python3.13/site-packages/docmancer/__init__.py`; asserted installed site-packages, no source PYTHONPATH injection.
* Config/environment copied directly from `/tmp/opencode/terra-step10-final/L2/minimal-context/opencode.json`, `mcp.servers.docatlas` environment and cwd.
* Prepared root: `/tmp/opencode/step8-corpora2/L2-0`; project binding is runner's exact JSON binding. Offline model and policy paths unchanged.
* Real factory `create_local_mcp_service` and public `call_docs_tool_payload`; no mocks, no component substitutions, no reindex/prepare operation.
* SHA256 before/after for all 489 project Markdown files and prepared `.db` (490 watched files total): **unchanged**.
* Initial launch failed before profiling/public invocation due to importing factory from facade instead of `_docs_server_part01`; corrected diagnostic import. Exactly one timed public call was executed.

Command:

```sh
env -u PYTHONPATH /tmp/opencode/step10-mini-py313/bin/python \
  /tmp/opencode/step10-performance-profile.py \
  --config /tmp/opencode/terra-step10-final/L2/minimal-context/opencode.json \
  --out /tmp/opencode/step10-performance-profile-02
```

## Profile measurements (overlapping cumulative times, not additive)

| Function/stage | Calls | Cumulative seconds |
|---|---:|---:|
| Dispatcher `run` | 1 | 2.163 |
| SQLite candidate iterator | 11,861 resumptions (11,860 rows) | 0.737 |
| `SourceReferenceContext.prepare` | 1 | 25.388 |
| `prepare_dependency_sets` | 1, still running at abort | 20.775 |
| `build_dependency_sets` | 8,181 | 16.750 |
| `_build_source_sets` cache misses/body executions | 8,181 | 16.666 |
| `source_graph` cache misses/body executions | 7,695 | 12.773 |
| `parse_markdown_parents` | 8,184 | 5.298 |
| `validate_evidence_set` | 8,115 | 3.781 |
| `_closure` | 9,668 | 1.520 |
| SQLite `fetchall` | 585 | 2.270 |
| SQLite connection `execute` | 5,920 | 1.704 |
| `_validate_read_generation` | 592 | 1.680 |

Parser caller breakdown is decisive: **489 calls** from `_document` (0.232s) versus **7,695 calls** from `source_graph` (5.066s). All 7,695 graph misses originate from `_build_source_sets`, not the later validator. Source-native document hydration already caches one parse per document, but dependency preparation reconstructs another graph repeatedly.

Total recorded activity: ~73.98 million calls, ~57.65 million primitive calls. Built-in hash invoked ~20.10 million times (3.086s own time); source/span dataclass hashing and graph edge set operations account for much of that. Graph generation also repeats `_atom_spans` (95,061 calls), text splitting, SHA256 construction (~988k calls), and JSON/dataclass operations.

The SIGALRM stack is:

`call_docs_tool_payload → get_docs_context → get_project_context → get_project_docs → query_project_docs → _run → SourceReferenceContext.prepare → prepare_dependency_sets → build_dependency_sets → _build_source_sets → source_graph → _list_parts`.

No MiniLM scorer/model forward occurred in this interval. Single-CPU activity here is consistent with Python parsing/hashing/validation; changing model thread count would not address this stage. The previously fixed repeated dispatcher-per-lookup problem is not present: exactly one dispatch and one prepare were reached.

## General mechanism confirmed by installed code

* `source_dependency_graph.py:72`: `@lru_cache(maxsize=16)` over full raw document + SourceKey.
* `source_dependency_preparation.py:17–41`: loops every retrieved native window, calls `build_dependency_sets`, then validates each proposed bundle.
* `evidence_set_validation.py:79`: `_build_source_sets` cache size128 but key includes window start/end, so distinct native windows still miss. Each miss obtains the full graph, scans graph nodes for overlap, computes closure scanning graph edges, then builds sets.
* `validate_evidence_set`: `span_matches_source` hashes full raw source per span, constructs sets from full graph edges/nodes, and scans dependencies again. Cache hits alone do not remove these repeated whole-document checks.
* `prepare_dependency_sets` still computes/validates bundles even after its old 24-result proposal limit is filled. This is both wasted work and a legacy proposal limit; it is not a reason to cap candidate source membership. The new full structural selector has a different closure implementation. Whether the old proposal preparation can be skipped for candidate needs owner review of remaining provenance consumers.

## Coordinated correction direction (not implemented)

1. Give structural preparation a request-local immutable per-source graph (or process windows grouped by full source identity and restore original ordering), avoiding 16-entry global cache churn. Do not merely introduce another corpus/window quota.
2. Bind graph/hash validation to immutable prepared source identity once per request; retain independent exact span and terminal source freshness/authorization checks. Never memoize authorization verdicts globally.
3. Index graph edges/nodes by span/adjacency instead of reconstructing and scanning whole graph for every window/bundle.
4. Audit whether candidate needs legacy bounded dependency proposals at all; if not, a candidate-specific bypass must preserve `_reference_evidence`/original-body receipts and rely on the already implemented complete structural closure, rather than remove source checks blindly.

These changes concern `source_dependency_preparation.py`, `source_dependency_graph.py`, `evidence_set_validation.py`, and `source_reference_evidence.py`; coordinate ownership before edits. No query/path dictionaries or frozen-answer-specific changes are appropriate.

## Limits and artifacts

This is a **first-30-second censored profile**, not a full latency attribution for the reported ~40-minute run. cProfile adds overhead, and later stages may have additional dominant costs. No inference about complete runtime reduction is justified. Shared machine contention may affect timings. Existing 16 Terra runs and their 900s censored results remain untouched.

Artifacts:

* Portable diagnostic source: `/tmp/opencode/step10-performance-profile.py`
* Raw profile: `/tmp/opencode/step10-performance-profile-02/public-call.prof`
* Receipt and interrupted stack: `.../receipt.json`
* Sorted tables: `.../cumulative.txt`, `.../tottime.txt`
* Caller breakdown: `.../hot-callers.txt`
* Installed relevant-code fingerprints: `.../installed-code-sha256.json`
* Console log: `/tmp/opencode/step10-performance-profile.log`

The diagnostic uses a BaseException-derived alarm to avoid ordinary application Exception handlers converting cancellation into a successful partial response. It writes only diagnostic output. Public request and model/policy/config are not tuned.

## Authorized correction implemented (source tree; installed measurement wheel untouched)

Changed production files:

* `docmancer/docs/domain/original_body_discovery.py`: capture documentation-only request mode; expose `minimal_context_documentation_read()`. Bypass is scoped to a live candidate project documentation request, not patch requests, explicit library requests or mixed mode.
* `docmancer/docs/application/source_reference_evidence.py`: after all existing source identity/generation/hash/span/owner preparation, candidate documentation reads return those prepared native rows without obsolete bounded dependency proposals. `_reference_evidence`, `_reference_root_plan`, `_reference_plans`, source snapshot hashes/member bindings and every candidate window remain intact. Request discovery receipts are still recorded by the owning public service immediately afterward. Stale `_evidence_sets` aliases are removed from the new request-owned metadata dictionaries, never trusted.

No graph or authorization global cache added; no fixed source/window/closure quota introduced. Other three authorized dependency modules need no changes because the candidate no longer calls that legacy algorithm. Legacy and patch proposal preparation stays intact.

### Why bypass is correct

Repository consumer audit found legacy `_evidence_sets` delivery consumer in `need_context_projection.py`, while the candidate's active path is `project_native_rank_context → select_minimal_context → minimal_context_structure.build_units/close_selection/recheck_structural_row`. The latter consumes exact `_reference_evidence` and live original-body/derivation bindings, not `_evidence_sets`. It has complete own-unit/subtree/ancestor/link/footnote closure independent of the legacy 2-hop/8-span/24-set proposals. The bypass occurs only after native source preparation and before request provenance recording; no source-check or receipt is synthesized/omitted. Existing successful public tests below exercise that actual boundary.

### Required verification: PASS

1. `DOCATLAS_TEST_MINI_MODEL_DIR=/tmp/opencode/step10-mini-assets PYTHONPATH=. /tmp/opencode/step10-mini-py313/bin/python -m pytest tests/test_context_portions_integration.py::test_minimal_candidate_public_full_scan_refs_and_scope -q` — **1 passed in 19.07s**. Real public MiniLM pipeline returns all 257 exact facts, excludes module-private source, retains 257 units/pairs, preserves first/last source refs, replay denial, stale denial, read-only DB and <=50k delivery. Log `/tmp/opencode/step10-performance-257.log`.
2. Existing `eval/blind_project_context/probe_minimal_structure.py` — **PASS**. Real public acquisition followed by observed actual structural closure retains ancestor intro/empty heading, selected subtree/tail, table/footnote/continued note, internal cycle and cross-document anchored dependency. Unchecked missing target is explicitly incomplete; unrelated noise excluded; exact source text/hash/native binding and expired-receipt rejection remain checked. Receipt `/tmp/opencode/step10-performance-structure.json`; log same stem `.log`. Boundary remains structural integration, not semantic threshold recall proof.

### Concrete L2 progress (same request/config/store, bounded 30s)

New repository diagnostic: `eval/blind_project_context/profile_minimal_context.py`. Default requires installed imports. `--source-root` explicitly labels a source comparison without changing the measured wheel. Captures phase call/time receipts, actual interrupted scorer counters if present, completed observer scorer receipts when available, explicit zero model calls when scorer not entered, source/DB SHA256 before/after, code digests and raw profile. No inferred batch→pair counts.

Ran one source comparison against the exact same runner config and original T01-ru:

```sh
env -u PYTHONPATH /tmp/opencode/step10-mini-py313/bin/python \
 /tmp/opencode/step9-gap-resolution/eval/blind_project_context/profile_minimal_context.py \
 --config /tmp/opencode/terra-step10-final/L2/minimal-context/opencode.json \
 --source-root /tmp/opencode/step9-gap-resolution \
 --out /tmp/opencode/step10-performance-fast-01
```

* `SourceReferenceContext.prepare`: **4.379s, completed**, versus old installed **25.388s, incomplete** when old alarm fired. This measured stage improvement exceeds 5.7× for the sampled run; it is not a full end-to-end speedup claim.
* `prepare_dependency_sets` and `source_graph`: **zero calls** after bypass (confirmed from raw pstats).
* Dispatcher: **one call, 2.139s**, still all 11,860 source windows.
* `query_project_docs`: **completed in 14.978s**; `get_project_docs`: 17.331s; `get_project_context`: 24.173s. Old run was still preparing dependencies at 30s.
* Cutoff now in downstream unified `annotate_context_pack → _policy_scope → Path.resolve`, after original candidate qualification and DTO serialization. Qualification costs 6.168s; `dataclasses.asdict` cumulative ~4.850s, unified `_to_dict` 3.840s. These remaining stages are outside this correction.
* Model load attempts/forwards/pairs at cutoff: **exactly zero** (scorer not entered), not an inferred throughput estimate. No completed L2 final packet or final latency claim.
* 490 watched files unchanged. `elapsed_seconds=30.1588`. Existing tests were independent concurrent jobs, so cross-run timing is diagnostic rather than controlled benchmark speedup.

Latest diagnostic received additional completed-scorer observation/phase-digest reporting after that run; AST syntax checked. Those additions do not change production behavior and no extra L2 run was spent merely to regenerate output fields. Existing raw profile remains available for phase analysis.

Artifacts: `/tmp/opencode/step10-performance-fast-01/{receipt.json,source-hashes.json,public-call.prof,cumulative.txt,tottime.txt}`, console `/tmp/opencode/step10-performance-fast-01.log`. Main can now build a separate finalfast wheel and repeat the controlled public diagnostic/probe without overwriting old-wheel 663e measurements. No installs, commits or ongoing-process changes performed here.

## Deeper installed finalfast profile: remaining quadratic packet serialization

Authorized exactly **one 120s** diagnostic on finalfast installed environment `/tmp/opencode/step10-final-py313`. Main identifies its wheel SHA256 as `174e837fa1c63c98132231fee236b21037a9b56e5055e25f321518d84d13f30c`; imported installed module paths and exact code digests are captured independently in the receipt.

Copied the runner JSON to `/tmp/opencode/step10-performance-finalfast-config.json`, changing **only** `mcp.servers.docatlas.command[0]` to the final environment's `doc-atlas`. Verified parsed config equality after restoring that one field. Environment, cwd, model/policy, prepared source and original question unchanged. `--source-root` was NOT used. No production files edited; diagnostic CLI now accepts explicit positive `--seconds` (default remains 30).

```sh
env -u PYTHONPATH /tmp/opencode/step10-final-py313/bin/python \
 /tmp/opencode/step9-gap-resolution/eval/blind_project_context/profile_minimal_context.py \
 --config /tmp/opencode/step10-performance-finalfast-config.json \
 --seconds 120 --out /tmp/opencode/step10-performance-finalfast-120
```

**Result:** diagnostic aborted at 120.205s; **model load attempts=0, model forwards=0, model pairs=0**, scorer not entered. All 490 watched source/database hashes unchanged. Graph bypass active: source preparation completed in 4.420s, one dispatcher call 2.134s; no legacy dependency graph phase.

The remaining dominant sampled mechanism is now proven directly:

`docs_context_projection.project_docs_context → attach_source_continuation_locators → _refresh_estimate(payload) → canonical_projection_bytes(payload) → json.dumps`.

Installed `_source_continuation_core.py:312–320` loops every source row, sets its URI, then calls `_refresh_estimate` **inside that row loop**. `_refresh_estimate` serializes the **entire growing all-candidate packet**, not just the changed row. This is quadratic-style repeated whole-packet pricing before semantic selection. There is no per-row membership/authorization decision in this loop that needs intermediate packet pricing. Snapshot source_uri assignments follow the estimate; final selected-packet pricing/authorization remain separate later operations.

Measurements (overlapping cumulative times):

| Phase | Calls | Seconds |
|---|---:|---:|
| `project_docs_context` (still running) | 1 | 86.104 |
| `attach_source_continuation_locators` (still running) | 1 | 42.681 |
| `_refresh_estimate` | 1,066 | 42.703 |
| `canonical_projection_bytes` | 36,089 total, including small hash materials | 42.959 |
| JSON encoder `iterencode` | 271,408 total | 38.341 own time |
| `project_native_rank_context` | 1 | 28.424 |
| `capture_experimental_context` | 1 | 14.985 |
| `_snapshot_entry` | 23,348 | 14.164 |
| `deepcopy` | 23,179,237 total / 70,336 primitive | 29.548 cumulative |
| Unified public service acquisition/result construction | 1 | 30.369 |

At cutoff URI-decoration had only reached roughly the first thousand refreshes for a preselection pool of ~11,674 accepted native rows. This is not a complete-loop timing; do not extrapolate it as measured final latency. Raw pstats contains exact callers. Additional copy cost is concrete: `_snapshot_entry` deep-copies each original metadata dictionary; `capture_experimental_context` deep-copies each unique candidate and again each alternative row/snapshot before selection. Those snapshots hold nested provenance/plans; immutable strings may be shared but the metadata containers are repeatedly copied. Eliminating these copies requires ownership/aliasing review, unlike moving a terminal size refresh out of a pure decoration loop.

**Coordination recommendation, not implemented:** references owner can batch URI attachment and snapshot binding, then refresh the full packet estimate once after the loop, preserving the final exact emergency pricing and every source check. Main owns `docs_context_projection.py`/`experimental_context_finalization.py` and can audit whether the candidate needs preselection locators and legacy native-alternative capture at all. Do not remove immutable provenance snapshots indiscriminately or cache access verdicts.

This falsifies any “cost fixed” claim from the earlier preparation improvement: **even finalfast has not reached inference by 120 profiled seconds**. Later model/structural/final-source checks remain unmeasured. No longprobe/Terra process was stopped, restarted, altered or polled by this diagnostic.

Artifacts: `/tmp/opencode/step10-performance-finalfast-120/{receipt.json,source-hashes.json,public-call.prof,cumulative.txt,tottime.txt,hot-callers.txt}`, console `/tmp/opencode/step10-performance-finalfast-120.log`. No further production edits pending main coordination.

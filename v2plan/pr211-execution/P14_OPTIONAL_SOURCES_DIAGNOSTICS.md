# P1.4: optional empty sources and diagnostic visibility

Base: `589a6366e33278fe542a0e3c971d2502e5e9f99f`. The three base files are byte-identical to the published P1.4 slice at `ec85a496`.

## Observed runtime

The actual P1.4 run [37974589158 / job113969530578](https://github.com/Vanilla1999/DocAtlas/actions/runs/37974589158/job/113969530578) completed all14 cases with no runtime errors. Current verdict: **0/14**, required discovery3/10, required complete facts2/5. All14 failed `read_only`; missing-source cases additionally failed the source-list oracle. Five oracle controls, current-report integrity and syntax checks passed. These observations are not acceptance.

The full JSON was uploaded as artifact11638078903, ZIP SHA256 `8dc3fe8741a7378c95a6295a218f12df36d81206e9f0d6c2faf0a62aa44c8bd3`. Its download reference was obtained; the ZIP contents were not decoded in the disconnected local environment. No unobserved before/after values are asserted here.

## Small correction

Current `project_insufficient` may legitimately omit `sources`. The source oracle now interprets **only absence plus status insufficient_evidence** as an empty local iteration list. It never inserts a field into the raw payload. Explicit null, dict, string or boolean values remain invalid, as does a successful response without sources. Binding-roster equality is always checked, including for malformed/omitted sources, so orphan bindings cannot disappear behind an early return.

The existing named negative control checks all these distinctions and raw-DTO immutability. It also retains the independent wrong-source and answer/mutation-authority negatives. No test function was renamed or removed.

## Read-only investigation

No before-snapshot, read-only condition, store hash, generation, document hash, catalog hash, preparation grant or production code is changed. No warm-up read was introduced.

The runner now prints one bounded diagnostic record per failing fixture. It includes differences for the four already observed state fields, before-field types, both generations, expected versus observed document hashes, source/authority errors, output-cost observations and runtime error. The saved report remains complete and is still written before validation/verdict.

Static source review identified a possible first-read write path: lazy default agent construction can call `SQLiteStore._ensure_schema`, which creates/drops `fts5_check` even for an existing database. This is a hypothesis until actual state differences identify the failing condition; no oracle relaxation hides it.

## Frozen scope

All14 original questions, facts, seven families,10 required discoveries,5 required full facts,2 negative controls, public request identity, source coordinates/hashes, no-lookups and no-answer/edit obligations remain unchanged. Historical protocol/report and migration sidecar bytes are unchanged. Output costs remain measurements without a fixed ceiling.

## Exact blobs

| Path | Base blob | Proposed blob |
| --- | --- | --- |
| eval/agent_developer_v1/current_retrieval_runtime.py | 8ad4d361764acfd123ce58da3259bac6b3b61867 | 866cd50bdb4605e511f386ba5bd2c7ebe84aba76 |
| scripts/paraphrase_proofability_self_test.py | 015eacc4fb8ef699eb36c1432040526533e47ad6 | 796822b217d70023a5252bf0ae534535abc30a54 |
| scripts/run_paraphrase_proofability_gate.py | 0cfcf8e9a8a3439b320ab9dfde784691ce9d4124 | 5141506048cfde8bf0fd3f2408afc621a110129e |

Remote roundtrip confirms exact contents. Local AST/import/runtime were not run because exec transport is unavailable. Ordinary P1.4 CI executes the unchanged workflow commands on the next published SHA.

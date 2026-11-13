# FRESH17 frozen evaluation protocol

## Seal and permitted access

24 cases = 12 semantic question families, each Russian/English; 6 dev families and 6 holdout families. All 24 are answerable in the separate FRESH17 corpus. There are **no negatives**: failure to retrieve is not an answerability-negative label. Russian cases send unchanged `question` plus the complete English translation in `search_question`; English cases omit it.

`questions.json` contains no gold, but DOES contain the sealed holdout. **Do not open the whole file during implementation.** The oracle, authoring record, and overlap audit are also sealed: `oracle.json`, `author.sealed.py`, `overlap-audit.sealed.json`. Do not open these until all compared variants' code, environment, policy, model assets, decoding/scoring code and execution plan are frozen and their exact hashes recorded. The adapter filters dev cases without printing holdout. For dev question review, a trusted evaluator may export only cases whose `split` is `dev`; do not expose the author record to get them.

No inference, API calls, tests, model outputs or model scores were used to construct this evaluation. Only repository source documents and old questions/oracle (to avoid old families) were read. The authoring command extracts immutable Git blobs, binds exact witnesses and writes the frozen files once. It refuses to regenerate questions. Do not change questions, gold, splits, witnesses or criteria after any output; errors require retiring this evaluation and declaring a separately versioned replacement, not repairing it toward PASS.

## Frozen corpus and rebuild recipe

This is **not L0 or L2** and must never be aggregated as another L0 result. L0's exposed questions already cover broad MCP, retrieval and operational families; adding more phrasing to those would not give an honest fresh set. FRESH17 contains seven real repository Markdown files at the manifest's exact source revision. It contains no invented fact documents or edited excerpts. Files were copied via `git show <source_revision>:<path>` preserving all bytes, and original relative paths were retained.

`manifest.json.documents` is the complete source list, exact-byte SHA-256 inventory, Git blob identity and byte size. To rebuild into a NEW directory, for each entry write `git show REV:path` to `NEW/project/path` and verify SHA-256 against that entry. Copy the supplied frozen `corpus/project/docatlas.project-docs.yaml` unchanged and verify `catalog_sha256`. No network is required. Catalog is JSON syntax (valid YAML), schema 1, finite explicit project entries, English language metadata, neutral filename-only descriptions, and no query-specific routes. Markdown links to excluded files are not corpus membership and must not be followed to supplement gold. Original documents remain unmodified; their full bodies provide natural distractors.

Copies remain under existing repository terms for this internal evaluation; no external material was imported. Do not infer a new distribution license from this protocol.

## Actual public MCP execution (future, not run by author)

Use a prepared Python environment containing the normal production dependencies. Do not use the main `run.py` CLI: it loads old questions and rebuilds L0/L2. The supplied adapter calls the EXISTING actual `run_unit` directly, not a replacement/private-helper test. It performs the real cold public `get_docs_context` call, real public `prepare_docs` with explicit catalog-member grant, then the unchanged frozen cases over actual stdio MCP. No selector or source modifications are included.

Example, relative to repository root (OUT and WORK must be new paths):

```sh
python3 eval/blind_project_context/step17-pipeline-study/fresh_eval/run_fresh.py \
  --split dev --out OUT --work WORK --source-tree CHECKOUT --env-json VARIANT_ENV.json
```

For holdout use `--split holdout --variants-frozen VARIANTS_FROZEN.json` only after the freeze. The receipt must bind each compared variant's exact commit plus dirty-code hashes, environment values/hash, model asset/policy hashes, Python/package versions, shared corpus/questions/oracle hashes, adapter and decoder/checker hashes, call limits and planned order. The flag is a procedural acknowledgment, not cryptographic access control. Maintain this boundary organizationally.

The fixed primary endpoint is one returned portion per case (`portions=1`), isolated work/home/storage for every variant/split, no reused stores and no hand-authored lookups. Observe=False deliberately prevents old observer gold entering the server process. The runner's ordinary explicit offline environment is retained; variants' predeclared environment is recorded. Do not supply corpus-changing paths, oracle paths or an arbitrary replacement transport via environment. Preserve full raw payloads, stdout/stderr, preparation errors and receipts. A preparation/server error is an execution failure, not a semantic negative. No claim that the adapter has been runtime-validated: author was explicitly prohibited from tests or inference.

## Offline fact and answer checks

After all variants freeze, run the offline checker on saved **actual MCP** artifacts:

```sh
python3 eval/blind_project_context/step17-pipeline-study/fresh_eval/check_delivery.py OUT \
  --variants-frozen VARIANTS_FROZEN.json > DELIVERY_REPORT.json
```

It hashes exact docs, questions, oracle, manifest and payloads. Existing production codecs only decode the wire representation; independently implemented literal-span checks place each delivered row inside its cited frozen source lines. Ambiguous/nonliteral/out-of-corpus rows are anomalies, never automatic passes. Union of unique exact row spans must cover each fixed witness, including its qualifications. Line endpoints are inclusive and 1-based; character endpoints are half-open and Unicode-based. Adjacent windows can jointly cover a witness. Whole paragraph witnesses are intentionally stricter than keyword hits. No semantic relevance inference is performed by this checker. It does not independently certify every metadata provenance field; retain original payload metadata for a separate audit.

The oracle's `topics[].facts[]` contains required complete-answer obligation groups (not only a few easy key phrases), each with `obligation`, exact `quote`, path, line interval, character interval and source SHA-256. Every material condition and exception in the bound passage must remain in a complete answer. Some groups cover several conjunctive facts, so report group counts, not misleading atomic-fact totals.

Two different endpoints MUST stay separate:

1. **Retrieval witness delivery:** all fixed required source spans delivered, no source/span/hash anomalies. Missing context is retrieval incompleteness. The checker measures this only.
2. **Final answer completeness (if a later preregistered answering stage exists):** an independent evaluator checks each obligation semantically against the saved answer, including all listed conditions/exceptions, correct scope/historical tense, and citations resolving to the frozen path/span/hash. Quotes need not be copied verbatim into the answer. Contradictions, unsupported additions, treating a plan as completed implementation, or an omitted material exception prevent complete-answer PASS. Do not mistake retrieved source presence for a correct answer. Do not use a model's output to alter obligations.

A purely retrieval run has **NOT_MEASURED** final-answer correctness. No model-based judge or inference is required to apply the offline/manual rubric. Source documents are the authority, not production selection helpers. No mock, private helper test, internal flag, exit status or mere citation presence proves fulfillment.

## Reporting and limitations

Report dev and holdout separately, English and Russian separately, then paired family outcomes. Do not count translations as independent questions. Report each case's missing obligation groups, anomalies, runtime/errors, and the full-family all-obligation rate. Freeze any optional cost or recall metric before opening holdout. Missing records count as failures; do not drop them. Aggregate inferential statistics are not justified by this tiny clustered set.

Seven documents span multiple but related development, support, release and change-review policies. Families are distinct decisions, not statistically independent domains. Some source documents are shared between families; dev and holdout use disjoint document sets, but all are from the same repository. This is independent source-grounded authorship relative to old questions and outputs, **not** proof of no model pretraining, no prior Lead source exposure, or external-project generalization. The sealed overlap audit identifies nearest old topics and substantive differences, including near-domain overlap instead of claiming independence from wording alone.

Facts are claims of the pinned documents, potentially historical or planned. They do not establish present-day package availability or implementation correctness. This all-answerable, modest corpus cannot establish behavior on no-answer questions, production-sized retrieval, adversarial documents, or hidden link completion. Construction completed without runtime testing as requested.

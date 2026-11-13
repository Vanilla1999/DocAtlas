# FRESH17 infrastructure review (no results)

Scope: only adapter/checker and this note changed. Protocol and runner source read; no sealed questions, oracle, author, overlap audit, manifest or corpus contents opened during review. No inference, public calls, imports of application modules, tests or checker execution. Validation is AST parsing only. Frozen hashes were not changed.

## Comparison contract

The owner's current same-prepared-work instruction supersedes PROTOCOL's old separate/no-reuse-store sentence. The original public `run_unit(..., observe=False, reuse=..., portions=1)` remains the only execution path. Question text and frozen Russian search translation pass through unchanged; no case-specific additions. Unknown environment names are rejected. Cache and compressed selector-trace destinations are generated inside owned work/output, not taken from arbitrary environment paths.

Cold invocation requires a new work root; reuse requires that exact work root and split, exact frozen corpus/catalog membership and bytes, and a successful snapshot receipt. All files under the prepared unit root (including settings/store/cache) are hashed and must remain byte-identical before and after reuse. An exclusive nonblocking work lock serializes cooperating adapters. Bypassing this adapter bypasses its advisory lock. Any file drift, including benign SQLite/cache drift, fails closed; there is no refresh, repair or automatic deletion. Output/work must be disjoint. Each run requires at least 1 GiB available on both filesystems; this is a floor, not an upper growth bound or disk reservation.

**Important first-run limitation:** original `run_unit` combines cold probe, preparation and first case execution. Its first snapshot can only be recorded after that invocation returns. Treat the cold invocation as setup, not an equal-prepared-snapshot comparison. Run the reference arm again with `--reuse-work`, followed sequentially by the other arms, against the sealed snapshot. No claim of runtime validation or semantic store-identity equivalence from hashes alone.

## Artifact retention

The adapter never invokes recursive removal. Full selector traces target `.jsonl.gz`. The unchanged original runner still writes raw MCP payloads, stderr and record journal while executing; in `finally`, the adapter losslessly compresses each exact artifact, verifies SHA256 and uncompressed byte count, persists a compact compression registry, then removes only that verified exact plain file. Stores/cache are retained. This is **post-run compaction**, not streaming compression of the original runner's outputs; interrupted processes can leave plain artifacts. Achieving fully streaming original-runner outputs requires a separately reviewed change outside adapter ownership. No automatic cleanup is attempted for other artifacts.

## Checker

Explicit freeze receipt required, bound to the run. Only offline invocation opens sealed oracle. Existing production codecs decode actual MCP source rows; all literal placement, unique occurrence within cited inclusive line range, source-byte hashes and witness-span union checks are independent. Missing, duplicate, malformed or errored payloads cannot pass. Every expected selected case contributes all required obligation groups, including missing records. Final-answer correctness remains NOT_MEASURED. Raw-wire cost is `max(o200k_base tokens, ceil(UTF8 bytes / 4))`; missing costs remain null, never zero. `tiktoken`/encoding availability is mandatory. Both plain and gzip payloads are supported. Output is compact JSON.

Schema v2 run receipt: split, manifest/questions/environment/adapter/runner/freeze hashes, exact expected_case_ids, shared work, reuse_work, observer=false, portions=1, status, units[].records[], snapshot_sha256 on success. Snapshot receipt: work, manifest hash, full relative file/hash inventory. Compression registry: original path, archive path, decompressed sha256/bytes, archive sha256. Checker: expected/present/passed cases; required/delivered groups; per-family all-case outcome; per-case facts, anomalies and wire costs. It is a retrieval witness metric, not answer scoring or statistical generalization.

## Future commands — NOT executed

From repository root, prepare a reviewed env JSON using only the adapter's finite allowlist; use the same nonempty freeze receipt on all scored arms. Model assets must already exist locally. Substitute new absolute OUT paths and a stable absolute WORK outside this source directory:

```sh
F=eval/blind_project_context/step17-pipeline-study/fresh_eval
python3 "$F/run_fresh.py" --split dev --out "$OUT_SETUP" --work "$WORK" --source-tree "$CHECKOUT" --env-json "$CONTROL_ENV" --variants-frozen "$FREEZE"
python3 "$F/run_fresh.py" --split dev --out "$OUT_CONTROL" --work "$WORK" --reuse-work --source-tree "$CHECKOUT" --env-json "$CONTROL_ENV" --variants-frozen "$FREEZE"
python3 "$F/run_fresh.py" --split dev --out "$OUT_VARIANT" --work "$WORK" --reuse-work --source-tree "$CHECKOUT" --env-json "$VARIANT_ENV" --variants-frozen "$FREEZE"
# Only after all variants/code/config/decoder/checker freeze:
python3 "$F/check_delivery.py" "$OUT_VARIANT" --variants-frozen "$FREEZE" > "$REPORT"
```

Holdout remains sealed until the complete freeze and execution plan; use a separately prepared holdout work root and the same sequential setup/reference/variant pattern. Do not aggregate FRESH17 as L0. Receipt presence is procedural acknowledgment, not cryptographic access control or proof of model-asset versions. No source/gold content is sent through observer configuration.

## Revision hashes (AST-only validation)

- `run_fresh.py`: `4da27c9b2e8b372b7d082489e305445b27d74aea7f5d9ea4797966722b572ecb`
- `check_delivery.py`: `fd255081a1609c03aaa4f7dc4ddb70742d0b2ec1bedb55dfc2447c77da2da2da`

Both parsed successfully with `ast.parse`; modules were not imported. These are new infrastructure revision hashes, not replacements for frozen question/oracle hashes. Update the separately owned freeze receipt before any future evaluation.

**Open review item:** whole-root snapshot hashing binds settings bytes, but explicit semantic settings-language validation still requires the authoritative settings path/schema from the lead. No settings implementation was opened under the instruction to read only protocol/runner code. Do not treat this as a fully cleared run gate until that check is added. Linux/Unix `fcntl` is required. Russian/English report grouping uses the protocol's frozen `search_question` presence rule, not question text heuristics.

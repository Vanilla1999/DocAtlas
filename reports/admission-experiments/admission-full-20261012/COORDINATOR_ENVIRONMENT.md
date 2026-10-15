# Read-only environment and existing CI

- Checked branch/HEAD: fix/main-flow-compact-evidence / 4849b8f796d9e3e25e2c49e58562ec6859978411; clean.
- Product diff against d8af387: four review documents only, 356 added lines. No product change.
- Frozen corpus/questions hashes match EVIDENCE_MANIFEST.json (sha256sum).
- CPU i9-12900K, 24 logical CPUs. RAM 62 GiB total, ~30 GiB available at inspection. Disk ~27 GiB available.
- GPU: NVIDIA GeForce RTX 5070 Ti; 16303 MiB total, 14773 MiB free; driver 595.84. This does not prove framework/CUDA compatibility.
- Model cache directory names found: EmbeddedLLM/bge-reranker-v2-m3-onnx-o3-cpu, cointegrated/rubert-tiny2, MPNet multilingual and unrelated speech models. Presence of a cache directory does not prove complete weights or execution permission. None executed.
- PR #214 OPEN, base eval/main-flow-extra40-20261012, remote head matches local.
- Existing current-head CI run 38232527945 succeeded, exact head above. Saved artifact downloaded to current-head-ci/ without rerunning CI.
- Workflow main-flow-context-review.yml has only pull_request trigger, no workflow_dispatch. It installs dev dependencies, runs listed pytest targets, 40 direct questions and 24 lookup calls. Its existing green status is not an A/B experiment or model generation proof.
- Before any future invocation, listed pytest targets must be classified by actual execution boundary to obey user prohibition on unit tests. No new CI invocation performed.
- All hardware/CI inspection commands were read-only except saving downloaded historical artifacts. No product imports, model calls, weight downloads, installations or secret reads.
- HOST_PROMPT_RU.txt is coordinator's frozen prospective generation prompt; no generation executed. A harness must supply original question and public packet only, never oracle/private trace.
- Existing language-agent-fp32.yml is not an authorized shortcut: it installs a separate CPU model environment and explicitly runs pre-evaluation unit.xml targets (lines 35–47). Several other research/pilot workflows also include unit suites. Do not invoke them unchanged under this user's prohibition. No GPU CI runner established; inspected workflows use ubuntu-latest.
- The apparent cached EmbeddedLLM/bge-reranker-v2-m3-onnx-o3-cpu directory contains only refs/main (40 bytes) in inspected depth; it is not evidence of available ONNX weights. Do not claim a ready local reranker from the directory name.

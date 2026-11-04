# Local generative evidence selection — experiment from main

Base: `439815771b96edc77a12f42f90f1fecb35f5e5d7` (main, PR #229).
Not based on #230/#231; no guarded-cover lexical veto or 3,000-token page cap.
Default is unchanged: this feature is OFF unless a trusted host opts in.

## Research basis and what this implementation does NOT reproduce

- **RECOMP**, ICLR 2024: learning extractive/abstractive context compressors for downstream tasks. We adopt the separation of evidence compression from answer generation and measure the downstream cost. We do not use their trained weights or claim their reported compression ratio. https://proceedings.iclr.cc/paper_files/paper/2024/hash/bda88ed2892f5e61c9a9bf215c566913-Abstract-Conference.html
- **FILCO**, Learning to Filter Context for Retrieval-Augmented Generation: learned context filtering instead of lexical relevance as a sufficiency proxy. Here a generative model selects original section IDs; no training or faithful reproduction of their learned filtering method is claimed. https://arxiv.org/abs/2311.08377
- **Sufficient Context: A New Lens on Retrieval Augmented Generation Systems**, ICLR 2025: distinguish relevance, sufficient context and the generator's ability to use it. Our second arm audits all question requirements against the FULL admitted pool, including omitted sources. It is a fallible model judgment, not a certificate. https://proceedings.iclr.cc/paper_files/paper/2025/hash/33dffa2e3d2ab74a783d1a8c292f66d9-Abstract-Conference.html
- **Self-RAG** uses trained retrieval/reflection tokens. A second prompted call in this PR is not that trained algorithm. https://arxiv.org/abs/2310.11511

The papers justify testable design choices, not an advance guarantee that this
particular small model, quantization or prompt will work on DocAtlas.

## Replacement boundary

The source-native retrieval/admission path stays intact. At the section selection
boundary, successful `DOCATLAS_LLM_EVIDENCE=select` replaces MiniLM/fixed-five
selection, not applies a second lexical veto. `select-audit` adds a full-pool
critique and corrected selection. The same local model is used in a separate
call; this is not an independently trained judge.

There is no word list, lexical overlap threshold, fixed section count or target
of filling a token budget. Whole acquired owner sections remain original and
source-bound. Structural grouping, schema validation and security checks are
not semantic completeness judgments. No new source reads, broader scopes or
external document search occur. A relevant fact missing upstream cannot be
recovered by this prototype. Sources are data, not tool-execution instructions.

An error, unknown/insufficient judgment, invalid reference or oversized output
falls back to main. No model verdict grants answer/edit authority or proves
corpus absence. Partial selections preserve documented parts but do not certify
that the model correctly identified every missing requirement. The existing
main 12,000-token complete-machine-packet ceiling remains a safety boundary;
it is NOT 3,000 tokens or a semantic target. Model input overflow is explicit,
never silently truncated. Full-context audit overhead is measured, not hidden.

## Local models and deployment

Two official Qwen GGUF candidates are pinned in `eval/llm_evidence/models.json`:
Qwen3-1.7B Q8_0 and Qwen3-4B Q4_K_M. These are generative models, unlike the
existing MiniLM cross-encoder. Different sizes and quantizations are a practical
candidate comparison, not a controlled size-only ablation. They are not claimed
to be the newest or the best models. Official cards:
https://huggingface.co/Qwen/Qwen3-1.7B-GGUF
https://huggingface.co/Qwen/Qwen3-4B-GGUF

CPU llama.cpp is pinned by commit. Weights are downloaded and SHA-256-verified
only during explicit setup, never during product requests. Host configuration
requires an explicit numeric-loopback endpoint and model alias. No paid API,
proxy, automatic remote fallback or source-controlled endpoint is allowed.
Non-thinking mode, seed 17 and temperature zero are frozen before inference.

```bash
export DOCATLAS_LLM_EVIDENCE=select-audit
export DOCATLAS_LLM_EVIDENCE_URL=http://127.0.0.1:8099
export DOCATLAS_LLM_EVIDENCE_MODEL=docatlas-local
# Provision the existing MiniLM too to preserve normal main fallback.
export DOCATLAS_MINILM_MODEL_DIR=/absolute/path/to/verified-minilm
```

`DOCATLAS_LLM_EVIDENCE_TRACE=1` emits optional receipts on stderr, not MCP
stdout. Complete prompt/source capture is opt-in and should only be used in a
trusted diagnostic environment. The trace does not decide selection.

## Frozen experiment

Ten authored questions / eight fictional documents / 21 documented requirements.
The suite includes cross-file conditions, English/Russian questions, versions,
partial/unknown requests, alternative sufficient witnesses and hostile text in
an imported incident note. It is a same-author exploratory pilot, NOT an
independent or blind acceptance benchmark. Gold is frozen before model calls
and not fed to the selector; prompts/gold must not be retuned to this result.
Original V40 files and dependencies remain untouched.

Five public installed-MCP arms: uncompressed admitted pool, provisioned main,
fixed-five rollback, local-LLM selection, and selection plus full-pool audit.
Actual source text/path/line/scope and SQLite state are checked independently.
An unavailable local endpoint is exercised via public MCP and must preserve
main's original selected sources. No retrieval/selection/storage/model mocks.

Each model additionally generates real final answers for the PREDECLARED subset
L10-03, L10-04 and L10-07 in all four non-pool arms. This limits CPU experiment
cost while testing multilingual, multi-document and unknown cases. All answers,
prompts and actual usage are retained. Source coverage is machine-scored;
generated answers and unknowns are NOT automatically accepted by the same model.
Their content needs a separately disclosed review. No autonomous OpenCode/GPT
agent dialogue is run in this pilot; installed stdio is not a real-client smoke.

Token accounting separates complete MCP text (o200k) from actual Qwen prompt and
completion tokens. Selection, audit and answer tokens are all recorded, including
failed generations with known usage. Missing usage is unknown, not zero. Episode
cost comparisons apply ONLY to the common answer subset; aggregate selector-only
and answer-subset totals must not be mistaken for complete 10-question dialogues.
MiniLM has no generated tokens; its CPU latency remains part of the tool time.
No claim of GPT billed savings is made.

CI success means that measurement and integrity checks completed. Individual
coverage errors, false sufficient judgments, model failures and increased cost
remain explicit in the scorecard. Neither mode is automatically promoted to
default; the result can legitimately be negative. The workflow splits 10 cases
into two disjoint shards for each of two models, with no duplicate scenarios.

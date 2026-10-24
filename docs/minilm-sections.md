# Opt-in MiniLM sections (selection v1, wire v2)

This feature is **off by default**. It is experimental; it does not implement
semantic abstention and does not authorize edits. An unanswerable question may
still return real but irrelevant source text.

## Enable on the MCP host

Dependencies are supplied by the existing `fastembed` runtime stack
(`onnxruntime`, `tokenizers`, NumPy); no PyTorch or transformers extra is needed.
Provision the pinned model explicitly, before starting an offline server:

```sh
python -m docmancer.docs.application.section_model /absolute/private/minilm-model
export DOCATLAS_MINILM_MODEL_DIR=/absolute/private/minilm-model
export DOCATLAS_CONTEXT_COMPRESSION=minilm-sections-v1
doc-atlas mcp docs-serve
```

These are host settings, never model/tool-call arguments. Unset
`DOCATLAS_CONTEXT_COMPRESSION` (or use `off`) for the existing response unchanged.
No model is downloaded, no remote API is used, and no model is loaded merely
because a document or query asks for this mode.

Model: `cross-encoder/ms-marco-MiniLM-L6-v2`, revision
`233902d25c440f23af6f7d6e94d2946bac0bee0a`, Apache-2.0. Runtime verifies exact
SHA-256 and size of tokenizer and ONNX bytes. Weights are not shipped in the
repository, wheel, or CI evidence. No remote model code is executed.

## Selection boundary

The source-native public projector performs its normal source checks first.
The selector groups all **already acquired** windows sharing the source section
label, canonical source identity, snapshot/catalog, project/module scope,
version and authority. Overlapping or contiguous checked intervals are joined
only for scoring; gaps are not filled. It does not assert that the whole
original document section was acquired.

All groups participate. MiniLM scores each question/section pair, dividing only
the model input into non-overlapping slices of at most 512 tokens. The section
score is the maximum slice score. The five highest scoring groups are retained
with all their original rows, in native order. There are no keyword bonuses,
neighbor additions, semantic thresholds or old first-fit truncation.

The English checkpoint has not been certified for other languages. Questions
over 128 model tokens fail explicitly rather than being truncated. MaxP/top-5
is a fixed ranking policy, not a proof of sufficiency or a set optimum.

## Explicit compact wire format

With the host mode enabled, `get_docs_context` now uses an adaptive encoder:
it considers `context_format=docatlas.sections.v2` with path-only and
section/identity grouping, and the legacy `docatlas.sections.v1` packet. It
emits the cheapest complete packet, so clients must accept **both versions**.
The cost is the final packet's fixed-point `estimated_tokens` (the maximum of
actual tokenizer tokens and UTF-8 bytes/4, rounded up); ties prefer fewer UTF-8
bytes, then v2. Thus its estimated wire cost cannot exceed encoding the same
payload as v1. V2 is not guaranteed to be smaller, nor always emitted.
No evidence is removed to obtain this saving. The host setting
remains `minilm-sections-v1`: the selection algorithm has not changed. There is
no per-client wire-version negotiation or additional opt-in argument. Existing
clients that assumed v1 or a flat `sources` array must use the decoder below
(or implement v2) before consuming these responses. Disabling the host mode
still restores the unencoded response.

`source_defaults` holds fields identical across all selected rows. V2 chooses
between grouping rows by exact `path_or_url` and the legacy grouping by path,
section, project identity, scope, version and authority. Path-only grouping can
save repeated paths but repeat section metadata, so it is not always cheaper.
Each
`source_groups` entry has `common` and `fragments`, whose `fields` hold the
remaining fields and whose `index` preserves original source order. This is
lossless factoring, not source merging or another selection pass. Differing
sections, scopes, versions and authorities remain explicit where needed.
Every source field, exact snippet (including headings), evidence ID, URI,
fingerprint/hash and line/character span is preserved. No heading heuristics
remove evidence. There is no second full copy sent in structuredContent.

V2 includes `context_meaning="Retrieved evidence only; not completeness or edit authority."`
Top-level non-default decisions remain explicit. `envelope_defaults`, when
present, is a nonnegative integer bitmap with these fixed zero-based positions:

| Bit | Field | Restored value |
| --- | --- | --- |
| 0 | `answer_supported` | `false` |
| 1 | `answer_available` | `false` |
| 2 | `edit_ready` | `false` |
| 3 | `requires_confirmation` | `false` |
| 4 | `hard_stop` | `false` |
| 5 | `covered_query_ids` | `[]` |
| 6 | `missing_query_ids` | `[]` |
| 7 | `missing_facets` | `[]` |
| 8 | `read_next` | `[]` |
| 9 | `missing` | `[]` |
| 10 | `warnings` | `[]` |

A set bit means the original envelope contained exactly that typed default;
the field is omitted on the wire and restored on decoding. An unset bit does
not create an absent field. Missing bitmap means zero. Non-default values
(including nonempty arrays and true flags) are never omitted. Unknown bits,
boolean/noninteger masks and overlapping explicit/default fields are rejected.
These omissions never mean answer support, completeness or edit permission.

```python
from docmancer.docs.application.section_compression import expand_sections
legacy_shape = expand_sections(received_payload)
```

The decoder accepts both v1 and v2 and passes unencoded packets through as
copies. It restores all selected source rows and original envelope values,
removing format-only fields. Python callers can still explicitly encode v1
using `encode_sections(payload, context_format=LEGACY_FORMAT)`; the MCP tool
does not expose that encoder option; the default encoder may also emit v1 when
it is cheaper. Repository host sessions and source-read
controllers use the decoder before consuming source rows; transport extraction
retains the wire packet so channel comparisons and wire budgets remain exact.
`estimated_tokens` in the compact packet is the maximum of actual o200k_base
tokens and UTF-8 bytes/4; `source_estimated_tokens` retains the original legacy
estimate for decoding. The entire compact JSON is checked against 12,000.
Oversized sets fail as `section_compression_output_limit`; examples are never
silently dropped to fit. This is not the host model's complete prompt budget.

`source_uri` keeps its existing meaning: a bounded source **continuation** cursor.
It is not a new whole-document lookup or an edit capability. Existing server
expiry, snapshot and access checks still apply when a resource is read.

Packets without source rows and v2 confirmation/hard-stop/delivery-denied
packets retain their existing shape, including operational reasons and denials.
Missing/corrupt assets, input overflow, and resource exhaustion
are explicit operational errors, not semantic empty answers or full-pool fallback.

## Resources and diagnostics

One cached CPU session, batch size one, two intra-op threads. Scoring is
serialized across requests to avoid multiple simultaneous model working sets.
No pool or question is cached globally. Provisioned bytes are pinned in memory
until process restart (or an explicitly different model directory).

Input guards: 4,096 rows, two million snippet characters, 8,192 forward passes,
60 seconds of scoring. These are error ceilings, not evidence truncation.
For a hard memory ceiling run the host in a container with
`--memory=1000000000 --memory-swap=1000000000`; deployment limits are required
for a hard process guarantee. CI measures the installed process, not weight size.

`observe_section_compression()` provides optional host-only per-call receipts.
Diagnostics do not change model inputs or selection; nothing is printed on MCP
stdout. Debug receipt counts are not a claim of answer correctness.

## Acceptance

`.github/workflows/minilm-sections.yml` installs a wheel, provisions assets
before execution, then runs the integration suite in a CPU-only network-disabled
container with a 1 GB hard limit. It exercises real SQLite and public stdio MCP,
all frozen V40 queries, preservation of complete acquired sections and exact
source rows, actual serialized cost, unchanged state, resource reads, changed
sources, long-query errors and missing-assets errors. Gold is evaluated only
after responses have been delivered.

The V40 is a known regression set, not an independent generalization test.
Strict-empty negatives are reported separately and remain outside this feature.
A successful workflow is not blanket acceptance of the pre-existing main CI.

Research basis: MaxP (Dai & Callan, SIGIR 2019,
https://arxiv.org/abs/1905.09217), adapted to existing source sections and MiniLM.
This is not a reproduction of that paper's BERT training or overlapping slicing.

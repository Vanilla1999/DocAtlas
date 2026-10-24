# Opt-in MiniLM sections: v1 wire by default

This feature is OFF by default. It selects acquired source sections, not answers,
semantic refusals or edit permissions. An unanswerable question can still return
real but irrelevant source text. The answering agent is separate from MiniLM.

## Enable on the MCP host

Dependencies come from the existing fastembed stack (ONNX Runtime, tokenizers,
NumPy). Provision the exact model before starting an offline server:

```sh
python -m docmancer.docs.application.section_model /absolute/private/minilm-model
export DOCATLAS_MINILM_MODEL_DIR=/absolute/private/minilm-model
export DOCATLAS_CONTEXT_COMPRESSION=minilm-sections-v1
doc-atlas mcp docs-serve
```

These are host settings, never tool arguments or document instructions. Unset
DOCATLAS_CONTEXT_COMPRESSION (or use off) for the ordinary response. Request
handling never downloads weights or calls an external model API.

Model: cross-encoder/ms-marco-MiniLM-L6-v2, revision
233902d25c440f23af6f7d6e94d2946bac0bee0a, Apache-2.0. Runtime verifies SHA-256 and
size of tokenizer and ONNX bytes. Weights are not shipped in the repository,
wheel or CI artifacts. No remote model code is executed.

## Selection boundary and explicit experiments

The source-native projector checks sources first. Legacy grouping requires the
same source section label, canonical identity, snapshot/catalog, project/module
scope, version and authority. Overlapping/contiguous acquired spans are joined
only for scoring; gaps are never filled. This is not a claim that the whole
original document section was acquired.

All groups are scored. Inputs are non-overlapping slices of at most 512 model
tokens; MaxP takes the maximum score. Default selection keeps five groups and
all their original rows in native order. No keyword bonuses, topic dictionaries,
relevance threshold, oracle-driven rescue or first-fit truncation is used.

Explicit host-only experiment settings:

- DOCATLAS_SECTION_TOP_K=1|2|3|5, default 5. A size policy, not a sufficiency test.
- DOCATLAS_SECTION_UNITS=legacy|markdown-owner-v1, default legacy. Structural
  mode attaches parsed bodyless heading ancestors to already-acquired substantive
  descendants within the same source identity. Orphan headings remain independent;
  short rules, examples and exceptions are not discarded by length. Shared
  ancestors are emitted once by evidence ID. No unacquired span is inserted.

Smaller outputs are not automatically better. The independent V40 policy study
reports coverage failures separately from operational success. See
[scope ledger](context-audit-completion.md). Defaults do not change as a result
of a diagnostic run.

The English checkpoint is not certified for other languages. A full host-provided
search_question translation reaches the scorer; original question is retained.
Inputs above 128 model tokens fail explicitly, never silently truncate. The
500-character search_question schema bound is a different limit, not a promise
of 128 tokens. Put project paths/task instructions in their separate arguments.

## Wire compatibility

The default wire remains docatlas.sections.v1. To explicitly permit adaptive v2:

```sh
export DOCATLAS_SECTION_WIRE_FORMAT=adaptive-v2
```

A compatible host then accepts both v1 and docatlas.sections.v2. The encoder
compares v1 and v2 path/section factoring and chooses the cheapest whole packet.
Its cost is max(o200k_base tokens, ceil(UTF-8 bytes/4)); ties prefer fewer bytes,
then v2. The selection policy is unchanged. Unknown settings fail explicitly.
There is no automatic per-client negotiation, so do not opt old clients into v2.
Python callers may request a specific policy with encode_sections(...,
context_format=LEGACY_FORMAT or FORMAT). FORMAT means adaptive, not forced v2.

Both encodings retain every source field and exact snippet, including headings,
IDs, URIs, hashes and spans. source_defaults contains identical common fields;
source_groups has common fields plus indexed fragment fields restoring native
order. Factoring is not source merging. Differing scopes/versions/authorities
remain explicit. There is no second full copy in structuredContent.

V2 context_meaning is 'Retrieved evidence only; not completeness or edit authority.'
Its optional envelope_defaults bitmap restores PRESENT, exactly typed default
values at fixed positions: 0 answer_supported=false; 1 answer_available=false;
2 edit_ready=false; 3 requires_confirmation=false; 4 hard_stop=false;
5 covered_query_ids=[]; 6 missing_query_ids=[]; 7 missing_facets=[];
8 read_next=[]; 9 missing=[]; 10 warnings=[]. Unset bits never invent fields.
Non-default values are explicit. Unknown bits, bool/noninteger masks and
explicit/default overlaps are rejected. Omitted flags never grant permission.

```python
from docmancer.docs.application.section_compression import expand_sections
original_selected_payload = expand_sections(received_payload)
```

The decoder accepts both wire versions and copies unencoded packets unchanged.
It restores exact selected rows/envelope values, removes format-only fields and
restores the original estimate from source_estimated_tokens. The entire encoded
packet has a 12,000-cost ceiling. Oversize selection fails explicitly; examples
are not silently dropped. This is not the whole host-model prompt budget.

source_uri remains an issued bounded continuation, not a new whole-document
read or edit capability. Expiry, access and snapshot checks still apply on read.
Operational denials, confirmation and errors are not turned into semantic absence.
Missing/corrupt assets and resource overflow never fall back to an unbounded pool.

## Optional model view and managed client

DOCATLAS_MCP_MODEL_VIEW=1 is a separate, OFF-by-default compatible-host setting.
It puts readable exact sources and short refs in model text and the complete
packet in private _meta. The host must retain _meta but exclude it from the LLM
prompt. Raw transport size is not reduced. See [model view](model-context-delivery.md)
and [managed session](model-context-session.md). The managed client also handles
ordinary packets and supplies a deduplicated model evidence block. Server code
cannot remove replay performed by an unrelated external client.

Normal whole-section selection has separate candidate/selected/omitted counts;
it is not itself delivery truncation. Upstream real truncation stays explicit.
Completeness remains unassessed and answer/edit authority remains false.

## Resource and audit limits

One cached CPU session, batch one, two intra-op threads; scoring is serialized.
No global question/pool cache. Assets stay pinned until restart or an explicitly
different directory. Guards: 4,096 rows, two million snippet characters, 8,192
forward passes, 60 scoring seconds. These are error ceilings, not truncation.
A hard deployment cap requires container/process enforcement. CI uses
--memory=1000000000 --memory-swap=1000000000 and disables network during requests.

observe_section_compression() optionally records host-only group scores/ranks,
selected IDs and scoring-text hashes without extra inference or result changes.
No diagnostic text enters MCP stdout or model content. Counts are not answer
accuracy. The exact historical Q02 still requires its original documents/request.

Installed stdio integration uses real SQLite, exact source rows, immutable V40
questions/gold, delivered-byte costing, resource reads and revocation checks.
V40 is known regression data, not an unseen holdout. Strict-empty negatives and
strong-agent final-answer accuracy remain separate, unvalidated claims. A green
focused workflow does not imply that broader repository CI is green.

Research basis: MaxP (Dai & Callan, SIGIR 2019), adapted to acquired sections and
MiniLM, not a reproduction of the authors' BERT training or overlapping slicing:
https://arxiv.org/abs/1905.09217

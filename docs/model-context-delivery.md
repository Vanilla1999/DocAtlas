# Model context delivery (compatible-host opt-in)

This fixes the order of language preflight and false truncation signals, and
separates the text a model needs from the machine evidence packet. It does not
change MiniLM, top-5 selection, source admission or semantic refusal.

## Host configuration

Continue enabling the existing pinned MiniLM mode normally. In addition, only
for a host verified to keep MCP result `_meta` OUT of its model transcript:

```sh
export DOCATLAS_MCP_MODEL_VIEW=1
doc-atlas mcp docs-serve
```

Default is off. No fourth MCP tool or model-controlled parameter is added.
Mode 1 emits compact JSON `docatlas.model-context.v1` in text, no duplicate
structuredContent. Each source retains exact text, source order, path, heading,
lines, scope and version. Scope/version/authority common to all rows is stated
once. Long hashes, IDs and continuation URLs remain in `_meta["docatlas/source-packet"]`
inside the exact original packet. There is no summary or source deletion.
This saves MODEL INPUT, not transport/storage bytes. A generic client that forwards
_meta to the model saves nothing and must not enable this mode. A client that
throws _meta away loses the machine audit and must not enable it either.

`extract_tool_payload(reply)` verifies the displayed refs/text against the
private packet and returns that exact packet. `expand_sections` then restores
legacy rows. `resolve_model_reference(view, metadata, ref)` resolves an issued
citation into its original source row. A ref is NOT a new read/edit capability.
Use its original source_uri for an authorized bounded continuation; expiry,
access and changed-source checks remain on the source reader. A self-consistent
packet is not proof of server authenticity or semantic correctness.

Unknown additional top-level decisions are retained. Errors, hard stops,
confirmation and denied-delivery packets retain their existing shape, without
any compact-view reinterpretation. Explicitly true answer/edit certification
is not compacted. Missing scope/unknown languages do not become English.

## Language first, once

When the user enabled documentation-language search and the selected source's
language is not bound to the current snapshot: call compact docs_status FIRST,
then get_docs_context with the original question and full search_question
translation. Otherwise retrieve directly. Put paths and instructions in their
own arguments, not in question. Neither selected sources nor unassessed
coverage is a reason by itself to repeat retrieval. Follow up only for a
concrete missing fact; preserve partial supported answers.

## Status and trace

Whole-section selection preserves an upstream real `truncated` status but no
longer manufactures it for ordinary source selection. A normal complete
selected packet has `status=ok`, `answer_supported=false` and unassessed semantic
coverage. `source_selection` states candidate/selected/omitted row counts for
ADMITTED CANDIDATES, not recall or completeness of the documentation corpus.
Rejected sources, actual budget truncation and operational failures are not
relabelled. Selection of five groups may still include irrelevant text.

`observe_section_compression()` optionally records all scored groups, scores,
positions, selected evidence IDs and hashes of scorer text. It does not log
source bodies, change inputs, adjust thresholds or add inference calls. The
trace remains host-only. It helps locate Q02's loss IF its original source
snapshot and exact request are supplied; that case is not claimed fixed here.

## Verification and remaining work

The integration workflow runs installed wheels, real SQLite, actual stdio and
the unchanged V40 oracle in CPU-only offline containers. Model view checks
are additional transport/answer-input checks, not LLM answer evaluations.
Target: retain 24/24 positives, 8/8 documented partials, all exact selected
rows, and source revocation. Strict-empty negatives remain 0/8.

A real strong-agent A/B must still verify skill loading, language-first order,
question construction, answer quality, replayed history and provider usage.
No Qwen substitution or claim of provider savings. Generic MCP cannot compact
its host's conversation or force a model to obey a skill. Dynamic tool
exposure, history compaction and fewer semantic sections remain separate
host/selection work; no arbitrary score threshold or gold-informed filter is added.

# Reversible host-side packing of selected evidence (opt-in)

The QA/NLI studies in `semantic-preservation-results.md` did not establish useful
semantic sufficiency or lower context costs. This alternative leaves the entire
selection and every original source-text byte alone. It factors only repeated
paths/section labels and the spelling of line-coordinate fields.

## Pipeline and compatibility

Existing native retrieval -> MiniLM/facet selection -> existing v1 MCP reply ->
**optional compatible-host packing** -> answering model.

This is NOT a new retrieval, summarization or semantic completeness decision.
It does not replace the existing public MCP format or automatically change
`ModelContextSession.model_input()`. A host must explicitly opt in and understand
the new `docatlas.packed-model-context.v1` representation. A generic old client
must continue using its existing v1 view; do not append both views to a prompt.

```python
from docmancer.docs.application.model_context_packing import (
    prepare_packed_context, resolve_packed_reference,
)

# reply is the actual response from your existing MCP client.
# Handle errors, denials, preparation and patch-context results normally first.
model_context, private_ledger = prepare_packed_context(reply, policy="adaptive-v1")
# Send only model_context, NOT private_ledger or the original MCP _meta.
# Store model_context and private_ledger together for this response.
original_row = resolve_packed_reference(model_context, private_ledger, full_citation_ref)
```

The full issued citation reference is unchanged. Bare `s1` is not accepted as a
substitute. `restore_packed_result` recovers the exact original machine packet;
this is not permission to read arbitrary paths or bypass the original source
reader's access/snapshot checks.

## Compared policies

- `paths-v1`: factor exact paths into a response-local catalog; preserve section
  labels per row, all text, full refs and order. Represent a present pair of line
  coordinates as `lines=[first,last]`, inclusive.
- `sections-v1`: factor exact path+section pairs, including whether the section
  field was absent. No source rows or text are combined or removed.
- `adaptive-v1`: compare both candidates with the original v1 projection using
  the bundled o200k_base codec, UTF-8 byte count and the existing conservative
  packet budget. Never increase any of these three on the same response; retain
  the original v1 when there is no benefit. This is a representation choice,
  not a learned evidence-quality threshold.

All non-source fields and non-factored source attributes stay unchanged. A
catalog/text/ref/line/authority mismatch, missing private ledger, unsupported
policy or mixed-response ledger is rejected. Metadata is host-owned and remains
private; the original response's binding/authority is neither strengthened nor
replaced by this transformation.

## Acceptance and measurement

`eval/packing_selection_integration.py` reuses the established installed-wheel,
SQLite, CPU MiniLM and public stdio MCP scenario. It compares current fixed-5 and
efficient facets at the SAME code revision over all 84 already-known questions.
The original independent witness oracles are unchanged. Then every packing arm
uses the exact SAME issued response, nonce and private ledger. An independent
visible-field expansion must equal the original v1 view in its entirety.

Host tamper controls mutate actual delivered text, paths, lines, refs, catalog,
authority, format policy and ledger. They do not fabricate retrieval or model
results. No unit test, product scorer mock, source rewrite or gold tuning is
introduced. The existing coverage workflow is reconciled with the current
integrated selectors: immutable DATA remain frozen, but obsolete implementation
bytes from 95c7bf4 are no longer used as a reason to reject every later revision.
Current controls are run together instead of mixing historical policy labels.

Token savings from packing are exact paired differences for an unchanged
response; random short-reference nonce differences cannot produce a false win.
The selector comparison uses newly executed controls, not previously advertised
numbers. Local host-packing overhead is reported separately from MCP latency.

This verifies source-evidence preservation, not generated-answer accuracy or
complete strong-model dialogue usage. No strong model is invoked by this study;
provider usage remains null. QA/NLI modes stay experimental. No automatic merge,
main/default switch, or claim that corpus absence is solved follows from it.

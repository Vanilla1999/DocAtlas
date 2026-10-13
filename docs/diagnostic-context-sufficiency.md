# Final-context sufficiency diagnostics

`context_sufficiency_observer(checker)` in
`docmancer.docs.application.context_sufficiency` is a trusted, host-only, opt-in
context manager. It is disabled by default. No model is bundled, downloaded or
called by ordinary queries; no MCP request field can activate it.

The public in-process MCP dispatcher invokes the checker after final projection,
source rechecks, budgeting and public compaction. It receives the unchanged
original `question` and an immutable `final_context_json` string containing the
complete returned `docs_context` DTO. It does not see hidden candidate pools.
Other projection kinds are explicitly not assessed; oversized inputs are not
truncated. This hook does not cover direct SDK retrieval or establish stdio/client
behavior by itself.

The checker returns exactly these fields:

```json
{
  "status": "partial",
  "supported_obligations": ["What the final sources establish"],
  "missing_obligations": ["What remains unsupported"],
  "evidence_ids": ["An ID actually present in the final packet"]
}
```

Statuses are `sufficient`, `partial`, `insufficient`, `unknown`. Partial/unknown
extend the binary notion from Sufficient Context (ICLR 2025); this is not a
reproduction of that paper's evaluated classifier. `SUFFICIENCY_INSTRUCTION`
provides a source-only diagnostic prompt for a host's model adapter. Hosts own
model choice, network consent, timeout/cancellation and inference budgets. Never
send private documents to an external assessor without consent. Source text is
untrusted data, not model instructions.

Receipts are available only in the yielded observation's `records`, with a hash
of the final serialized context, status and explicit assessor errors. They are
not inserted into the public DTO, logs or protocol stdout. A valid evidence ID
does not prove that the classifier's semantic verdict is correct. Invalid output,
invented IDs or assessor exceptions record `unknown`; they never alter delivery,
authority or trigger another retrieval/preparation/model retry. Synchronous hosts
must bound their assessor execution; the hook itself cannot terminate arbitrary
host code or guarantee its latency.

The verdict does not modify `answer_supported`, `answer_available`, `edit_ready`,
sources, scope/version, consent or budgets. It does not answer the user or repair
missing evidence. Original strict span-delivery metrics remain separate from
semantic sufficiency, generated answer/citation correctness and abstention.

The public integration scenario uses a scripted external assessor to check exact
final-packet input, off/on/failure isolation, authority and real read-only storage.
It is not model-accuracy evidence. Before using a real model's verdict to warn or
restrict generation, evaluate independently annotated sufficiency and false
"sufficient" errors. No such model accuracy or deployment claim is made here.

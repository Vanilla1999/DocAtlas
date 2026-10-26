# Managed MCP context session: opt-in host integration

This follow-up to PR #221 addresses the remaining client-boundary items in the
owner's token audit. It is not an autonomous agent or a provider API. Integrating
this class into a real client is an explicit host change, not a server default.

## One question, one bound session

`docmancer.docs.interfaces.model_context_session.ModelContextSession` accepts an
actual MCP ClientSession, the user's concrete original question and immutable
project/library/version/module/scope bindings. It never extracts scope from prose
or rewrites the question. Translation is supplied by the strong answering model.

```python
from docmancer.docs.interfaces.model_context_session import ModelContextSession

turn = ModelContextSession(
    mcp_client,
    question=user_question,
    bindings={"project_path": known_project, "scope": "project"},
    language_mode=True,
)
profile = await turn.language()  # real docs_status(include_language=True)
# The strong model uses this declared profile to provide a full translation.
# Unknown/mixed/partial declarations must not be guessed as English.
model_context = await turn.retrieve(search_question=translated_question)
# Send ONLY model_context (or later turn.model_input()) as the evidence block.
# Never append turn.audit or MCP _meta to the LLM prompt.
```

Without language mode, retrieve directly. Library mode requires a previously
known canonical_id. Module mode uses its exact path. Language preflight with
scope=all fails explicitly: a project-only language profile must not be reused
for sibling modules. It also rejects simultaneous project_path and library
bindings: one library-language profile cannot describe an independently
declared project-language lane. The server still supports mixed project/library
and all-scope retrieval with language_mode=False; use separate exactly bound
source turns if language-specific translation is required for each lane. These
host restrictions never change the server's normal mixed or all-scope reads.

`tools()` returns the genuine advertised definitions for the current phase:
only docs_status before required preflight, get_docs_context afterwards, and
prepare_docs only after a returned typed recovery or explicit host lifecycle
request. It does not execute lifecycle actions or manufacture confirmations.
The server still has exactly three public tools; their validation is unchanged.

## Bounded history, private provenance

A cached language call makes no extra product request. A repeated identical
retrieval fails before dispatch. A different follow-up requires a concrete
caller-assessed missing_fact. These are host workflow guards, not a semantic
judge or a claim that a single result is sufficient. Maxima default to three
searches and twelve recorded MCP calls; invalidation cannot reset the ceilings.

Every transport result stays in the private audit. The model projection retains
one copy of each exact source record in the same verified source snapshot,
including all original provenance and issued continuation identity in the
private key. Different versions, scopes or snapshots are never merged merely
because the text matches. Without a verified snapshot/issued handle, results
remain response-local. Repeated result events refer to the retained text; the
model never receives only 'unchanged' after the text has been removed.

Use a fresh `model_input()` evidence block instead of replaying older blocks.
Keep the user's question, host system instructions and ordinary conversation
outside this block as appropriate for the target provider. The adapter cannot
remove history that a separate client still forwards. No provider-cache or
billable-token claim is made by measuring this block alone.

`resolve(ref)` returns an exact retained source row. It does not read a path,
verify semantic support or grant access. Use the existing validated source-read
gateway for its original source_uri. Host changes to project/catalog/version or
access must call `invalidate()` or create a new turn. An explicit
`language(refresh=True)` invalidates active refs on snapshot change. No cache
crosses independent conversations. Source URI expiration is still enforced by
the server reader; the host never refreshes it by inventing a new URI.

## Explicit budgets and compatibility

The projection has a 12,000-token default ceiling, measured with the bundled
projection tokenizer. Over-budget input fails without silently dropping sources.
This is a data-block ceiling, not the entire provider request or invoice.
GroundedMCPSession now defaults to the same 12,000-token packet ceiling;
`evidence_budget=800` retains a host's historical stricter choice. Recovery has
its own explicit `recovery_budget` (default600). Query limits are unchanged:
MiniLM still refuses over128 model tokens, and search_question remains <=500
characters. The managed host rejects a blank/overlong translation, invalid
lookup list or a sixth distinct translation lookup BEFORE making an MCP call.
It does not over-reject a translation identical to the original question or
already included in the lookups. The 128-model-token limit still belongs to
the server's real scorer; the host does not guess it or silently shorten input.
Paths and task instructions belong in separate arguments, not in question.
No semantic truncation is introduced to make long questions pass.

For compatibility, section wire now defaults to v1. Explicit host setting
`DOCATLAS_SECTION_WIRE_FORMAT=adaptive-v2` enables the existing adaptive v1/v2
encoder. Clients enabling it must accept both. This supersedes the prior
adaptive-by-default description in minilm-sections.md. Model view itself remains
OFF unless `DOCATLAS_MCP_MODEL_VIEW=1` is configured for a compatible host. The
managed adapter also creates a verified model projection from normal packets;
it does not require trusting a generic client's handling of _meta.

## Selection experiments, not semantic fixes

Default selection remains five legacy groups. Host-only settings allow a
predeclared diagnostic comparison: `DOCATLAS_SECTION_TOP_K=1|2|3|5` and
`DOCATLAS_SECTION_UNITS=legacy|markdown-owner-v1`. Neither is an LLM tool argument.
Invalid configuration fails explicitly. No relevance threshold, question-specific
rule, training or oracle-assisted production decision is introduced.

markdown-owner-v1 attaches a parsed heading with no body to already-acquired
substantive descendants in its exact source namespace. It no longer occupies an
independent selection slot. Orphan headings stay independent; short rules,
examples, exceptions and unacquired gaps are not deleted or inferred. Selected
original source rows retain exact bytes and order. A shared ancestor is delivered
once by evidence ID. This is not a guarantee of minimal sufficient evidence.

The workflow records real installed-MCP V40 outcomes for k1/k2/k3 and structural
k5 separately. A diagnostic run finishing is NOT quality acceptance: consult
`quality_gate_passed`, coverage and failed IDs. Defaultk5 retains its original
strict positive/partial gate. The original questions/gold are unchanged.

## Remaining evidence limits

The owner's exact Q02 source fixture and request traces were not supplied.
The independent session-lease control is not that Q02 and must not be reported
as its repair. Existing candidate-admission observer and all-section rank
receipts permit diagnosis once those exact inputs are available.

No strong-model cold-agent A/B, final-answer correctness, provider history replay
or cached-input billing is certified by this SDK integration. The full workflow
must use the same real strong model and deployed client; no small-model substitute.
Semantic refusal remains separate and unvalidated. Main is not changed by this PR.


## Selection and packing defaults (2026-10-26)

When an already provisioned trusted `DOCATLAS_MINILM_MODEL_DIR` exists, new
retrieval uses the `facet-guarded-v1` selector with `markdown-owner-v1`
grouping unless a host explicitly requests `fixed`. If the model directory
is absent and compression is not explicitly requested, selection stays
uncompressed; nothing is downloaded during a request.

Managed `ModelContextSession.model_input()` defaults to
`context_packing="adaptive-v1"`. Repeated source paths or path/section fields
are cataloged only if the full model input becomes smaller by the tokenizer
and does not grow in bytes or conservative budget. Text, full refs, source
ordering and private provenance stay unchanged. The returned input may use
`docatlas.packed-managed-context.v1`. A compatible managed client can call
`unpack_managed_model_input(view)` to recover the plain visible fields.
To force the exact older managed input layout, pass `context_packing="off"`
to the session constructor.

For raw MCP callers, the server's old `docatlas.model-context.v1` wire is
unchanged; `prepare_packed_context(reply, policy="adaptive-v1")` remains an
explicit opt-in helper. No generic client's wire format is silently switched.
Neither packing nor local QA/NLI makes unsupported content answerable.

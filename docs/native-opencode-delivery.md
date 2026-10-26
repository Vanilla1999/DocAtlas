# Native OpenCode delivery: bounded, source-preserving evidence

## Defect and why a default selector alone did not fix it

The 2026-10-26 report against `43981577` counted 256 returned fragments for every
question in one project containing fifteen documents from five products. The
constant comes from `retrieval/experimental_acquisition.py`: it is a work ceiling
for finding candidates, **not** a model-input budget or relevance guarantee.

`select_experimental_candidates()` retains every source-checked admitted row.
If the host has not provisioned MiniLM, `section_compression.enabled()` is false.
The terminal budget enforcement in the docs handler is disabled, and
`compact_mcp_payload()` exempts `docs_context` before its byte check. Standard
OpenCode registration previously only enabled the full JSON text fallback.
The managed Python SDK's compact representation does not modify a native
OpenCode client.

OpenCode 2.1.2 is pinned to `a517687fde98a7329ada3ae644a01a9fc6c4e99e`.
Its ToolOutput default is 50 KiB / 2,000 lines. A larger single JSON line leaves
zero complete lines in the preview and is saved to a file. Its MCP client also
**discards result `_meta`**. Therefore simply switching on the old SDK model view
cannot be presented as a verified, source-bound native integration.

## New installation and model-facing path

`doc-atlas install opencode` now registers:

```json
{
  "DOCATLAS_MCP_TEXT_FALLBACK": "1",
  "DOCATLAS_MCP_PRESENTATION": "opencode-v1"
}
```

The CLI facade routes this trusted host setting to a dedicated native server.
The ordinary public handler still validates arguments, authorization, original
source-read receipts, paths, scopes and versions. It returns bounded multiline
original text with response-local references, paths, original line coordinates
and exact source-snippet character offsets. The native server does not require
OpenCode to retain a private model-context ledger. Generic clients and direct
legacy handler consumers remain unchanged.

The complete rendered page, including the real signed continuation, is limited
to 24,000 UTF-8 bytes, 900 lines, and 3,000 `o200k_base` tokens. These are host
budgets, not tool arguments, and can be lowered with `DOCATLAS_NATIVE_MAX_BYTES`,
`DOCATLAS_NATIVE_MAX_LINES`, and `DOCATLAS_NATIVE_MAX_TOKENS`. They are deliberately
below OpenCode's default caps, but clients configured with even smaller limits
must lower the server budgets accordingly.

Large original snippets are split into consecutive exact slices, never
summarized. Source-text bytes are not silently discarded. A page explicitly
states PARTIAL when there is more evidence; otherwise END OF ACQUIRED EVIDENCE
still does **not** certify corpus completeness or support every requested claim.
An indivisible framing/binding that cannot fit results in an explicit error.
Lifecycle/mutation responses are not falsely converted to failure after a
successful side effect.

## Selection and diagnostics

- The installed default preserves the existing acquisition/selected-source order.
  The delivery-only experiment already retained the required source witnesses;
  there is no demonstrated need to add another mandatory ranker.
- Optional `DOCATLAS_NATIVE_SELECTION=lexical-v1` uses ordinary BM25 over the already
  admitted bodies with small heading/path signals. It is a page ordering, not a
  fixed-k, scope selector or semantic sufficiency oracle. There are no product
  names, answer dictionaries or gold-dependent rules in the algorithm.
- If MiniLM actually selected evidence, preserve that set rather than applying a
  second lexical veto. The remaining source text remains available by paging.
- Default `DOCATLAS_NATIVE_SELECTION=preserve` isolates delivery changes without changing
  the acquisition order. It is useful for the delivery-only experimental arm.
- `DOCATLAS_NATIVE_TRACE=1` records acquisition/admission/selection/delivery
  counts and policy to stderr, never protocol stdout. Counts explicitly
  distinguish acquisition occurrences from admitted rows. No trace implies no
  claim that MiniLM ran. The small `_meta` receipt is diagnostic only; it can be
  dropped by OpenCode without breaking evidence delivery or continuation.

## Continuation and source integrity

Repeat the same get_docs_context arguments and add the issued `continuation`.
It is process-local HMAC-authenticated, expires after 600 seconds, and binds the
full arguments (including scope, original question and translation), page,
position, and exact source pool. Every page executes the same authorized public
read again. It does not serve cached original text after permissions, source
bytes or provenance change. No cursor grants another root, broader scope, edit
permission, or filesystem access. Altered, expired or different-process cursors
fail explicitly. Page count is limited to 64. Request continuation only for a
concrete missing fact, not to assert absence by exhausting a candidate list.

There is no new disk cache or temporary JSON-output file in this server path.
Citation references identify the visible source span; they are not source-read
capabilities. Use the normal validated reader for any source URI obtained through
a separate authorized interface.

## Acceptance boundary

`eval/native_opencode_integration.py` installs the actual wheel and configures a
normal project OpenCode registration. All fifteen original V40 documents are in
**one catalog project**. The first ten original questions and committed gold are
unchanged. Legacy JSON, delivery-only, and ranked native output are compared.
It tests public stdio output, full acquired-source pagination, forged cursor,
changed question/scope, and changed-source rejection. Gold is read only after
execution and checks exact source-span coverage, independently of the selector.

`eval/native_opencode_client.ts` is executed inside the pinned upstream checkout.
It invokes OpenCode's real McpClient adapter and actual ToolOutput truncator
against the installed DocAtlas server. It does not substitute a handwritten
truncation check. It does not run the full interactive answering agent, make paid
model calls, measure final answers, or calculate provider usage. Those boundaries
must remain explicit in reported results.

The retained V40 gold groups several facts together and is not the same granularity
as the user's 23 individually graded facts. Source-span coverage cannot be
advertised as a fresh 23/23 final-answer grade. Negative-case absence recognition
also remains a separate full-dialogue evaluation.

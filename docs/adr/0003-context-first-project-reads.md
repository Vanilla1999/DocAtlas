# ADR 0003: Context-first project reads

## Status

Accepted. Updated for the explicit-request/member contract in PR #211.
Earlier automatic aliases, lexical answer certification, implicit discovery,
physical prune promises, and fixed output ceilings are superseded below.

## Decision

Project and module documentation reads return source-attributed `docs_context`.
The server retrieves current, explicitly admitted sources; the host writes the
answer and identifies gaps. Project reads do not return server-certified
`docs_answer`. A compatibility kind or advanced `patch_context` representation
is not proof or mutation permission.

The public MCP surface contains `get_docs_context`, `prepare_docs`, and
`docs_status`. The original question and explicit host lookups are preserved.
The server does not infer translations, questions, expected answers, or source
names. Public lookup credit never transfers to the original question.

## Invariants

- Finite literal catalog membership, scope, current hashes, and source identity govern reads.
- Readiness and `hard_stop=false` are not permission; `hard_stop=true` blocks edits.
- `docs_context` denies answer support, availability, and edit readiness.
- Useful partial evidence remains usable with honest missing information.
- Metadata-only matches cannot qualify visible evidence; final text is rechecked.
- Admitted text, hashes, and coordinates survive delivery together.
- Complete DTO bytes/tokens and MCP tool-catalog bytes are minimized without fixed 800/6144 ceilings.
- Input, bounded source-read/candidate work, lifecycle, and host-session controls remain separate.
- Sync without `mutation` performs no writes. Confirmed upserts bind exact source
  and catalog hashes, a host-selected private store, and the expected generation.
- Deleted, stale, and no-longer-admitted members cannot supply current evidence;
  confirmed sync does not promise physical deletion of unselected stored rows.

## Literal partial body context

Partial context is an additional admission for original project reads through
`get_docs_context`, not whole-question qualification. Canonical source, scope,
version, explicit identity and body-window checks remain mandatory. Missing
hard-exact terms cannot be excused by a low whole-question lexical ratio.

`ordinary_body_clause_context_v1` uses a contiguous span of the unchanged
question with at least two distinct literal words. All words in that span must
appear in order inside one substantive source clause; source insertions are
allowed. It does not delete function words, short words or query modifiers.
`literal_body_block_context_v2` additionally permits a complete technical term
and a separate literal query term in one substantive structural body block.
Parts of one composed identifier cannot count as two independent terms.
Neither witness proves an unmatched modifier or the whole question's relation.

Paragraphs, individual list items, code bodies and individual table data rows
can supply body context. Headings, links, table headers and fence markers cannot
supply these body witnesses. Source bytes and coordinates survive formatting.
Unresolved names must occur in the verified current structural owner's scope,
or the current body when no owner exists. A bare name may match the first
underscore namespace segment for context only; this does not establish exact
symbol identity or a subject relation. Query numbers, including numbers next
to sentence punctuation, must occur in the same witnessing body block.

There is no word dictionary, minimum word length, stemming, synonym expansion,
generated lookup or new provider/dependency. The existing conservative clause
boundary grammar only rejects phrase joins. Stored queries and canonical
hard-exact extraction do not change. Common literal phrases can still be weak
relevance signals; this lane is not semantic answer validation.

Every partial-body witness requires a private receipt from this exact original
query's actual native body discovery. The receipt binds the host-requested
local project identity independently of the candidate, the finite current
catalog member, generation, source/file hashes and complete returned window
span/hash. Fresh source preparation by the owning native context is required;
serialized metadata and lookup-only discovery cannot mint that receipt. The
receipt exists only for the synchronous public handler, including final
projection. Nested calls receive fresh state; normal and exceptional exits
deactivate it, including copied contexts. This process-local ledger guards
normal consumer replay; it is not a capability against arbitrary Python code.

Admission retains the whole acquired source window and its provenance.
Qualification remains false, original-query coverage remains missing, and
answer/edit authority remains false. A question mentioning an unknown ordinary
modifier may still receive partial context when a real literal phrase matches.
Existing explicit-literal and unrelated-empty controls remain required. The
main-flow integration check preserves the ten frozen questions and source
bytes, independently checks required facts and source/hash/span binding, and
keeps public negative reads for a foreign section owner and an absent numeric
condition. This evidence does not establish installed-client or production
behavior.

## Consequences

Independent quality evaluators preserve the original questions and required
facts. They check returned witnesses separately from production coverage claims.
Source fidelity, true MCP delivery, and installed-client behavior require their
own evidence; a small payload or a green planning test does not prove them.

The frozen project-answer v1-v4 evaluators and direct `get_project_context` MCP
surface remain historical. Current checks exercise the advertised public tools.

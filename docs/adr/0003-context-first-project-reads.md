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

## Ordinary partial body context v1

`ordinary_body_clause_context_v1` is a deliberately limited additional context
admission, not whole-question qualification. It applies to ordinary, original
project reads through `get_docs_context`; module/library requests, explicit
literal or technical references, quoted/path syntax, and numeric/operator
syntax continue through their existing lanes. The ordinary fallback declines
unsupported syntax instead of silently deleting it.

A witness is one contiguous raw span of the original question containing at
least two distinct content words. Its content words must appear in order inside
one substantive prose clause of the current source. Source insertions are
allowed; query content words between the endpoints cannot be skipped, and
separate sentences or coordinating clauses cannot be joined. Heading, link,
table/list, code-fence and repeated-label text cannot supply this prose witness.
Whitespace wrapping and inline emphasis preserve raw coordinates.

A documented, general English function-word set covers question words,
auxiliaries, determiners, personal pronouns and basic connectors/prepositions.
It is not a topic dictionary. Temporal, conditional and negative words such as
`before`, `after`, `unless` and `not` remain content words. There is no stemming,
synonym expansion, generated lookup, threshold fitted to a fixture, or new
provider/dependency. Stored queries and canonical hard-exact extraction do not
change.

Every ordinary witness requires a private receipt from this exact original
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
answer/edit authority remains false. The selected lexical span does not prove
every unmatched ordinary modifier or semantic relation in the whole question:
a question mentioning an unknown ordinary modifier may still receive useful
network context when a real network phrase matches. Existing explicit-literal
and unrelated-empty controls remain required. The initial evidence obligation
is native MCP delivery for the unchanged two P14 questions, independent prose
and formatting, and causal source/relevance/replay counterfactuals; it does not
establish V2 or whole-PR acceptance.

## Consequences

Independent quality evaluators preserve the original questions and required
facts. They check returned witnesses separately from production coverage claims.
Source fidelity, true MCP delivery, and installed-client behavior require their
own evidence; a small payload or a green planning test does not prove them.

The frozen project-answer v1-v4 evaluators and direct `get_project_context` MCP
surface remain historical. Current checks exercise the advertised public tools.

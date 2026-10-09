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

## Consequences

Independent quality evaluators preserve the original questions and required
facts. They check returned witnesses separately from production coverage claims.
Source fidelity, true MCP delivery, and installed-client behavior require their
own evidence; a small payload or a green planning test does not prove them.

The frozen project-answer v1-v4 evaluators and direct `get_project_context` MCP
surface remain historical. Current checks exercise the advertised public tools.

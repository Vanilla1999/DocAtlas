# ADR 0002: Retrieve project documentation before certifying an answer

- Status: superseded by ADR 0003
- Date: 2026-08-30

## Context

The public `get_docs_context` path is already bounded. The observed failure is
not that bounded delivery appeared only after legacy compatibility was removed;
the standard public path was bounded before that change as well. What fails is
the interaction between a deliberately strict answer parser, conditional
`docs_context` fallback, and lexical retrieval across Russian questions and
mostly English repository documentation.

A strict parser is appropriate for certifying a complete `docs_answer`, but its
uncertainty must not by itself prevent safe project documentation from reaching
the model. The resolved project identity already supplies the hard corpus
boundary analogous to a Context7 library ID: project path, repository identity,
scope, lifecycle, freshness, and source class remain verified before
projection.

## Decision

Project documentation delivery has two independent stages.

1. **Bounded retrieval** accepts the original natural-language question and may
   add a small number of deterministic, auditable retrieval-only aliases. These
   aliases improve lexical recall across reviewed EN/RU documentation intents.
   They never create proof obligations or authorize an answer or edit.
2. **Answer certification** may upgrade retrieved material to `docs_answer`
   only when the existing strict answer contract is completely parsed and every
   mandatory obligation has a local source witness.

When safe current project documentation is relevant but answer certification is
not available, the result is `docs_context`, not `insufficient_evidence`.
`docs_context` remains bounded, source-attributed, non-complete, and never
edit-authorizing. Explicit mutation requests continue to use strict
`patch_context`.

This decision does not claim a production dense multilingual path. A future
dense qualification change must carry calibrated dispatcher provenance through
fusion and hydration and must be tested through the public projection before it
can qualify `docs_context`.

## Invariants

- Cross-project, stale, historical (unless requested), risky, or unowned sources
  never become visible context.
- Parser uncertainty prevents `docs_answer`, not project-scoped retrieval.
- Retrieval aliases remain tied to the original query plan and are never proof.
- Broad workflow, overview, architecture, installation, testing, storage, or
  troubleshooting requests return `docs_context` when qualified context exists.
- A named policy, rule, contract, or invariant is not collapsed into a nearby
  broad topic merely to obtain a hit.
- `insufficient_evidence` remains the result for operational blocks,
  authoritative conflicts, or no qualified relevant project documentation.
- Only the current `.docatlas` namespace is used. No `.docmancer` discovery,
  migration, or runtime diagnosis is restored.
- No legacy public MCP tools or unbounded payloads are restored.

## Consequences

Weak models receive useful project documentation more often and need fewer
recovery turns. Narrow exact facts retain stronger proof semantics. The system
gains a small retrieval-language adapter, so its intent families and negative
boundaries must be covered by public-path and holdout tests rather than by a
self-host-only parser score.

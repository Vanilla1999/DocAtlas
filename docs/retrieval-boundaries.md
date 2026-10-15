# Retrieval and admission boundaries

## Active-only lexical statistics

The active-generation lexical index isolates FTS/BM25 document-frequency and
corpus-length statistics from inactive and candidate generations. A not-yet-promoted
index must not change the active search ranking merely by existing. Source-policy
checks apply to expanded candidates before text hydration; a second check after
hydration remains defense in depth. Promotion and active-generation tests protect
this boundary.

## Source selection and optional diversity

By default, retrieval preserves the backend/fusion order without a per-source
quota or a second sort by literal question-word counts. Relevant sections from
one document can fill the existing global candidate budget.

An explicitly configured `max_sections_per_source` retains the existing diversity
policy: one additional candidate per source may use unused global capacity when
its indexed parent is already represented. Explicit adjacent/page expansion keeps
its existing behavior. A shared parent establishes structure, not semantic
support; source authority, scope, freshness and final admission still apply.

## Whole-response token budget

The public `estimated_tokens` retains its compatible estimate: the ceiling of
canonical UTF-8 JSON bytes divided by four. Admission of `docs_context` separately
takes the maximum of that estimate and the pinned offline `o200k_base` token count
over the entire canonical JSON, including metadata and optional locators. Fixed
800-token and three-source output ceilings are retired; minimize the measured
payload while retaining useful source text and provenance. Neither estimate
promises the exact count of every client model. Operational read and candidate
work bounds remain separate.
Do not change the public estimate globally to simulate this internal admission
policy. A shorter snippet still must retain a qualified contiguous source span.

## Bounded source analysis

Repository maps and code graphs share one captured set of parsed source facts
within a request. Each independently selects and budgets its results; consumers
cannot mutate the shared capture. A new request captures fresh facts. This is not
a global cache. Path discovery alone does not require a connectivity graph;
explicit call paths and cross-module relationships can still request it. Existing
patch-target recovery keeps its own routing checks.

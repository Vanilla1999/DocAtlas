# Retrieval and admission boundaries

## Active-only lexical statistics

The active-generation lexical index isolates FTS/BM25 document-frequency and
corpus-length statistics from inactive and candidate generations. A not-yet-promoted
index must not change the active search ranking merely by existing. Source-policy
checks apply to expanded candidates before text hydration; a second check after
hydration remains defense in depth. Promotion and active-generation tests protect
this boundary.

## Per-source diversity and structural overflow

The normal per-source quota remains the diversity floor. At most one additional
candidate per source can use otherwise unused global candidate capacity, and only
when its indexed parent is already represented by a preferred chunk from that
source. A shared parent establishes structure, not semantic support. Qualification,
source authority, projection, and final budget checks still apply. Overflow does
not globally remove the source cap or displace preferred candidates.

## Whole-response token budget

The public `estimated_tokens` retains its compatible estimate: the ceiling of
canonical UTF-8 JSON bytes divided by four. Admission of `docs_context` separately
takes the maximum of that estimate and the pinned offline `o200k_base` token count
over the entire canonical JSON, including metadata and optional locators, within
800 tokens and three sources. Neither number promises the exact count of every
client model.
Do not change the public estimate globally to simulate this internal admission
policy. A shorter snippet still must retain a qualified contiguous source span.

## Bounded source analysis

Repository maps and code graphs share one captured set of parsed source facts
within a request. Each independently selects and budgets its results; consumers
cannot mutate the shared capture. A new request captures fresh facts. This is not
a global cache. Path discovery alone does not require a connectivity graph;
explicit call paths and cross-module relationships can still request it. Existing
patch-target recovery keeps its own routing checks.

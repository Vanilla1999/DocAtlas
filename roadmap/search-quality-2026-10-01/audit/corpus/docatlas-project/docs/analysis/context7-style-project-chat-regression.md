# Context7-style project-chat assessment

## What is established

After a successful current-state sync, the 15-question Russian newcomer run
returned one formally supported answer, one partial retrieval-only context, and
13 `insufficient_evidence` results. The formally supported first-commands case
was semantically wrong because generic CLI commands were interpreted as the
Docs MCP public-tool inventory.

The code path explains the low useful-retrieval rate:

- parser uncertainty is represented in the strict answer requirements;
- ordinary non-mutation requests initially enter the `docs_answer` route;
- `docs_context` exists, but it is a conditional fallback;
- Russian lexical queries have weak overlap with mostly English documentation;
- auxiliary retrieval queries were not eligible to carry broad context through
  the model-visible projection.

## What is not established

The standard public path was already bounded before commit `735e58f`. Removing
compatibility surfaces removed optional permissive routes, but it does not by
itself prove that the standard public route regressed. A causal claim requires a
fixed-corpus A/B comparison of the old public bounded route, compatibility
routes, the current public route, and raw retrieval before projection.

The initial zero-document state is consistent with the intentional breaking
cutover from the former namespace to current `.docatlas` state. Production code
must not rediscover, inspect, or diagnose `.docmancer`; an absent current index
uses the existing `project_docs_found_not_indexed` recovery and an explicit
`sync_project_docs` action.

## Change implemented here

This pull request restores useful bounded context without restoring a legacy
surface:

1. broad reviewed EN/RU project-documentation intents receive retrieval-only
   English aliases inside the resolved project identity;
2. those aliases are visible only to the `docs_context` projection;
3. broad aliases force non-authoritative context delivery even if an accidental
   narrower proof could otherwise be assembled;
4. generic first commands no longer become the Docs MCP tool inventory;
5. bare Russian `Архитектура?` is no longer rewritten as MCP-server
   architecture;
6. Russian parser recovery no longer manufactures mixed-language questions;
7. named policy/contract/rule questions do not receive a synthetic broad alias.

## Deliberate boundary

This is a provider-free lexical bridge for audited documentation intents, not a
universal translator. It makes the observed newcomer flow useful while retaining
fail-closed behavior outside those families. A generic dense multilingual
profile remains a separate change until calibrated provenance survives the full
public `get_docs_context` path.

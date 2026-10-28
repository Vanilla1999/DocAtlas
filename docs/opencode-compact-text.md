# Compact MCP text for ordinary OpenCode (no private metadata required)

The default `doc-atlas install opencode` registration now sets both
`DOCATLAS_MCP_TEXT_FALLBACK=1` and `DOCATLAS_MCP_COMPACT_TEXT=1`. An existing
registration is upgraded idempotently by running `doc-atlas install opencode`
again (add `--project` for a project-owned config). Updating the package alone
**does not edit existing OpenCode configuration**; restart OpenCode after
registration. This changes only OpenCode's registered DocAtlas MCP environment,
not other MCP consumers or selection policies.

## Why not just set `DOCATLAS_MCP_MODEL_VIEW=1`?

That earlier mode transmits a concise `content[].text` plus the complete
source packet in MCP `_meta`. The pinned stock OpenCode v2.1.2 adapter in
`anomalyco/opencode/packages/core/src/mcp/client.ts` (`toCallToolResult`)
retains `structuredContent` and `content`, but drops response `_meta`.
`packages/core/src/tool/mcp.ts` exposes `content` to the model and parses the
text JSON when no output schema is declared. Turning on the private-ledger
mode for stock OpenCode would lose the original `source-packet` and make its
response-local short references non-resolvable.

The new **standalone text** mode has no private dependency: selected source
text, its original `evidence_id` (`sources[].ref`), `source_uri`, path, section,
line range, project identity, scope, version, authority and trust remain in the
text. Source common values are stated once in `source_context` where possible.
No new LLM calls, generated paraphrases, selection, fetch or permission grants
are involved. A different status, denial, edit/lifecycle result, unknown future
source shape or capacity problem uses the established **full JSON text** route.
`DOCATLAS_MCP_MODEL_VIEW=1` and `DOCATLAS_MCP_COMPACT_TEXT=1` are mutually
exclusive. For an immediate rollback, remove/set
`DOCATLAS_MCP_COMPACT_TEXT=off` in OpenCode's DocAtlas environment; retain
`DOCATLAS_MCP_TEXT_FALLBACK=1`.

The compact JSON is a model-facing **view**, not a replacement for a full
DocAtlas `docs_context` machine packet or a sufficiency certificate. It does not
edit the selected source bytes, widen scope or confer answer/edit authority.
Clients requiring the full schema must keep the old JSON text interface.
The existing full-machine packet safety budget remains; no new 3,000-token
cap is introduced.

## Evidence

On 58 previously captured real stdio context calls (57 successful text
responses, one retained error), an offline projected OpenCode text-only view
with exact original evidence identities required **62,560 vs 84,228** o200k
text tokens (**25.7% less**): V40 65,732→51,166; L10 10,164→6,370;
LM08 8,332→5,024. Original selected snippets, paths, lines,
source IDs/URIs, scope/version/authority/trust, source ordering and omission
notices were checked. This is less than the 38.4% reduction of the incompatible
private-metadata model view because resolvable evidence IDs and URIs must stay
in text. Real installed stdio and registration checks are separate in the
workflow. **No paid GPT/OpenCode conversation or billing was measured**;
MCP-text tokens are an input proxy, not guaranteed invoice savings.

The dedicated GitHub Actions workflow builds and installs a wheel, tests a
real source-ingest/SQLite/stdio lifecycle, verifies existing-registration
migration and source/denial preservation, then independently re-scores the
frozen recorded 58-question corpus without tuning the selector or gold.

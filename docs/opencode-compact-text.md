# OpenCode: concise instructions and self-contained MCP text

## Installation and normal use

The default `doc-atlas install opencode` registration now sets both
`DOCATLAS_MCP_TEXT_FALLBACK=1` and `DOCATLAS_MCP_COMPACT_TEXT=1`. An existing
registration is upgraded idempotently by running `doc-atlas install opencode`
again (add `--project` for a project-owned config). Updating the package alone
**does not edit existing OpenCode configuration**; restart OpenCode after
registration. This changes only OpenCode's registered DocAtlas MCP environment,
not other MCP consumers or selection policies.

When the compact-text flag is active, **Context Assembly defaults to
`adaptive`** after upgrading to a package containing this change and
restarting the MCP server. It may put columns and source-group indexes in the
model-visible JSON, with a self-contained reading legend and the original
source refs, paths and line ranges. To restore the previous JSON shape set
`DOCATLAS_CONTEXT_ASSEMBLY=literal` in the DocAtlas MCP environment and restart.
Clients that do not enable compact text remain unaffected. This is an
evidence-preserving transport improvement; paid-model reading accuracy remains
unverified until a real answering A/B is run.

The advertised three-tool surface is sufficient for ordinary calls. With
`doc-atlas install opencode --project`, the installer explicitly binds the
selected project in the MCP launch command. The agent passes only the unchanged
question: omitted target/scope searches all prepared docs in that project,
including catalogued module docs. It does not need to know a documentation folder.
Global registrations remain unbound: pass a known absolute `project_path` or an
explicit registered `library`, or configure `docs-serve --project-root` once.
See [the current-project contract](current-project-default.md). The agent does not need to load a
skill, enumerate tools again or call `docs_status` before each read. The optional
documentation-language mode still requires its scoped language metadata when
unknown. Installed guidance adds the short workflow; repair, preparation and
advanced patch details remain in guides loaded only when needed.

Global installation writes the optional OpenCode skill. `--project` writes a
managed repository instruction block and its guides, preserving other text.
These are separate instruction surfaces: do not add their measurements to the
tool catalog as if every client always injects all of them.

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
are involved. Denials, errors, edit/lifecycle results and advanced patch packets
keep their existing routes. An unsupported ordinary documentation shape can use
the complete canonical JSON only if that fallback fits the compact-text budget.
`DOCATLAS_MCP_MODEL_VIEW=1` and `DOCATLAS_MCP_COMPACT_TEXT=1` are mutually
exclusive. For an immediate rollback, remove/set
`DOCATLAS_MCP_COMPACT_TEXT=off` in OpenCode's DocAtlas environment; retain
`DOCATLAS_MCP_TEXT_FALLBACK=1`.

The compact JSON is a model-facing **view**, not a replacement for a full
DocAtlas `docs_context` machine packet or a sufficiency certificate. It does not
edit the selected source bytes, widen scope or confer answer/edit authority.
Clients requiring the full schema must keep the old JSON text interface.
For ordinary successful `docs_context` in this explicitly enabled profile,
both compact output and a canonical fallback must fit the existing compact-text
budget: `max(o200k_tokens, ceil(UTF-8 bytes / 4)) <= 12000`. The fallback path now
uses that check too; previously a failed compact rendering could emit a canonical
packet without this check. This does not change source selection, the
underlying tokenizer, Context Assembly or private model view. It does not add a
limit to advanced v4 patch packets or to consumers with compact text disabled.

## Delivery failure is distinct from missing evidence

If compact rendering fails and the complete canonical fallback also exceeds
the budget, the server now returns a small MCP error:
`context_delivery_unavailable`, `isError=true`, `retryable=false`. It includes a
diagnostic reason instead of a partial success packet. The agent must not
interpret this as missing documentation, repeat the unchanged call, broaden the
scope or treat a grep recovery from the saved dump as successful MCP delivery.
Host configuration or the delivery defect must be addressed before retrying.

| Observed text | Interpretation |
| --- | --- |
| `docatlas.assembled-*.v1` | Self-contained assembled layout was delivered. |
| `docatlas.standalone-text.v1` | Self-contained literal layout was delivered; adaptive may select it. |
| Complete canonical JSON within the budget | Compatibility fallback; no source fields were silently removed. |
| `context_delivery_unavailable` | Selected evidence could not be delivered in this profile. |
| OpenCode reports truncation | Inspect the actual model-visible result; server `ok` alone is insufficient. |

Compact JSON can also occupy one physical line. Line count alone does not
identify the selected representation, and adding newlines does not reduce its
size. An absent `assembled-*` marker alone does not prove Assembly was skipped:
literal and its ordinary fallback preserve `docatlas.standalone-text.v1`.

## Diagnose the installed route without a model call

Record the executable and package path actually used by the registered MCP
command, the active global/project registration, and these effective process
settings. A checkout SHA alone does not identify a running installed server.

| Setting | Meaning |
| --- | --- |
| `DOCATLAS_MCP_TEXT_FALLBACK=1` | Put the response in the text channel consumed by OpenCode. |
| `DOCATLAS_MCP_COMPACT_TEXT=1` | Enable the self-contained compact route. |
| `DOCATLAS_MCP_MODEL_VIEW` absent or `off` | Avoid the private-ledger route that stock OpenCode cannot preserve. |
| `DOCATLAS_CONTEXT_ASSEMBLY` absent or `adaptive` | Choose a reversible layout; `literal` is an explicit rollback. |
| `DOCATLAS_CONTEXT_COMPRESSION` | Separate section-selection setting; `off` disables it. |
| `DOCATLAS_MINILM_MODEL_DIR` | Explicitly provisioned MiniLM assets; when compression is unset, a nonempty path enables section selection. |

No model directory is a supported configuration. Installation neither downloads
MiniLM nor silently enables a new selection policy. When comparing with an
installed acceptance run, compare these settings too; equal questions and package
versions alone do not establish equal selection or delivery routes.

Use the saved full MCP response to inspect the first rejected transformation and
the sizes of its intermediate views. There are two size checks before Context
Assembly: the initial model view and the standalone view with public refs/URIs.
A large original packet does not by itself prove either check failed, because
the transformed view can be smaller. Also check unsupported source fields,
duplicate refs and an invalid Assembly policy. Keep raw evidence out of routine
diagnostic output; report bounded reasons and sizes instead.

After repair, verify the selected source text, public refs/URIs and line spans in
the actual OpenCode tool message. A saved full dump, server `ok`, source count or
`truncated=false` alone does not establish useful delivery. Client/provider
quality and billed tokens require a separate real client measurement.

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

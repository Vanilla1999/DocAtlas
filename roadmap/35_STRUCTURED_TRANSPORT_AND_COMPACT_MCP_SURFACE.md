# Task 35 — structured transport and compact public MCP surface

## Priority

P1 recurring-token reduction. Start only after Task 34 establishes a checked-in local footprint baseline.

## Implementation status

Implemented locally after Task 34 and hardened after adversarial review. The default surface remains three tools and now measures 2,001 canonical UTF-8 bytes (~501 estimated tokens) for `tools/list`, down from the 13,470-byte Task 34 baseline. The advertised output schema accepts both canonical success and bounded error envelopes; internal validators retain the detailed contract. Error messages, tracebacks, hints, warning fields, and location metadata are bounded, and MCP errors are marked `isError`. Normal calls still use a constant 57-byte marker plus one structured payload; explicit `DOCATLAS_MCP_TEXT_FALLBACK=1` remains text-only. These are provider-free byte gates, not provider-token or benchmark claims.

## Problem

The public `get_docs_context` definition currently advertises retrieval, pagination, formatting, debug, maintenance, delivery, and budget controls together with a detailed `ActionPacket` output schema. MCP clients may resend this static catalog on every model request.

For non-bounded compatibility results, the server also serializes the complete payload into text while attaching the same value as `structuredContent`. Clients that expose both channels to the model can therefore receive the same result twice.

The model is also responsible for selecting `delivery_strategy="bounded_direct"` and a packet budget. Forgetting those optional arguments returns the broad compatibility shape, even though bounded delivery is the intended normal coding workflow.

## Goal

Keep exactly the existing three public tools while making their advertised catalog and transport compact. Server policy, not model prompt accuracy, owns the normal bounded response.

The agent still calls `get_docs_context` itself. This task does not replace the Context7-like MCP interaction with host prefetch.

## Public contract

The default public `get_docs_context` input schema should expose only fields needed for normal selection:

```yaml
question: string                  # required
project_path: string | null
library: string | null            # canonical ID/name when known
version: string | null
mode: auto | project | library | mixed | null
```

The server owns:

- bounded delivery selection;
- response kind;
- retrieval/source limits;
- packet budget and hard ceiling;
- safe network default;
- pagination of internal diagnostics;
- debug/full-output availability.

Advanced and legacy arguments may remain accepted by compatibility handlers for a documented transition period, but they are not advertised to ordinary coding agents. Do not silently delete CLI or internal APIs that still use them.

`prepare_docs` and `docs_status` remain public because repository policy requires the three-tool surface. Their advertised schemas and descriptions must be shortened to the normal workflow. Rare admin/debug fields remain available through existing advanced/admin/legacy surfaces or CLI, not the default catalog.

## Structured transport contract

Default structured response:

```yaml
content:
  - type: text
    text: "Structured DocAtlas result attached."
structuredContent: <canonical payload>
```

Rules:

1. The full JSON payload appears in one transport channel only.
2. The default text marker is constant, contains no retrieved document text, and is at most 128 UTF-8 bytes.
3. `DOCATLAS_MCP_TEXT_FALLBACK=1` may support old clients that cannot consume `structuredContent`, but fallback mode must return full JSON in text **without** attaching an equal structured payload.
4. Fallback state is explicit in diagnostics/logging, not silently auto-detected from model behavior.
5. Errors use one bounded canonical representation and obey the same no-duplication rule.

## Output schema policy

The detailed `ACTION_PACKET_OUTPUT_SCHEMA` remains an internal server validator and test contract. The default `tools/list` entry should either:

- omit `outputSchema`; or
- publish a minimal envelope schema containing only `status`, `kind`, and the presence of the canonical payload.

Do not publish the full nested ActionPacket schema merely so the server can validate its own output. Any change must remain valid under the MCP SDK used by DocAtlas.

## Compatibility and rollout

This task explicitly approves changing the default behavior when a public caller omits `delivery_strategy`: the result becomes bounded. It does not approve deleting previously accepted arguments or CLI capabilities without a documented deprecation path.

1. Add characterization tests for existing bounded and compatibility calls before changing the catalog.
2. Make the new compact advertised schema accept normal calls without `delivery_strategy`.
3. Treat absence of `delivery_strategy` as bounded default in the public handler.
4. Keep an explicitly named compatibility path for broader exploration; it must not be the default agent-facing behavior.
5. Update `AGENTS.md`, installed templates, MCP resources, README examples, and user docs so agents stop sending server-owned arguments.
6. Record a migration note for integrations that relied on model-selected `output_mode`, pagination, or maintenance fields.
7. Do not add a fourth public tool.

## Required work

1. Shorten public tool descriptions to decision rules, not an embedded operations manual.
2. Reduce the advertised `get_docs_context` schema to the normal selection fields.
3. Reduce advertised `prepare_docs` and `docs_status` schemas to their common safe path while retaining explicit compatibility coverage for older calls.
4. Make bounded delivery the public server default.
5. Move debug/full/unbounded selection behind an advanced or explicit compatibility boundary.
6. Replace full text JSON with a marker whenever structured content is present.
7. Add the text-only compatibility mode with mutually exclusive transport channels.
8. Remove the full ActionPacket schema from the default tool catalog while continuing internal validation before return.
9. Run the Task 34 footprint command in tests and check the catalog budget.
10. Update generated/installed agent contract fixtures deterministically.

## Hard local gates

- default public tool count: exactly `3`;
- serialized default `tools/list`: at most `10 KiB`;
- target serialized default `tools/list`: at most `6 KiB`;
- marker text: at most `128 bytes`;
- `mcp_duplicate_payload_bytes`: exactly `0` for every default fixture;
- one normal model call need not provide `delivery_strategy`, `packet_tokens`, `output_mode`, pagination, or diagnostics flags;
- no raw `context_pack` appears because the model omitted a bounded-delivery argument.

The target may be stricter than the hard gate. A PR above 6 KiB must explain the remaining catalog bytes by tool/field using Task 34 output.

## Expected implementation areas

- `docmancer/mcp/docs_server.py`
- `docmancer/docs/interfaces/mcp/context_tools.py`
- `docmancer/docs/application/action_packet.py` only for internal validation wiring, not schema weakening
- `docmancer/docs/agent_contract.py`
- `docmancer/templates/`
- `AGENTS.md`
- MCP/user documentation and focused tests

## Local verification

```bash
uv run pytest tests/docs/test_mcp_token_footprint.py
uv run pytest tests/docs/test_mcp_docs_tools_registration.py tests/docs/test_action_packet.py
uv run pytest tests/test_unified_docs_context_mcp.py tests/test_install_cmd.py
uv run python -m compileall docmancer
git diff --check
```

No benchmark or provider call is required. Existing local behavioral tests must still prove that the same authoritative evidence produces a valid bounded packet.

## Acceptance criteria

- The default public surface still exposes exactly `get_docs_context`, `prepare_docs`, and `docs_status`.
- A normal agent call is bounded without model-selected delivery/budget/debug arguments.
- The default catalog meets the 10 KiB hard budget and reports its measured size.
- Full payload duplication between text and structured channels is impossible by construction and covered by tests.
- Text fallback is explicit, mutually exclusive, bounded, and documented.
- The detailed packet schema remains enforced internally even when omitted from `tools/list`.
- Existing compatibility calls have named tests and a migration path.
- Installed agent instructions match the new server-owned defaults.
- Focused local tests, `compileall`, and `git diff --check` pass.

## Non-goals

- Do not change evidence ranking or ActionPacket factual content.
- Do not lower the 2,000-token hard packet ceiling in this PR.
- Do not remove the three-tool lifecycle workflow.
- Do not add automatic network access or preparation.
- Do not claim that a smaller catalog proves a smaller complete agent session.

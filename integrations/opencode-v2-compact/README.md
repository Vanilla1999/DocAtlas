# Opt-in OpenCode V2 compact adapter

Verified against **OpenCode 2.2.5**. This local server plugin forwards DocAtlas's
already assembled, self-contained text through a native tool. It neither selects
sources nor changes their text, references, scope, quality or continuation fields.
The tool is removed from Code Mode by the supported tool transform API.

## Install explicitly

Keep this directory intact. Install the **latest Step10 candidate package** into
an isolated Python environment. It must include
`docmancer.docs.domain.minimal_context_config.EMERGENCY_TOKENS`, the bundled
offline `o200k_base` vocabulary and `regex`. An older published/current shared
installation may lack this new contract and is not sufficient. Use that environment's
absolute Python path (not a checkout-dependent `PYTHONPATH`). Add this plugin
**last** to the project's `opencode.jsonc`, preserving other settings:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "plugins": [{
    "package": "/absolute/path/integrations/opencode-v2-compact",
    "options": {
      "python": "/absolute/path/docatlas-venv/bin/python",
      "tools": ["docatlas_get_docs_context", "docatlas_read_docs_source"]
    }
  }],
  "tool_output": { "max_bytes": 6400000, "max_lines": 6400000 }
}
```

`tools` must contain the **effective native tool IDs from your installed catalog**,
including candidate `read_docs_source` (normally `docatlas_read_docs_source`). Server prefixes vary;
do not assume the example matches every installation. The adapter follows MCP
catalog refreshes. It leaves inputs, permissions and underlying execution intact.
Do not enable this on a generic resource reader serving unrelated servers. A
resource reader is covered only when its dedicated native ID is explicitly listed.

With the minimal-context candidate enabled, the server advertises
`read_docs_source({uri})` after its existing three public tools. Prefer it over a
generic resource reader: it delegates to the same `resources/read` handler, with
the identical one-use source capability, snapshot and expiry checks, and returns
one canonical text block. It accepts no filesystem path, new scope or line range.
Both documentation context and dedicated source reads are then guarded by this
plugin; resource failures and emergency envelopes remain visible as exact text.

The host output configuration is necessary: OpenCode's default 51,200-byte limit
can hide even a 20,042-token packet in a file. The pinned vocabulary's longest token
is 128 bytes: 50,000 tokens need at most 6,400,000 UTF-8 bytes. The explicit line
limit also prevents a smaller line ceiling. These are host rendering allowances,
not selection targets. They apply to other tools in this project too. No default
configuration is changed by adding these files to this repository.

## Boundary and failure semantics

- Exactly one text content block is forwarded byte-for-byte. No `_meta`-only
  evidence, structured-body duplicate, or hidden-file substitute is used.
- The complete text is priced before return, and again after OpenCode rendering
  in `context`, `compaction`, `generate` and `title` hooks. Above **50,000** tokens
  the model receives `context_emergency_stop`, measured size and no source body.
- The threshold comes from the installed package's single canonical
  `minimal_context_config.EMERGENCY_TOKENS` constant. The Python subprocess returns
  `{emergency_tokens, counts}`; JavaScript reads it at startup and verifies it on
  each count. There is no separate JavaScript threshold or agent/config override.
  A missing contract fails activation; a changed contract requires plugin reload.
- An unavailable counter or unsupported envelope fails closed with
  `client_envelope_unverified`; the observed 2.2.5 truncation marker becomes
  `client_output_truncated`. No prefix or automatic continuation is supplied.
- This is an **o200k text-result** boundary, not provider-specific framing tokens
  or a limit on the entire conversation. Later plugins/HTTP rewrites can invalidate
  it; install last and reverify after upgrading OpenCode or adding transforms.
- Server capabilities may already be registered when the client rejects a result.
  This plugin withholds their text but cannot roll back server registration. The
  server must independently implement atomic delivery/emergency semantics.
- Source reads, stale/replay checks and resource lifecycle are the server's job.
  The replay spike below does **not** prove working historical source capabilities.

## Measured spike (2026-11-06)

One recorded public T12-ru packet, SHA-256
`48ffa86c21f6475216777070c18258b52987de0a4748e0dd6b1cef1925d6c20a`,
was replayed through actual MCP/Code Mode/native execution and captured at the
outgoing OpenAI-compatible HTTP endpoint. Only the external provider was scripted;
there were no paid answering-model calls. Recorded MCP replay is not fresh retrieval.

| Actual client path | Tool-result o200k tokens | Fidelity |
|---|---:|---|
| Code Mode returns object | 5,356 | decoded packet identical |
| Code Mode returns `JSON.stringify(packet)` | 4,854 | exact compact bytes |
| Native MCP text | 4,854 | exact compact bytes |
| Native adapter | 4,854 | exact compact bytes |

Rechecked after the server agent's single-TextContent update: **without any
`structuredContent`**, Code Mode still parses the JSON text and re-expands an
object to 5,356 tokens. Returning a string and the native adapter both preserve
4,854 tokens/exact bytes. New artifacts:
`/tmp/opencode/step10-spike-textonly-{object,string,adapter}`. Use
`--text-only-mcp` to reproduce this current wire contract.

Savings: **502 tokens / 9.37%** for this packet, not a corpus-wide or total-input
claim. Native tool schemas cost 3,286 tokens versus 3,249 for Code Mode in this
environment (+37). System/catalog text also changed across isolated locations;
it is recorded separately, so these runs do not establish whole-session savings.

Additional actual-client checks:

- 100,160-byte / 20,042-token synthetic packet: exact bytes including tail survive
  with the documented host configuration.
- Same packet under default output limits: hidden-file truncation detected;
  explicit 45-token refusal instead of pretending evidence was delivered.
- 60,042-token synthetic packet: blocked before rendering; 46-token refusal.
- Defect injection **after** execution: 4,854-token real packet inflated to 64,854
  by an earlier context hook; final adapter guard blocks it with a 46-token refusal.

Artifacts (four forms, actual provider requests, session context, receipts):
`/tmp/opencode/step10-spike-{object-ready,string-ready,native-ready,adapter,large-supported,over,truncation-detected,inflated-envelope}`.
The initial two attempts exposed MCP readiness and empty HTTP response handling
in the probe; they are retained under `step10-spike-{object,native}` and are not
successful measurements. The first large-packet probe exposed host truncation
(`step10-spike-large-under`), leading to the explicit installation requirement.

Reproduce from the repository Python environment:

```sh
.venv/bin/python eval/blind_project_context/spike_opencode_compact.py \
  --packet /path/to/recorded-public-packet.json \
  --output /tmp/opencode/new-spike-directory \
  --arm native_adapter --large-output
```

Other arms: `codemode_object`, `codemode_string`, `native_raw`.
For a >50k fixture add `--expect-stop context_emergency_stop`. To exercise the
post-format guard on a small packet additionally use `--inflate-model-envelope`.
For the default-host truncation check omit `--large-output` and use
`--expect-stop client_output_truncated`. Each run makes two scripted provider
requests and one replay tool call; the probe requires a new output directory.

API references verified using V2 documentation and Context7:
[server plugins](https://opencode.ai/v2/docs/build/plugins/server),
[configuration](https://opencode.ai/v2/docs/config),
[providers](https://opencode.ai/v2/docs/providers).
No invented pretty-print option or V1 plugin hooks are used.

### Candidate-package verification status

The initial presentation measurements used the then-installed tokenizer package.
After centralizing the threshold, the shared installed environment was found to
lack the latest candidate module. It was **not modified**. Scoped re-verification
uses `/tmp/opencode/step10-adapter-source-python`, a diagnostic executable that
sets an explicit checkout `PYTHONPATH` and invokes the existing Python. This is
source-backed adapter verification, **not installed-candidate package acceptance**.
Use `--adapter-python` in the probe to select an isolated installed candidate for
the latter. The diagnostic override is not the installation recipe above.

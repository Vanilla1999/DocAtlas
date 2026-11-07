# Explicit read-only documentation profile

`documentation-light-v1` is an optional OpenCode V2 location for reading an
already prepared documentation project. It connects the real installed DocAtlas
MCP and reuses the existing native compact adapter. It does not select a different
retrieval model, create an index, install a skill, modify `AGENTS.md`, or replace
your ordinary coding agent.

The profile uses full source identifiers and ordinary JSON objects, without a
table legend, column dictionary or shortened citation aliases. The server option
is `DOCATLAS_CONTEXT_PRESENTATION=literal-v2`. Original source text, paths, lines,
source URIs, scope and trust metadata remain visible. Source validation remains
the server's responsibility; the profile does not remove validation hashes from
machine packets or from source-read/patch contracts.

## Connect it to a project

Keep this integration directory intact at a stable absolute path. Install the
current DocAtlas wheel into an isolated environment. Use that environment's
`doc-atlas` and Python executables, not an editable checkout or a Python from a
different environment.

Create a **new dedicated location**, leaving existing OpenCode configuration intact:

```sh
/absolute/docatlas-venv/bin/python /absolute/DocAtlas/integrations/opencode-v2-compact/documentation_profile.py \
  --project /absolute/project \
  --output /absolute/documentation-client \
  --executable /absolute/docatlas-venv/bin/doc-atlas \
  --python /absolute/docatlas-venv/bin/python
```

This writes `opencode.json` and `profile-receipt.json`. It refuses to overwrite an
existing configuration. No provider request or source preparation occurs. To use
an existing host-selected store or explicitly configured retrieval mode, pass
`--server-env-json /absolute/server-environment.json`, a JSON map of environment
variable names to string values. The profile does not automatically enable
MiniLM, E5, Qwen or minimal context. It requires a self-contained text channel;
the private-ledger `DOCATLAS_MCP_MODEL_VIEW=1` mode is incompatible.

Then start OpenCode in that location with the generated `docs` agent and the
provider/model you normally use. For an exact question file:

```sh
cd /absolute/documentation-client
opencode run --agent docs --model your-provider/your-model < /absolute/question.txt
```

`--model` can instead be supplied to the generator, or omitted to retain the
client's configured model. An optional `--max-steps` creates an explicit host
limit. The profile adds no default model-step limit.

The generated `opencode.json` embeds the instruction text at generation time.
To adopt an updated profile prompt, generate a **new dedicated location** using
the updated integration and launch OpenCode there. Updating the integration files
alone does not replace the prompt in an existing configuration. The generator
continues to refuse overwrites, and the receipt records the actual prompt hashes.

## What the profile changes

- The MCP project root is explicitly bound. This first profile fixes
  **project scope**. Requests for another root, module, library, or wider scope
  are rejected; use the ordinary integration for those workflows.
- Only `get_docs_context`, project `docs_status`, and issued source reads are
  available. `read_docs_source` is used when the selected server mode advertises
  it. Otherwise `opencode_read_mcp_resource` is restricted to this server and
  `docatlas://source/` URIs. Source capability, snapshot, expiry and one-use checks
  still happen on the server.
- Other MCP servers are removed from **this dedicated location's** configuration.
  Permissions and final model-tool filtering exclude shell, writes, preparation,
  job inspection, web research and delegation. The tool input schemas are
  retained. A runtime `execute.before` hook enforces the target restrictions even
  when OpenCode attaches MCP executors after initial registry transforms.
- In pinned V2.2.5, MCP's connected notification can precede publication of its
  native tools. Before admitting an MCP prompt, the profile checks the public
  tool registry for the exact context/status IDs. It checks again every 25 ms
  until they exist, with a 10-second deadline and an explicit readiness error.
  It waits for this actual condition, not for a fixed startup delay, and records
  checks/duration in prompt metadata. The files control has no such wait.
- A shared documentation prompt plus the backend's mechanics replaces injection
  of the whole installable skill. Applicable global/project instructions remain
  enabled. If the location is outside the bound project, its root `AGENTS.md` is
  included explicitly. The generator does not discard instructions to lower a
  token count; inherited and dynamically discovered instructions remain part of
  the actual client input.
- The language preflight is conditional, as in the existing contract. There is
  no arbitrary `--language en` switch or unverified language cache. Reuse requires
  matching project/scope/version/snapshot metadata; otherwise project status is
  still needed. Unknown or mixed language is not assumed to be English.
- Titles are deterministic in both comparison backends. The profile neither
  summarizes nor removes previous tool results or conversation history.
- The existing native adapter guards complete model-facing tool text with the
  installed package's 50,000-token emergency limit. This is not a context target
  or a limit on the whole session. Host rendering allowances and refusal behavior
  are the same in both lightweight comparison backends.
  Native resource/file tools use its `guard_tools` path: their execution, typed
  output and rendering stay native, and the final model text is checked. MCP
  tools retain the strict authoritative-text path. The profile explicitly sets
  native MCP mode, including for tools attached after plugin setup.

The plugins remain in the generated order, with the compact adapter last. Do not
move this restrictive profile into a general coding location or remove its scope
guard while retaining the file-tool permissions. This is an application-level
profile, not an operating-system sandbox.

## Source-to-draft check

The shared `profile/common.txt` now asks for one final comparison of the draft
against each question-relevant statement in the supplied sources: add supported
omissions and remove unsupported claims, then return only the final answer.
Both MCP and files profiles receive this same paragraph through the builder.
This is an internal answer-writing instruction, not a new tool, permission,
retrieval route or client-scheduled provider request. It cannot recover evidence
that was never supplied and does not certify that all relevant conditions were
found. Existing scope, uncertainty, citation and stopping rules still apply.

The exact paragraph was previously tested in an
[answer-only diagnostic](../../eval/blind_project_context/step11-completeness/README_RU.md)
on four known Meridian questions with Astra Pro. With all six allowed documents,
fully preserved requirements increased from 16/19 to 18/19; one scope condition
remained partial. That result is not a general completeness guarantee, a Terra
Low result, an end-to-end OpenCode test or evidence of token savings. Prompt
delivery and final-answer quality must still be measured separately. The
historical skill, historical study prompts and frozen results are not rewritten.

## Files comparison control

`--backend files` is a **diagnostic control for an already isolated frozen
documentation corpus**, not a general substitute for MCP project authorization.
A repository root can contain private module documents and unregistered files
which project-scoped MCP must not return. The generator therefore accepts only:

- a valid finite catalog of active project-scoped source/supporting documents;
- no module/private entries, catalog roots or `code_files`;
- exactly those documents, their catalog and an optional root `AGENTS.md` on disk;
- regular files and directories without source symlinks.

Use a separate location outside, and not containing, that frozen source root.
The host records the exact file membership and hashes. Its plugin checks the
snapshot before and after native execution and constrains `read`, `glob` and
`grep` paths to the bound root. A source change requires a new control profile;
the control never exports or selects a subset of a larger repository. OpenCode
permission resources for grep/glob are search expressions, so directory safety
is enforced by the mandatory wrapper, not by pretending those resources are paths.

The two backends share `profile/common.txt`, output guards, read-only intent and
project instructions. Their mechanical prompts and tool schemas necessarily
differ and must be counted separately. The generator **does not verify MCP's
active index**. A fair comparison must separately show that public preparation
committed the same source hashes. Catalog/AGENTS metadata are available to the
file control as metadata, not extra answer evidence.

The historical agent harness remains the default. To opt into this profile in a
fresh output directory, add:

```text
--client-profile documentation-light-v1
```

to `eval/blind_project_context/run_gap_agent_study.py`. Both its MCP arm and
`file-current` arm use the shared builder. Existing non-step10 arms retain their
12-step limit; step10 arms retain their existing absence of that cap. Historical
plans, questions, scoring policies and artifacts are not rewritten. The new
receipt distinguishes the shipped skill hash from the actual injected prompt.

## Acceptance and measurement boundaries

`check_profile_client.py` exercises the user-facing generator and actual pinned
OpenCode **2.2.5** with a fresh installed DocAtlas package. Only the external
answering provider is scripted; the fixture preparation, public MCP retrieval,
issued source read, native file reads, permission/scope guards, rendering and
outgoing HTTP lowering are real. The check requires a fresh output directory:

```sh
/absolute/docatlas-venv/bin/python -I /absolute/DocAtlas/integrations/opencode-v2-compact/check_profile_client.py \
  --opencode /absolute/opencode-2.2.5 \
  --executable /absolute/docatlas-venv/bin/doc-atlas \
  --output /absolute/new-client-evidence \
  --baseline-inventory
```

The real launch is `opencode run --standalone` with the exact question on stdin;
the check does not prewarm the client through an API or inject a startup sleep.
The plan is saved before execution. It bounds two full client sessions plus an
optional historical client inventory session with no tool execution. Artifacts
record exact provider requests, installed runtime/dependencies, source and
database hashes, rejected out-of-scope operations, common prompt identity, and
local `o200k` counts for system/tools/result text. A transparent stdio observer
proves the refused job request never reaches MCP. The existing compact adapter
represents native tool failures as an undelivered error envelope, so the check
does not mistake that envelope for a source answer or require the internal guard
message to be visible. There is no model inference,
answer-quality result or provider-billing measurement.

The first outgoing provider request of each new MCP/files session must contain
the exact source-to-draft paragraph. This verifies delivery through the generated
configuration and real client, not whether a model follows the instruction or
preserves the required facts. The historical inventory prompt remains unchanged.

The same ordinary canonical MCP packet is also rendered offline with current
and `literal-v2` presentation. Ordinary standalone already omits per-source
hashes: a literal JSON result can be **larger** than its current adaptive table.
The earlier 13.71% result on saved minimal/Qwen packets does not apply to this
ordinary profile. Client catalog size, tool-result size, repeated history,
provider rounds and final-answer quality are separate measurements. A smaller
first request does not establish that DocAtlas beats file search on total cost
or answer completeness.

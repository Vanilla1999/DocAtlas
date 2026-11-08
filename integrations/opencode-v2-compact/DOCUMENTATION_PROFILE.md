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
  job inspection, web research and delegation. Tool fields and validation
  constraints are retained. A runtime `execute.before` hook enforces target restrictions even
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
- By default, the language preflight remains model-selected, as in the existing
  contract. The explicit `--language-preflight host-v1` mode below moves this
  same metadata read before the first model request. There is no arbitrary
  `--language en` switch, language guess or unverified persistent language cache.
  Unknown, mixed and partial language are never treated as English.
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

## Opt-in concise instructions experiment

The default instruction variant remains `standard`. For a **new dedicated
location**, the generator accepts:

```text
--instruction-variant concise-v1
```

This is an experiment within `documentation-light-v1`, not a new retrieval
policy or a replacement for the ordinary MCP catalog. It changes only:

- the MCP-specific paragraph, using `profile/mcp-concise.txt` instead of
  `profile/mcp.txt`;
- descriptions of the allowed MCP/source-read tools, when advertised, in the
  **model-facing session snapshot**, removing repeated rules already stated in the shared
  instructions or the concise tool prose;
- known JSON Schema `description` annotations whose exact field semantics are
  retained in that prose. All property names, required fields, enums, defaults,
  length/range limits and other validation constraints remain unchanged.

No tool is added or removed relative to the same standard profile. The existing
context/generation/compaction hooks apply the annotations to MCP tools published
after setup as well. The executable registry, server catalog, call validation,
permissions, source text, tool results and history are untouched. The same
target/scope/version, language, continuation, uncertainty and truncation rules
still apply. Technical `scan_incomplete` results are explicitly distinguished
from missing evidence in the concise prompt.

`profile/common.txt`, including the exact source-to-draft paragraph, is unchanged
and shared by both comparison backends. With `--backend files`, selecting
`concise-v1` records the variant but does not change the file prompt or native
tool descriptions. Applicable project/host instructions remain enabled.

The receipt records `instruction_variant`, `tool_description_policy` and the
actual selected prompt hash. Existing generated profiles do not gain this
variant automatically: absence of the option means `standard`.

A smaller locally tokenized prompt or a successful scripted-provider delivery
check does not establish lower provider billing or equal final-answer quality.
Those require the same real answering model and a separately fixed live run.

The bounded Step13 check and the distinction between archived provider usage,
offline sizing and the real-client scripted-provider check are recorded in
[Step13 results](../../eval/blind_project_context/step13-runtime-token-review/RESULTS_RU.md).

## Host language preflight

For a **new MCP documentation location**, add:

```text
--language-preflight host-v1
```

It can be combined with `--instruction-variant concise-v1`. The default remains
`model`: existing generated configurations do not change, and the files control
does not support this MCP-only option. The builder still makes no MCP/model
calls and does not store a language guess in the generated configuration.

At each new user prompt, after actual tool readiness, the host invokes the
connected native `docs_status` executor with the trusted project path,
`action="project"` and `include_language=true`. It uses the same server, native
permissions and source authorization. A wrong project is rejected by the
server before inspection; the host also validates the returned project path,
project ID, workspace path and project scope before accepting any hint.
This does not add a second MCP process or a host-side file-reading shortcut.

Only a bounded normalized language hint is included in the model's current
system context. The full status response, source inventory, raw messages and
warning text do not become model instructions. No synthetic assistant/tool
history is inserted. The original user question, history and source-to-draft
paragraph remain unchanged. The model can begin with retrieval instead of a
separate round choosing the language-status tool; the metadata read itself
still happens once.

The language comes from the catalog's existing `documentation_languages`
declarations, **not** from MiniLM, Qwen, an English default, source filenames or
a new classifier. An unknown declaration stays `unknown`; multilingual and
partially declared sets stay `mixed` and `partial`. A successful unknown
preflight is not an instruction to repeat the same status call. Search the
original question without assuming a source language when no useful hint is
available. Any `search_question` remains a complete model-supplied translation
with the original question preserved, not a synonym dictionary or query rewrite
performed by this feature.

The API's catalog/snapshot hashes describe current **inspected candidates and
declarations**, not an active retrieval-index version or a proof that inspection
was exhaustive. This routing hint never grants source, preparation or edit
authority. Retrieval and issued source reads retain their independent
scope/snapshot/version/expiry checks. Sources changing after preflight must
still be revalidated through those ordinary mechanisms.

Hints are bound in memory to the exact admitted session and user-message ID;
there is no fallback to another message's hint or trust in imported metadata.
When no matching current record exists, the model receives `unknown`. A new
user prompt reads metadata again. The host rejects malformed/truncated results,
binding mismatches and permission/transport errors before model admission; it
does not retry, prepare sources or silently continue with a remembered language.
The metadata read has a bounded timeout and is aborted on plugin disposal.

This is verified against the installed **OpenCode 2.2.5** native tool executor
and primary context hook. Transient generation, compaction and title hooks do
not infer or refresh a language. Reverify after a client upgrade. The bounded
acceptance plan and its limits are recorded in
[Step14](../../eval/blind_project_context/step14-host-language/PLAN_RU.md), with
[results and raw captures](../../eval/blind_project_context/step14-host-language/RESULTS_RU.md).

### Offline instruction sizing

The following command measures the instruction variant, not host-preflight
session savings. For a preserved Responses request from the diagnostic observer:

```sh
node /absolute/DocAtlas/integrations/opencode-v2-compact/measure_instruction_variant.mjs \
  --capture /absolute/saved/capture/events.jsonl \
  --python /absolute/docatlas-venv/bin/python
```

The command applies the actual session annotation transform to the first saved
request and replaces only an exact occurrence of the standard MCP paragraph.
It reports local `o200k` estimates, hashes and structural schema identity; it does
not call the provider, retrieve sources or infer a full-session saving. Counting
serialized JSON tool definitions is not the provider's internal schema accounting.

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

To compare the opt-in variant and exercise the corrected standalone launcher,
use a new output directory with these additional options instead of the optional
historical inventory:

```text
--compare-concise
--session-runtime /absolute/DocAtlas/eval/blind_project_context/step13-runtime-token-review/session_runtime.py
--check-retrieval-failure
```

This bounded roster uses at most 13 scripted provider requests: standard MCP4,
concise MCP4, files2 and a missing-Qwen-assets negative case up to3. The negative
case invokes the real installed server but fails asset verification before model
inference. It must produce failed retrieval, never a successful no-answer. The
Linux-only launcher requires `/proc`, `waitid(WNOWAIT)` and `pidfd`; it records
and verifies the actual MCP server/transport identities, including processes
OpenCode places outside its own group. Missing registration or unverified cleanup
cannot pass. This is not a GPU-memory measurement or a guarantee about unseen
detached descendants. A failed run is retained; repeats need a diagnosed change
and a new output directory.

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

## Opt-in answer-writing hypotheses

The default remains `--answer-policy current`: the existing common prompt and
generated client configuration remain unchanged. New receipt fields record the
selection and its provenance. Two **experimental**, non-default alternatives
are available for a newly generated documentation location:

```text
--answer-policy rule-contract-v1
```

or:

```text
--answer-policy evidence-led-v1
```

`rule-contract-v1` asks for claims whose applicability, required conditions,
ordering, exceptions and invariants remain explicit where relevant. Simple
factual questions should still receive direct answers, not a forced procedure.
`evidence-led-v1` instead emphasizes composing from the supplied source
statements and their dependencies, rather than using a first draft as the
inventory of what must be checked. Neither policy adds topic-specific examples,
synonym dictionaries, question-to-document mappings or an expected fact count.
Both return an ordinary final answer, not a reasoning trace.

`answer_policy.py` is the common loader for the profile and answer-only studies.
Each alternative replaces only the exact existing source-to-draft paragraph in
`profile/common.txt`. The file itself is not edited. A changed or duplicated
paragraph boundary rejects the alternative instead of silently replacing other
instructions. Shared scope, trust, uncertainty, citation, tool and stopping
rules remain in place. The default policy returns the original common text.

This option applies equally to MCP and the isolated files comparison control;
keep the selected policy equal when comparing those backends. It is independent
of `--instruction-variant` and, for MCP, `--language-preflight`. It neither selects
Qwen/MiniLM, changes retrieval or one-hop expansion, nor schedules an additional
provider call. Prompt changes can still affect a model's choices and token use;
unchanged invocation code is not a guarantee of unchanged session cost.

Receipts record `answer_policy`, the base common-prompt hash, the candidate
paragraph hash (`null` for `current`), and hashes of the actual selected input
files. `common_prompt_sha256` and `system_sha256` describe the resulting injected
text. A previously generated location does not acquire a policy automatically.

These candidates are hypotheses, not a completeness guarantee. An answer-only
comparison can isolate use of already supplied evidence, but does not establish
native OpenCode/MCP acceptance, Terra Low quality, or provider-billing savings.
No default should be promoted solely because an instruction is more explicit.

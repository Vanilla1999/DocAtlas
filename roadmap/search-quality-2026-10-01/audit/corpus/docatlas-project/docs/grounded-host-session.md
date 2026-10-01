# Grounded host sessions over MCP

`GroundedMCPSession` is a Python host adapter over an initialized MCP
`ClientSession`. It owns one project question, retains its evidence and keeps
host judgments separate from server certification. It works with structured
payloads and the configured text fallback. It is not an additional MCP tool.

## Partial answers and source reads

Declare one to three concrete facts to investigate before the first call. Call
`GroundedMCPSession.start(client, arguments=..., requested_facts=...)` once.
The arguments are the normal `get_docs_context` arguments, including the original
question, project path, scope and optional documentation-language lookups.
The adapter preserves the original question and never silently retries it.

The host reads the returned snippets and assesses whether a requested fact is
supported. `support(fact_id, evidence_id=..., quote=...)` accepts only a verbatim
quote from retained evidence. A matching quote binds the judgment to a source;
it does not prove that the quote logically answers the question. Semantic
assessment remains the host's responsibility.

A `source_uri` alone does not cause I/O. If a concrete requested fact is still
missing and the next part of the selected source may answer it, explicitly call
`await session.read(uri, missing_fact_id=...)`. The shared source-read controller
checks the locator before network/transport I/O and checks the returned project,
path, snapshot, consecutive line range, duplicates and complete serialized size.
It also rejects overlapping lines reached through different locators.

There are at most two extra actions per question, each admitting at most 600
tokens of serialized evidence. Source reads and local recovery share this action
ceiling. The primary context remains bounded to 800 tokens. These are evidence
budgets, not an estimate of the host's total conversation or reasoning tokens.

Use `session.evidence` to obtain retained citation IDs for subsequent judgments.
Do not append the entire retained collection to model history after every read;
deliver the primary payload once and only new excerpts after explicit reads.

## Failed reads and bounded local recovery

A transport failure, changed snapshot or repeated locator leaves previously
supported facts intact. The failed attempt consumes an action. Repeating the
same locator cannot cause another read.

`await session.recover(search_local_source)` can execute one advertised
`code_search` / `search_local_source` recommendation that requires no confirmation.
The host-owned asynchronous callback receives the unchanged project path and
bounded query terms, and must enforce its existing local read permissions.
It returns `{"sources": [{"path_or_url": "relative/path", "snippet": "..."}]}`,
within 600 serialized tokens. Absolute paths, traversal, empty/duplicate results,
oversized results and repeat recovery are rejected. Recovery cannot invoke
preparation, arbitrary shell commands, editing or network acquisition.

The adapter does not provide a code-search engine or grant file access. A client
without an authorized local search callback leaves the recommendation as a next
step. Preparation requiring confirmation remains a separate host decision.

## Final handoff

`finish()` returns the known quotes, their citation IDs, the human-readable
missing facts and an unconsumed next step when available. Its status is:

- `host_assessed_complete`: the host supplied a quoted judgment for every fact;
- `partial`: at least one fact has a quoted judgment and others remain missing;
- `insufficient`: no requested fact has a quoted judgment.

`answer_supported` remains false in all three states. A read failure cannot turn
an existing partial answer into an empty refusal. The host should state the
supported part, explicitly name what is unknown and provide a feasible next
step or a necessary clarifying question. Unknown private configuration is never
inferred from a general documentation quote.

## Verification boundary

Behavioral tests cover quote binding, failed reads, duplicate reads, resource
binding, recovery limits and preservation of known facts. The installed-artifact
stdio smoke uses the adapter through real MCP transport, including the text-only
OpenCode registration path. It tests the protocol and package integration, not
an OpenCode model's decisions. No live-model quality or universal answer guarantee
follows from these tests. Other host implementations must implement the same
bounded loop; merely exposing MCP resources does not install that loop in them.

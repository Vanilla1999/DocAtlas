# One-call agent-loop capability

The optional provider-neutral host adapter in `eval/task_level/one_call_agent_loop.py` demonstrates and enforces a bounded coding loop without changing the core MCP server or the frozen Task 33C protocol.

The model still chooses and requests `get_docs_context`. After one canonical result is accepted, a capable host removes the DocAtlas tool from subsequent request catalogs and retains only the objective/task hash, canonical result, action state, current diff or bounded hash summary, latest relevant failure, and concise completed-action summaries.

## Local engineering profile

`one-call-local-v1` enforces:

| Limit | Value |
|---|---:|
| successful DocAtlas calls | 1 |
| model requests | 12 |
| serialized input estimate per request | 7,000 tokens |
| repair passes after the initial edit | 1 |
| test invocations | 2 |
| captured tool output per call | 32,768 bytes |

The input estimate is deterministic canonical UTF-8 bytes divided by four. It is an engineering ceiling, not provider usage. If a provider reports usage, the sanitized audit stores only its numeric usage fields; missing usage remains `null`.

Budget exhaustion and `insufficient_evidence` are typed incomplete outcomes. A second DocAtlas call, third test invocation, second repair pass, thirteenth request, oversized required prompt, or oversized DocAtlas/action result cannot become normal success. stdout, stderr, tool-result, and diff streams share one finite capture budget; the host passes it into the execution adapter and capture stops at the boundary instead of draining an unbounded producer. A truncated execution can claim verified output hashing only when the adapter supplies a complete content hash; otherwise the retained hash is explicitly a captured-prefix hash and the capability remains unverified. Superseded or summarized blocks are represented in the host-side audit by SHA-256 and an omission reason.

## Capability truth

A host is verified only if it proves all of these controls: one-call enforcement, dynamic tool exposure, hard request/input limits, streaming-bounded output, repair/test limits, and deterministic compaction. Provider usage availability is reported separately and is not required to enforce local budgets.

The repository's generic Claude, Codex, OpenCode, and ordinary MCP client paths do not currently prove all controls and must report this capability as unverified. They remain supported by the normal three-tool MCP workflow. The deterministic fake adapter is verified only as a local contract fixture; it is not a production model runner. A future production host can implement the same adapter protocol and must pass the provider-free matrix before making the local enforcement claim.

No API credentials, paid model request, GitHub Models call, benchmark execution, or GitHub Actions run is part of this capability test. Real-model token savings and correctness remain a later evidence gate.

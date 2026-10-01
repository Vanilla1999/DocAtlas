# Task 28 — separate source provenance from instruction trust

## Priority

P0/P1 safety. Complete before the live Kotlin closure, broader external-source coverage, or real-agent benchmarks consume crawled text.

## Problem

Exact version and official-source provenance do not make document text safe instructions for an agent. External pages and repository Markdown can contain prompt injection, copied malicious instructions, or text that tries to trigger tools. Current trust language can conflate provenance/exactness with instruction authority.

## Goal

Return documentation as cited data, never as executable agent policy, and expose enough trust metadata for the host model to treat it correctly.

## Required changes

1. Define independent dimensions for:
   - source provenance/owner;
   - version exactness;
   - repository authority/status;
   - content instruction trust.
2. Default crawled external content and ordinary repository docs to untrusted data. Only explicit agent policy files within the configured repository authority may guide workflow, and even those cannot override tool/user/system policy.
3. Structure MCP results so content is clearly delimited from DocAtlas-generated next actions, metadata, and warnings.
4. Never derive or execute `prepare_docs`, network, filesystem, shell, or credential actions from indexed content text. Actions come only from typed application state.
5. Detect high-risk instruction-like patterns for warning/telemetry without pretending that regex detection makes content safe.
6. Preserve useful code/text; do not silently delete content solely because it looks imperative. Mark and delimit it.
7. Add hostile fixtures: fake system messages, tool-call requests, credential exfiltration text, instructions hidden in code/comments, and a legitimate imperative tutorial.
8. Update threat model and agent guidance with the trust contract and limitations.

## Non-goals

- Do not claim perfect prompt-injection detection.
- Do not treat all official sites as trusted instructions.
- Do not block legitimate documentation examples by default.

## Acceptance criteria

- Source exactness cannot set instruction trust to trusted.
- Hostile indexed text cannot create a typed lifecycle action in integration tests.
- Returned content is delimited and carries provenance/authority/trust metadata.
- Legitimate tutorial content remains retrievable with an appropriate data warning.
- Threat-model tests/docs and `git diff --check` pass.

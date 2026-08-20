# Agent Developer adversarial v2

This gate extends Agent Developer Protocol v1 without changing its frozen public/oracle corpus. The v1 gate must remain target-green first; v2 then exercises a small set of reviewed architectural adversarial cases and enforces model-visible token ceilings.

The v2 cases focus on failure modes rather than natural-language paraphrase volume: tiny bounded packets for definition/behavior/requirements/project policy, module-vs-project scope isolation, bounded cross-module evidence, two-scope trajectories under a shared budget, stale project-doc recovery, and ambiguity recovery including the model-visible `docs_status` hop.

Run the deterministic gate with:

```bash
python scripts/run_agent_developer_adversarial_gate.py
```

The hard invariants are:

- Agent Developer v1 remains target-green;
- every `get_docs_context` projection fits its reviewed per-call ceiling and any explicit `packet_tokens` request;
- every complete coding-agent evidence trajectory stays at or below 2,000 model-visible tokens;
- `docs_status` recovery output is counted in the same trajectory budget;
- exact module scope, returned recovery candidates, forbidden-source isolation, and non-edit-ready insufficient evidence remain fail-closed;
- stale project evidence returns reviewed sync guidance rather than silently authorizing edits.

The companion mutation gate runs a provider-free self-test against the new validators and a production ambiguity mutant:

```bash
python scripts/run_agent_developer_adversarial_mutation_gate.py
```

A mutant survives only if one of the new critical safeguards can be removed without a deterministic gate noticing. The mutation harness copies `scripts/` as well as runtime/eval/tests so mutations of the gate itself are exercised in the isolated copy.

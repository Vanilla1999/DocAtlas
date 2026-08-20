# Agent Developer adversarial v2

This provider-free gate extends Agent Developer Protocol v1 without changing its frozen corpus. V1 must remain 11/11 target-green; v2 adds 28 reviewed architectural scenarios and measures every model-visible DocAtlas projection.

The v2 corpus covers bounded definition/behavior/requirements/project-policy packets plus an unsupported policy-detail fail-closed case, exact module-name/path resolution, bidirectional module isolation, project-vs-module leakage, cross-module evidence, multi-scope trajectories, stale project/module recovery, dependency-prefetch recovery, traversal/absolute/prefix/case/long-path safety, and five-way module-name ambiguity with a bounded `docs_status` recovery hop and exact retry.

Run the deterministic gate with:

```bash
python scripts/run_agent_developer_adversarial_gate.py
```

Hard invariants:

- Agent Developer v1 remains target-green;
- every `get_docs_context`, `docs_status`, and recovery projection is charged at its actual model-visible size;
- every complete trajectory is <= 2,000 model-visible tokens;
- requested `packet_tokens` and per-call ceilings are never exceeded;
- exact module scope, returned recovery candidates, and path identity remain fail-closed;
- forbidden-source contamination is zero;
- stale or dependency-missing evidence returns typed recovery instead of edit authorization;
- setup-only adversarial fixture files are path-bounded, byte-bounded, temporary, and never alter the frozen v1 corpus.

The bounded `docs_status` projection keeps recovery metadata small while preserving the existing active-index identity contract (`db_path`, `config_source`, `config_path`, and `retrieval_mode`) required by current clients.

The companion mutation gate:

```bash
python scripts/run_agent_developer_adversarial_mutation_gate.py
```

It kills nine v2-critical mutants covering per-call/trajectory token ceilings, contamination, scope drift, unreturned retry paths, insufficient-evidence edit readiness, production ambiguity rejection, bounded `docs_status` module inventory, and ambiguity recovery projection. The existing repository critical-mutation gate remains separate and runs first.

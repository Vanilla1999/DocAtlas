# Project chat quality protocol v1

This provider-free protocol combines two separate gates. The unit-level proof
gate contains 40 novel adversarial cases for response-contract predicates,
closed inventories, unsupported free-form relations, and positive controls.
The production-path gate syncs this repository in a fresh temporary home and
runs 20 frozen onboarding, operational, architecture, contribution,
wrong-relation, and nonexistent-fact cases through public `get_docs_context`.
The production corpus and thresholds are hash-locked by
`onboarding_protocol.lock.json`.

Run it with:

```bash
python -m eval.project_chat_quality_v1_protocol
```

The combined gate fails on any false-supported proof, wrong-predicate or open
inventory acceptance, production-case failure, operational lane contamination,
Top-1 below 80%, Top-3 below 95%, more than two false abstentions, fewer than
80% of cases scoring at least 8, or mean score below 8.

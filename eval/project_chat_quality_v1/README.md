# Project chat quality protocol v1

This provider-free development gate contains 40 novel adversarial cases for
response-contract predicates, closed inventories, unsupported free-form
relations, and positive controls. It does not replace the frozen v4 production
fixture protocol or the current-repository self-host gate.

Run it with:

```bash
python -m eval.project_chat_quality_v1_protocol
```

The gate fails on any false-supported proof, wrong-predicate acceptance,
open-inventory acceptance, generic free-form proof obligation, positive-control
regression, or exact eight-token question overlap with the frozen v4 corpus.

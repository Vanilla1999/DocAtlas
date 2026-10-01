# Product branch transfer

Transferred from `28477992` onto local `main` at `58c7f37c` in branch
`fix/checked-context-delivery`. Only the delivery commit and its evidence-set
prerequisites/tests were applied; earlier retrieval-ablation commits were not
transferred. `progress.md` is the historical experiment ledger, not a fresh
measurement on this branch.

Fresh transfer validation:

```sh
DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 PYTHONHASHSEED=0 \
/home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python -m pytest \
tests/docs/test_evidence_set_*.py tests/docs/test_source_continuation.py \
tests/docs/test_source_locator_resolution.py tests/docs/test_contiguous_seed_envelope.py \
tests/docs/test_python_module_policy_and_manifest.py -q --tb=short
```

Result: **242 passed**, including native MkDocs05/Pydantic03 delivery and
continuation replacement/replay guards. No full gate or new 80-case assessment
was run on this branch; historical results must not be represented as such.
No push, merge, or production activation authorized by this transfer.

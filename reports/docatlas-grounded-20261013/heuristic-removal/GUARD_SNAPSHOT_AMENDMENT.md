# Guard snapshot setup amendment2

guards02.log: lifecycle scenario failed after1 context on missing packing facts (real quality FAIL, **not fixed/replayed**). Restrictions scenario failed before any context because its helper assumed a single project per generation, whereas it deliberately prepares both foreign and requested projects.

Corrected only restriction setup expectation scope to root.parent with BOTH independently pinned source dictionaries, preserving every original byte/hash and public foreign/project/module/version guard. No product/wheel/question/gold changes, no weakening source allowlist, no change to lifecycle expected facts. Re-run only restriction node (previous0contexts), not lifecycle. Frozen input amendment records test-file new hash; originalfreeze/logs preserved. No output-driven product tuning. Remaining trace/freshness/partial lifecycle branches are NOT VERIFIED after early FAIL.

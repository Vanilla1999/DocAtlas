# TDD public contract checkpoint

Date: 2026-09-26. Branch: `fix/tdd-public-contract-20260926`.
Base: `54bd540f6cc130b8a056b2253aca47762cbae63a`.
Verified implementation and test commit: `01171e650fd1e1bc6ab8f79d1d2569cec9bd9267`.

## Verified execution, not a projected result

All executions below used GitHub Actions, Ubuntu, Python 3.12 and an editable installation of that exact commit. The chat container could not resolve GitHub/PyPI. No local execution is claimed.

| Commit | Workflow run | New regression result | Neighbor contracts |
|---|---|---|---|
| a05bfdb3b063166f6f6b809b0497e306fb36c552 | 36243978621 | BLOCKED: strict diagnostic registry rejected two unregistered modules; not RED | 33 passed |
| 7f4d6c54d39727c2c4cd2c3c7bdbee7cc9988e14 | 36244108607 | RED: 11 failed, 10 passed | 33 passed |
| 7ae5ca61a1fdc56836e70c7698061a55e8718dec | 36244267740 | 19 passed; two formerly masked lexical-path cases failed | 33 passed |
| e08e7796bda448aa2cf48a66c8178661c30c0535 | 36244444684 | 21 passed | 33 passed |
| 01171e650fd1e1bc6ab8f79d1d2569cec9bd9267 | 36244723785 | 82 passed, zero failures/errors/skips | 33 passed |

The last run also passed `scripts/docs_mcp_stdio_smoke.py`: scripted installed-artifact stdio and lifecycle checks, not a live model/quality benchmark. Artifact 10906992600 has SHA-256 `8e6be1d30146a13d2b099f604662b78fb93c33804e5ca4631f5aa5291c6df2eb` and includes raw JUnit XML, logs, HEAD, freeze, and a source archive. The dependency freeze differs between RED and final GREEN only in the tested DocAtlas editable commit.

## Changes

- Correct README's unsupported `mode` example; keep `scope=project` distinct from `scope=all`.
- Publish the three incremental-sync fields from existing RAW definitions in `_docs_server_shared.py::_tool_spec`, and validate against that same constructed public schema. This deliberately changes the final publisher rather than duplicating the large schema-data file.
- Reject delta fields for non-sync actions, including null values.
- Reject lexical absolute/traversal paths at the public schema boundary. This does not replace service-side filesystem and symlink containment, nor establish a previously exploitable storage escape.
- Register new tests through the existing collision-checked, hash-bound diagnostic manifest shards. No collection guard was bypassed.
- Add a read-only, exact-branch CI workflow. Main CI, release workflows, branch protection and retrieval algorithms are unchanged.

## Scope against T00-T12

T00: PARTIAL. Exact source/dependencies and targeted baseline recorded; full core baseline and a locked-environment comparison NOT RUN.

T01: README defect fixed with an inline-keyword/runtime-schema regression. A separate full machine-readable documentation-example validator is not yet added.

T02: Public schema/dispatcher fix verified, including unchanged full sync, null/empty/500-entry shapes, type/501-entry errors, action restrictions, path positions, fallback schema and independent schema copies. Existing agent-contract/template checks in the neighboring suite passed.

T03: Seven real SQLite cases passed: add, change, delete, rename, unchanged-save idempotence, refusal to delete an existing file, and outside symlink refusal. Tests inspect real source/section rows and preservation of unrelated chunk IDs. A separate two-project isolation regression and all other proposed controls are not yet added. Real lifecycle code was not changed to make these tests pass.

T04-T12: NOT IMPLEMENTED. In particular, main legacy/V2 job separation, first-loss retrieval tracing, semantic selection/window changes, new 30-question replay, full CI and final merge acceptance are not claimed.

## Resume without repeating the audit

Inspect the current branch and compare against the verified commit. Complete the remaining T00/T01/T03 controls before claiming those cards fully closed. Then implement T04 with a failing workflow contract test before changing `ci.yml`; preserve all existing required jobs. Do not change retrieval until a new exact-commit RED localizes the loss. Preserve frozen questions/thresholds, the three public tools, authority/scope/version checks and the 800-token/three-source limits.

No merge, release, main-branch update, or automatic follow-up task has been performed. This checkpoint is not a claim that the entire TDD plan or answer quality is complete.

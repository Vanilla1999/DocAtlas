# Python module size and responsibility policy

`PythonModuleSizePolicy` is the repository guardrail that limits every hand-written Python file to at most 1,000 physical lines and requires responsibility-based splitting before merge.

DocAtlas treats **1,000 physical lines as a hard upper bound for hand-written Python modules**. The limit is a guardrail, not a quality score: a 300-line file can still mix responsibilities, and a generated table can legitimately be large. Hand-written production, evaluation, and test modules must nevertheless stay at or below the bound so growth cannot silently recreate monoliths.

## Design target

Prefer modules in the **200–700 line** range when practical. Split on reasons to change, not on arbitrary line numbers. Good boundaries include domain models, parsing, persistence, transport, orchestration, formatting, and compatibility façades. Avoid `part1.py`, `misc.py`, and `utils2.py` as permanent architecture; implementation shards should have a named responsibility or remain private compatibility shards behind a stable façade.

Public import paths should remain stable when a module is split. A façade may re-export the old symbols, but new logic should live in focused internal modules. If tests or embedders monkeypatch a documented module-level seam, the façade must preserve that seam or provide an explicit replacement.

## Gate

Run:

```bash
python scripts/check_python_module_size.py
```

The gate scans all repository `.py` files, including newly created/untracked files in the working tree. It ignores only environment/build/cache directories. There is no blanket exclusion for `docmancer/`, `eval/`, or `tests/`.

A module crossing the limit must be split before merge. An exceptional temporary waiver should name the exact file, explain why splitting would be riskier, and include an expiry/removal task; there are no waivers in the current tree.

## Documentation contract for modules

Architecturally important modules should have a maintained Markdown contract and be registered in `docatlas.project-docs.yaml`. Use `scope: module` plus `module_path` so DocAtlas can filter module documentation during project retrieval. A module document should state responsibility, public boundary, invariants, neighboring modules, failure policy, and the tests that protect the boundary.

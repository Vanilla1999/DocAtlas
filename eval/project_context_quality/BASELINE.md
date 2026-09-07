# Baseline at fc0341c

## Provenance

Baseline source commit: `fc0341c` (`chore: checkpoint compound context retrieval
work`). The worktree already contained the evaluator agent's uncommitted runner
and release-gate test changes when this task began. Concurrent runtime changes
are not attributed to this corpus/report work.

The full historical live trace remains available at:

```text
/home/viadmin/.local/share/opencode/tool-output/tool_071408aac0013m3dNH7lF2i3hh
```

Its exact inputs and frozen legacy expectations remain in `cases.json`, and
were copied manually with `apply_patch` into `cases.legacy.json` without changing
one byte. SHA-256 for both:

```text
b77ae44e8fb41bc53a6aa6cf584d886ee884ba337302285e4de9af2e4a5d829a
```

This preserves the legacy permitted superseded ADR as an archival expectation;
it does not endorse it as current gold for new operational questions. The five
original natural questions were supplied verbatim in the user's follow-up and
are now preserved separately in `natural.json` before any live execution. They
are not retroactively attributed to this historical 16-case trace. The remaining
ten natural positives and independent paraphrases are explicitly authored probes.

## Reported historical results

| Evidence | Historical result | Interpretation |
| --- | --- | --- |
| Baseline targeted tests, user handoff | 116 passed | Reported baseline, not rerun here as a 116-test selection |
| Legacy hermetic contract | 16/16 | Alias/planning contract, not live usefulness |
| Old live trace | Reported PASS, 16/16 | Invalid original-coverage attribution; not accepted success evidence |
| Evaluator agent tests, user handoff | 48 passed | Existing work preserved and included in targeted verification |

The inspected historical trace reports 15 positive and one negative result,
Top-3 relevance 15, useful results 15, Top-1 fact-bearing 12, original coverage
15, direct coverage 12, derived coverage 15, lookup coverage 15, maximum three
sources, and maximum 772 estimated tokens. Those numbers are **reported old
output**, not independently valid attribution. Direct and derived categories
can overlap; they are not disjoint counts to add.

The user handoff identifies invalid attribution in that live result. The
evaluator's replacement observer audits the same public call and selected
projection rather than treating replayed/metadata-only matches as proof. A
historical green report cannot establish correctness of the new observer. No
replacement full live result has been captured during concurrent runtime edits.
The numeric thresholds and old `red_baseline` lock block are not rewritten to
make this old result green.

## Historical import-order defect

Reproduced during this task, without modifying the import graph:

```bash
DOCATLAS_OFFLINE=1 .venv/bin/python -c 'import docmancer.retrieval.dispatch; import docmancer.docs.service; print("retrieval-first imports OK")'
DOCATLAS_OFFLINE=1 .venv/bin/python -c 'import docmancer.docs.service; import docmancer.retrieval.dispatch; print("docs-first imports OK")'
```

Retrieval-first exits 1 with:

```text
ImportError: cannot import name 'canonical_hash' from partially initialized module 'docmancer.retrieval.contracts' (most likely due to a circular import)
```

The chain runs through retrieval contracts, the eager docs package/service,
library application, evidence selection, and evidence models, then re-enters
retrieval contracts. Docs-first exits 0. Passing docs-first tests therefore does
not prove import-order independence. The current worktree resolves this with a
lazy `LibraryDocsService` export from `docmancer.docs`; fresh-process checks now
pass in both orders. This section is retained as historical baseline evidence.

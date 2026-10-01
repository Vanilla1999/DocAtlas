# RFC: DocAtlas as a project constraint compiler

Date: 2026-06-28
Status: research direction
Verdict guardrail: `QUALITY_POSITIVE_COSTLY`

## Summary

DocAtlas should evolve from a docs retrieval surface into a project constraint compiler for coding agents.

The current task-level benchmark does not support claiming that DocAtlas is broadly better than repo-only agent prompting. The strongest signal is narrower: DocAtlas-assisted workflows, especially action-checklist style workflows, can surface quality/policy-clean constraints, but with higher token and wall-time cost and low confidence.

The proposed product direction is therefore not "return more docs". It is to compile visible repository and dependency evidence into an actionable constraint packet that a patch must obey.

## Product model

```text
docs storage / index
        ↓
retrieval / source selection
        ↓
context pack
        ↓
project constraints / action checklist
        ↓
patch validation
```

### 1. Docs storage / index

DocAtlas continues to ingest and store repository and dependency evidence.

### 2. Retrieval / source selection

DocAtlas selects source-of-truth evidence for the task: project docs, dependency docs, manifests, lockfiles, and relevant source excerpts.

### 3. Context pack

DocAtlas may still produce compact context packs with citations, but this becomes an intermediate product, not the main agent-facing surface.

### 4. Project constraints / action checklist

DocAtlas compiles selected visible evidence into explicit patch constraints:

- required files or layers to edit;
- forbidden edits;
- generated-file rules;
- dependency/version contracts;
- source-of-truth rules;
- do-not-duplicate policy;
- task-specific action checklist items;
- suggested tests/checks.

### 5. Patch validation

DocAtlas can validate a patch or changed-file set against the compiled constraints and report satisfied, violated, and unknown constraints.

## What DocAtlas continues to store

DocAtlas should continue to store and index:

- raw project docs: `README`, `docs/`, ADRs, module docs;
- dependency docs;
- lockfiles, manifests, and version metadata;
- selected source/code excerpts;
- indexed chunks, embeddings, and metadata;
- derived constraints, checklists, and cache entries.

The storage layer remains evidence-oriented. The new direction changes what is compiled from that evidence for coding agents.

## Product surface change

### Old surface

```text
get_docs_context → returns docs/snippets/context
```

This answers: "Here is relevant context for the task."

### New direction

```text
get_patch_constraints → returns what the agent must obey
validate_patch_against_constraints → checks patch against those constraints
```

This answers:

- what must be preserved;
- where behavior is owned;
- which files should not be touched;
- which dependency versions constrain the patch;
- what source is authoritative;
- what validation should run after the patch.

## Example constraint packet shape

```json
{
  "task_id": "example_task",
  "constraints": [
    {
      "id": "generated-files",
      "type": "generated_file",
      "severity": "must",
      "instruction": "Do not hand-edit generated *.g.dart or *.freezed.dart files.",
      "source": "docs/generated-files.md",
      "confidence": "high",
      "symbols": ["*.g.dart", "*.freezed.dart"],
      "files": ["docs/generated-files.md"]
    }
  ],
  "suggested_checks": ["Run the task public tests after editing."],
  "warnings": [],
  "source_summary": [
    {"path": "docs/generated-files.md", "kind": "project_doc"}
  ],
  "token_estimate": 180
}
```

## Why this is not a Context7 clone

Context7 answers:

```text
How do I use API X?
```

DocAtlas should answer:

```text
In this repository, what constraints must this patch satisfy?
```

Context7 is library/API usage oriented. DocAtlas is repository-contract oriented. It combines project docs, source excerpts, manifests, lockfiles, dependency docs, and benchmark-visible constraints into a source-attributed packet tailored to a patch.

## Claims guardrail

### Can claim now

- DocAtlas can ingest and retrieve project/dependency documentation with source attribution.
- Task-level benchmark artifacts show DocAtlas adoption/context-use in DocAtlas conditions.
- Existing cost/accuracy analysis currently reports `QUALITY_POSITIVE_COSTLY`: limited quality/policy-clean positive signal, higher token/time cost, low confidence.
- Action-checklist style presentation is the most promising observed workflow direction.

### Cannot claim now

- DocAtlas is broadly better than repo-only coding-agent prompting.
- DocAtlas improves patch success across repositories or tasks in general.
- DocAtlas is token-efficient or time-efficient versus repo-only on the current artifacts.
- Vector retrieval success is equivalent to fallback-local-project-context success.
- Current evidence is statistically strong.

### Can claim after stronger benchmark

Only after a larger, fair, policy-clean benchmark with accepted differentiating tasks can DocAtlas claim stronger product value, such as:

- patch constraints improve resolved or hidden-pass rate versus repo-only;
- patch constraints reduce policy violations without lowering quality;
- patch constraints improve correct-layer edits or generated-file compliance;
- token overhead stays within a defined budget;
- retrieval success and fallback success are reported separately.

## Benchmark implications

Near-term work should stay in the benchmark/eval layer before production MCP APIs:

1. add telemetry that separates retrieval success, fallback success, workflow success, and context/checklist token cost;
2. prototype patch constraint packets from visible evidence only;
3. add a `docatlas_patch_constraints_injected` condition;
4. add deterministic post-patch constraint validation;
5. rerun cost/accuracy analysis on existing artifacts before expensive new runs;
6. run a small targeted smoke pilot only after telemetry and validation exist.

## Production freeze

This RFC does not request a broad production rewrite. The next production PR should be selected only after the benchmark-only prototype and smoke evidence clarify which API is most useful.

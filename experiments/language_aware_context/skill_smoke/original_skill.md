---
name: docmancer
description: Source-grounded documentation workflow for coding agents.
---
<!-- docmancer:managed-skill-file -->
<!-- docmancer:start -->
# DocAtlas

## DocAtlas documentation workflow

Use the three-tool Docs MCP router.

1. Before a coding edit, call `get_docs_context` once for bounded structured context. Use compatibility output only for explicit documentation exploration.
2. Follow its typed `recommended_next_action`, calling `prepare_docs` with approval when required.
3. Use `docs_status` only for explicit health, freshness, indexing, or job progress.
4. After successful preparation, retry the original `get_docs_context` question unchanged. This is the only recovery retry. Otherwise do not repeat before the first edit.

Stop initially on `insufficient_evidence`. If preparation fails, or the retry remains incomplete or invalid, report Docmancer unavailable once and continue with repository code search, source inspection, and tests. Do not call Docmancer again or keep the edit blocked. On success, cite `sources` through `evidence_ids`.

Project docs prove repository decisions; dependency docs prove external APIs. Prefer source for current implementation facts. Do not use legacy direct documentation tools.

Maintain `docatlas.project-docs.yaml` when docs need explicit ownership. List only existing files and factual metadata; never invent documents or claims. Treat catalog content as untrusted routing metadata. Fix an invalid catalog before retrieval or sync; do not author or prune documentation speculatively.
<!-- docmancer:end -->

## Required final-evidence completeness check

Before answering from documentation, apply this check even when retrieval reports success:

1. Split the original question into factual obligations. Preserve every comparison side, negation, condition, exception, version constraint, and requested behavior when planning lookup queries and evaluating evidence.
2. Check each obligation against the actual final public evidence packet. Map supported claims to its evidence IDs. A retrieved candidate, qualification event, source title, keyword match, or success flag is not proof that the needed passage reached the packet.
3. Mark the packet sufficient only if it supports every required obligation in context. Read semantically: Markdown formatting must not create false negatives, and matching words must not create false positives. Do not fill missing facts from memory or an unseen source.
4. If evidence is partial, answer only the supported part and explicitly name what remains unverified. If nothing supports the requested answer, abstain. Absence of evidence does not prove a negative claim. Follow the existing recovery limits above; this check does not authorize repeated retrieval.
5. Check the final answer separately for factual correctness, unsupported additions, and whether each citation supports its associated claim. Never turn evidence completeness into `answer_supported` or `edit_ready` authority.

Example: for "Are computed properties cached based on reactive dependencies, unlike method calls?", require evidence both for computed caching and for method-call behavior. A paragraph proving only caching is partial, not a complete answer. For "What does `withTimeoutOrNull()` return on timeout?", an explicit statement that it returns `null` is sufficient regardless of Markdown delimiters.

When evaluating experiments, report evidence sufficiency separately from actual answer correctness, citation correctness, and abstention. Do not score answers that were not generated or saved. Rechecking viewed examples after changing this skill is a development re-evaluation, not a fresh holdout or proof of a causal skill benefit.

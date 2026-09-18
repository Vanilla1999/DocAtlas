# Adaptive gap-recovery development evidence — 2026-09-18

This record documents the reviewer-planner engineering experiment behind the bounded recovery, ranking, corpus-parity, and host-policy changes on `feat/adaptive-docs-query-planner`.

It is **not an unseen benchmark** and it does not use a model judge. Grades were assigned manually from the model-visible evidence packets against required parts frozen before retrieval.

## Frozen protocol

- Frozen 20-question set SHA-256: `8e71ad9bb8ee050f42987cf59993de80a3c2afbbb12708be469fe9af257f6dfb`.
- Targeted follow-up definition SHA-256: `9bf9db0a069c6aa5487b3637d575d192fe9c919fb81d962ebda205cb1e056251`.
- First-packet comparison uses the same corpus and normal bounded packet limits.
- Task-level recovery uses an **experimental** ceiling of 2,000 admission tokens across all evidence responses; this is not a new runtime task budget.
- `Full` means the model-visible evidence covers the frozen required parts. It does not require `context_quality=checked`.

## First-packet results

| Arm | Full | Partial | Insufficient | Calls | Admission tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original question only | **5** | **8** | **7** | 20 | 12,672 |
| Same question + frozen answer-blind lookups | **7** | **9** | **4** | 20 | 14,233 |

Average admission cost rose from 633.6 to 711.6 tokens. Blind lookup improves some retrieval cases, but it is neither free nor a monotonic improvement.

## Root-first + concrete-gap recovery

The final reviewer-planner policy produced **13 Full / 4 Partial / 3 Insufficient** over the same 20 root questions.

- total admission tokens: **21,958**;
- average per task: **1,097.9**;
- median: **1,012**;
- maximum: **1,758**;
- total evidence calls: **35** (`1.75` calls/task);
- every trajectory stayed below the experimental 2,000-token ceiling.

Approximate measured latency was 2.622 s average, 1.93 s median, and 11.149 s maximum in the development environment.

## Why the policy is root-first rather than pre-split

Pre-splitting merely because a question is compound or comparative is too aggressive.

- V16 was already Full from one root call at about 709 admission tokens; the preselected split consumed about 1,597 tokens without improving sufficiency.
- V05 was also already Full from one root call; splitting it can perturb a good bounded packet.

The maintained host policy therefore starts with one bounded root/original call. A second action is justified only by a **concrete missing requested fact**:

1. use an already-issued bounded source read when the source is known;
2. otherwise use one targeted same-need query;
3. use a dependent split only after the actual gap is known;
4. stop on sufficient evidence or no progress.

`context_quality=unverified` by itself does not require another read.

## Delivered changes

1. **Witness-targeted `read_next`.** When a missing mandatory component already has a verified source-bound assignment with valid offsets, recovery targets the exact witness range before generic continuation heuristics.
2. **No empty/redundant continuation.** Generic continuation is not advertised when the candidate range adds no meaningful source text beyond the visible span.
3. **Public-path verification.** The range is registered without source I/O, remains bounded, and `SourceReadController` reads the exact missing witness only when requested.
4. **Self-host corpus parity.** The canonical `SKILL.md` is declared in `docatlas.project-docs.yaml`, so the public project-doc path can retrieve the maintained agent workflow without another generated source of truth.
5. **Same-call capture.** Eval-only capture preserves the full request, retrieval/projection trace, public payload, strategy identity, timing, and actual admission-token cost without changing production behavior.
6. **Gap-directed ranking.** For safe positive action-shaped questions, a qualified procedural/action witness can outrank relation-only descriptive context. Negation and unrelated relation cases remain fail-closed; no expected action or source name is hard-coded.
7. **Root-first host contract.** Lookups, source reads, and splits are recovery tools for concrete gaps rather than mandatory preprocessing for every complex question.

## Residual gaps

V13, V15, and V17 remain Insufficient in the frozen task-level run. The needed knowledge exists in the corpus, but it does **not** enter `context_pack`; the first demonstrated loss is therefore retrieval/candidate generation, not final packing. V18, V19, and V20 remain Partial.

These residuals are intentionally not patched in this change. They require a separate retrieval-layer RED that traces query → candidate generation → qualification before production behavior is changed.

## Preserved boundaries

- Public MCP tools remain `get_docs_context`, `prepare_docs`, and `docs_status`.
- No runtime LLM, evaluator, reranker, embedding dependency, translation model, or new public tool was added.
- `context_quality=unverified` remains conservative rather than being weakened to inflate `checked` counts.
- Existing token/source caps, snapshot binding, project identity, version/freshness/authority checks, and edit authorization remain unchanged.
- No global token/window expansion or benchmark-ID-specific runtime branch was added.

## Interpretation

The development evidence supports **root-first, gap-directed recovery**, not a universal query-rewrite or split policy. The cheapest reliable gains came from preserving evidence lineage, reading the exact known missing witness, exposing the canonical workflow to the same retrieval surface, and preferring a qualified procedural witness only when the user question itself requests an action.

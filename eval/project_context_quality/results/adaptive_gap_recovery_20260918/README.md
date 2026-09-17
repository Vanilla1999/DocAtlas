# Adaptive gap-recovery development evidence — 2026-09-18

This record documents the engineering experiment behind the bounded recovery and host-policy changes on `feat/adaptive-docs-query-planner`.

It is **not an unseen benchmark** and it does not use a model judge. Grades were assigned manually from the model-visible `sources[].snippet` evidence. The original frozen-question file was accidentally overwritten after the first-packet run; the executed N01–N20 questions, preselected strategies, lookup strings, and split subquestions were recovered from the already-written first-packet raw capture. Therefore this experiment is evidence for development decisions, not a clean independent evaluation claim.

## Final manually reviewed counts

| Arm | Full | Partial | Insufficient | Calls | Admission tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original question only | 6 | 8 | 6 | 20 | 12,157 |
| Preselected `single / lookup / split` strategy | 7 | 11 | 2 | 22 | 15,800 |
| Same strategy + bounded concrete-gap recovery | 11 | 7 | 2 | 34 | 24,420 |

Maximum final evidence cost for one task was 1,830 admission tokens; no task crossed the experimental 2,000-token task ceiling.

The important result is not merely the higher `full` count. Recovery is expensive: automatically following every `unverified` result would roughly double evidence traffic without guaranteeing sufficiency. The host policy must therefore follow up only for a **concrete missing requested fact**, stop on sufficient evidence or no progress, and prefer an already-issued bounded source read when the source is known.

## Task 5: why no generic PACK patch was made

The source-continuation development case reproduced a post-retrieval selection gap:

- both relevant adjacent source fragments were present in the same `context_pack`;
- a manually composed valid public DTO containing both relevant fragments fit in about 567 admission tokens, below the 800-token packet budget;
- the second fragment was nevertheless not selected;
- the query plan did not contain a mandatory component contract for the missing fact, so the projector could not safely distinguish the second fragment from another same-query supporting fragment.

This is **not sufficient evidence for a global “merge neighboring chunks” rule**. Previous broad-window experiments produced regressions, and a structural-neighbor rule without a semantic obligation can promote unrelated material. The plan therefore stops at diagnosis for this case instead of adding benchmark-specific or global packing behavior.

## Delivered changes justified by stronger evidence

1. **Witness-targeted `read_next`.** When a missing mandatory component already has a verified source-bound assignment with valid offsets, the recovery capability targets that exact source range before falling back to generic continuation heuristics.
2. **Public-path verification.** The emitted range is registered without source I/O, survives the public payload budget, and `SourceReadController` reads the exact missing witness only when explicitly requested.
3. **Self-host corpus parity.** The existing canonical `SKILL.md` is declared in `docatlas.project-docs.yaml`, allowing the public project-doc path to retrieve the maintained agent workflow without adding another generated source of truth.
4. **Same-call capture.** Eval-only capture preserves the full request, retrieval/projection trace, public payload, strategy identity, and actual admission-token cost without changing production behavior.
5. **Gap-directed host contract.** Same-need vocabulary mismatch uses narrow lookups; independently answerable requested parts use separate bounded calls; a concrete missing fact uses a known issued source range first or one targeted same-need query when the source is unknown. `context_quality=unverified` alone does not require another read.

## Preserved boundaries

- Public MCP tools remain `get_docs_context`, `prepare_docs`, and `docs_status`.
- No runtime LLM, evaluator, reranker, embedding dependency, translation model, or new public tool was added.
- `context_quality=unverified` remains conservative rather than being weakened to increase `checked` counts.
- Existing token/source caps, snapshot binding, project identity, version/freshness/authority checks, and edit authorization remain unchanged.
- No generic PACK/projection rule was added without a failing production invariant that identifies a safe first-loss boundary.

## Interpretation

The current evidence supports an **adaptive recovery policy**, not a universal query-rewrite or split policy. Search reformulation helps some vocabulary/cross-language cases, while split calls help some independently answerable compound requests, but both add cost and can perturb bounded selection. The cheapest reliable improvement found in this iteration is to exploit already-verified evidence lineage when the exact missing fact is known, then use one targeted same-need query only when that source is not known.

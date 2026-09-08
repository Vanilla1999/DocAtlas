# Context-first project reads finalization checkpoint

Branch: `fix/context-first-project-reads-finalization`

Start commit inherited from prior diagnostic branch: `d216f6f83671f22de3f79c58a46418e26d7c5f19`.

Last confirmed full-green runtime before the diagnostic commits: `01f7b43afb00ead4a151099b9b11c0a27b94eafe`.

Confirmed validation at that runtime:
- full suite: 3937 passed, 10 skipped;
- frozen project-context audit: 12/15 natural, 3/5 exposed;
- false-full: 0;
- public project context remains bounded to at most 3 sources / 800 estimated tokens;
- project reads do not authorize answers or edits.

Inherited diagnostic progress:
- RED regression for architecture infrastructure-boundary recall is committed;
- RED regression for request-flow public selection is committed;
- raw dispatcher trace proved that the architecture infrastructure witness is retrievable;
- raw dispatcher trace proved that request-flow MCP/application/gateway/selection sections are retrievable before public projection;
- experimental routing hypotheses in transient workflow were not committed to production runtime because targeted GREEN was not established.

Latest closure on PR #179:
- request-flow lineage is GREEN: 7/7 targeted tests;
- the frozen request-flow case visibly carries MCP boundary, application orchestration, retrieval gateway, and selection policy within the existing 3-source / 800-token limit;
- project-context quality v2 live evaluation completed on the published request-flow slice; it is REPORT_ONLY, not a passing release/quality gate;
- neighboring model-visible projection, ranking, context, and service contracts are GREEN;
- `docs_context_projection.py` is back within the repository 1000-line module budget after formatting-only cleanup;
- temporary request-flow and size-validation Actions workflows/scripts were removed after their validated production commits;
- public answer/edit authorization remains denied and source provenance fields remain unchanged.

Finalization rules:
1. Work one proven loss at a time: source truth -> raw retrieval -> qualification/lineage -> final visible source.
2. Change only the layer where the loss is demonstrated.
3. Keep DDD small: domain owns intent/lineage/qualification, application owns selection/projection, infrastructure owns candidate retrieval, MCP/host owns scope and request parameters.
4. Do not lower qualification thresholds, hard-code benchmark questions, add a general semantic verifier, or widen scope after a miss.
5. Do not modify frozen evaluator/corpus/protocol or thresholds to make a gate green.
6. Keep original question, exact identifiers, negation, source identity, and selected scope unchanged.
7. No production implementation commit without RED -> targeted GREEN -> neighboring contracts; before acceptance run full pytest, compileall, diff check, frozen 15+5, newcomer 30, and review.
8. Commit each completed slice so progress cannot be lost.

Planned slices:
1. architecture evidence routing;
2. request-flow lineage/selection;
3. sync-renames compound witness retention;
4. contributor review-ready facets;
5. classify search-trust as runtime defect vs frozen evaluator witness limitation;
6. frozen 15+5 acceptance;
7. newcomer 30 first-pass with host-planned scope;
8. generalized newcomer retrieval fixes;
9. final review/acceptance.

# T07 real-P ratio call-site separation

Extended the existing AST-checked ratio remove-one hook with explicit modes:
`all`, `tagging`, `final`. The latter two match reviewed source-file/function
call sites, not arbitrary function names: `reference_query_tagging._tag_retrieval_query`
and `_docs_context_projection_core._requalify_visible_source`. Other callers keep
the original ratio comparison. Unknown modes refuse execution; exception/lazy
alias restoration is unchanged. Missing parent exact retains original ratio.
No exact/reference/version/stale/unsafe or authorization guard is removed.

Each intercepted call records its site, whether the intervention applied, and
the original-versus-changed qualification on identical arguments. This doubles
pure qualification work for observation; no latency/performance claims follow.
The original P control never installs the hook.

Ran the original 28 real development questions, P/P_MINUS_RATIO, three modes:
**168/168 executed, 168 audit-clean**, one execution per arm/case/mode.
Panels ran independently in separate ordinary processes; same controlled fixture
root within/across phases, fresh indexes, no OS isolation. All 28 baseline P DTOs
are exactly equal across phases. No repeat-stability claim for these single-repeat
phase experiments; previous all-mode repetitions remain separate historical data.

| Intervention mode | Changed public payloads | Changed visible source text/path sets |
|---|---:|---:|
| All reached sites | 21/28 | 15/28 |
| Tagging only | 5/28 | 3/28 |
| Final requalification only | 17/28 | 11/28 |

Qualification gains by site across both panels (calls, not independent questions):

| Mode | Tagging gains | Final gains | Condition-ranking gains |
|---|---:|---:|---:|
| All | 454 | 1801 | 60 |
| Tagging | 454 | 0 | 0 |
| Final | 0 | 972 | 0 |

Call counts differ downstream because changed admission/coverage alters the path;
these columns do not constitute additive isolated component contributions.
Final requalification participates throughout projection, not only after final
DTO assembly. `tagging` is the reviewed discovery-attribution call site, not a
claim that it contains every possible admission decision in P.

Cloud-backup unsupported continuation context (four-doc case 8) appears in all-mode,
not tagging-only or final-only. This does not prove general selectivity safety.
README case 9 and four-doc case 8 show why payload metadata changes must not be
counted as recovered evidence: source text remains empty in some phase comparisons.
No refreshed semantic sufficiency counts, generated answers, citation quality or
independent holdout claim. Product ratio behavior stays unchanged.

Tests retain stale/unsafe/foreign-project, exact/bound subject/parent exact,
nonempty body and exception restoration controls; unrecognized direct caller
chains keep original behavior in phase-only modes. **176 focused/adjacent tests
passed** after this instrumentation.

Artifacts: `/tmp/opencode/ablation-p-ratio-{all,tagging,final}-{readme,four-docs}/`,
`/tmp/opencode/ablation-p-ratio-phase-summary.json`,
`/tmp/opencode/ablation-p-ratio-phase-tests.log`.

**Completed T07 deliverable:** measured real-P ratio intervention separately at
tagging and requalification call sites. Other original add/remove-one components,
full legacy projection/packing package and independent semantic evaluation remain
open; this is not full T07 acceptance or a removal recommendation.

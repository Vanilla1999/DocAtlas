# T06 saved-pool assembly deliverable

Implemented `saved_pool.py`: persist the complete **exposed B ranked pool**,
source corpus, query lanes/order, filters and a backed-up SQLite snapshot.
Replay opens the snapshot read-only, recomputes canonical/hard-policy eligibility,
revalidates every candidate against its indexed bytes and metadata, reconstructs
the entire capped ranked pool from saved lanes, and repeats actual reference
admission. No stored qualified flag supplies authority. Source-bound CommonMark
parsing is enabled consistently for the saved structural B representation.

Then reproduce the saved B DTO exactly or refuse replay, and run existing bounded
D_L assembly on that same order. SQL authorizer denies bm25/MATCH; replay invokes
no query planner, ingestion or `_search_rows`. Snapshot hashes are verified before
opening; hashes are unsigned integrity checks, not adversarial authorization.
The current product hard-policy gates remain authoritative on replay.

Tests cover B reproduction, repeated D identity, forbidden retrieval, unchanged
snapshot bytes, changed payloads even after recomputing their unsigned hashes,
oversized units, DTO budget and source-owner boundaries. Native SQL search exposes
hydration_id as `id`; replay compares hydration identity and all evidence fields,
not that physical SQLite row-id alias.

Measured **34 saved case snapshots / 339 candidates / 68 B+D replays**, each replay
performed twice. All B packets equal their captured control; all D packets equal
the earlier same-root D_L run and their repeat. **Zero new searches**, audit-clean,
maximum D DTO **796 tokens**. Four-doc case 6 reproduces the source_changed
evidence's `whole_child_exceeds_dto_budget` omission from the saved snapshot.
No posthoc packing optimization was introduced to make that case pass.

Final implementation holds one read transaction and verifies artifact hashes
again before returning. Repeated all 68 snapshot replays after that refinement:
identical B/D packets, no searches. Harness plus adjacent product suites:
**174 passed** before the two additional HTML provenance tests.

CLI: `python -m experiments.retrieval_ablation.saved_pool BUNDLE_DIR`.

Artifacts: `/tmp/opencode/ablation-saved-pool-measure/` (each case's snapshot,
manifest, complete pool and replay), `summary.json` therein, driver
`/tmp/opencode/ablation-saved-pool-measure.py`, log
`/tmp/opencode/ablation-saved-pool-measure.log`.

**T06 native-project deliverable COMPLETE:** standalone saved-pool replay,
bounded existing owner-local closure, identical B control, zero retrieval,
budget/oversized and ownership controls, and reproduced budget-loss diagnosis.
This does not claim uncapped retrieval completeness, HTML/RST coverage, independent
semantic evaluation, or a product assembly activation decision. The original
full scope remains constrained by T05 format/ownership and project-only adapter.

Next stage is T05's missing source-format/ownership deliverable, not more T06
diagnostic infrastructure. T07 heading-phase observations are already documented
separately; remaining real-P remove-one and semantic evaluation are still open.

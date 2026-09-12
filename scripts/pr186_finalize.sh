#!/usr/bin/env bash
set -euo pipefail

cat > tests/docs/test_docs_context_budget_reserve.py <<'PY'
from __future__ import annotations

import math

from docmancer.docs.application.model_visible_projection import (
    canonical_projection_bytes,
    docs_context_budget_tokens,
    estimate_projection_tokens,
)


def test_docs_context_budget_reserves_for_structured_token_density() -> None:
    payload = {
        "status": "ok",
        "kind": "docs_context",
        "answer_policy": "cite_only",
        "answer_supported": False,
        "answer_available": False,
        "edit_ready": False,
        "sources": [
            {
                "evidence_id": "ev-a",
                "path_or_url": "docs/reference/configuration.md",
                "section": "Configuration / strict-mode",
                "snippet": (
                    "`strict-mode=true` preserves source-bound behavior; "
                    "use `worker.pool.size=4`, `retry.max=3`, and avoid "
                    "assuming hidden defaults from a different version."
                ),
                "version_binding": "current",
                "content_sha256": "a" * 64,
                "project_identity": "project:test",
                "line_start": 10,
                "line_end": 14,
                "authority": "source_of_truth",
                "scope": "project",
            }
        ],
        "estimated_tokens": 0,
    }
    serialized_bytes = len(canonical_projection_bytes(payload))

    # Keep the public engineering estimate backward-compatible.
    assert estimate_projection_tokens(payload) == math.ceil(serialized_bytes / 4)
    # Admission for docs_context is deliberately more conservative.
    assert docs_context_budget_tokens(payload) >= math.ceil(serialized_bytes / 3)
    assert docs_context_budget_tokens(payload) > estimate_projection_tokens(payload)


def test_non_context_projection_keeps_existing_byte_estimator_contract() -> None:
    payload = {"status": "ok", "kind": "docs_answer", "answer": "plain text"}
    serialized_bytes = len(canonical_projection_bytes(payload))

    assert estimate_projection_tokens(payload) == math.ceil(serialized_bytes / 4)
PY
if python -m pytest -q tests/docs/test_docs_context_budget_reserve.py; then
  echo 'docs-context admission reserve unexpectedly GREEN before production helper exists' >&2
  exit 1
fi
echo 'Separated admission-budget contract reproduced RED.'


python - <<'PY'
from pathlib import Path

projection = Path('docmancer/docs/application/model_visible_projection.py')
text = projection.read_text(encoding='utf-8')
estimator = '''def estimate_projection_tokens(value: Any) -> int:\n    size = len(canonical_projection_bytes(value))\n    return max(1, math.ceil(size / 4))\n'''
if text.count(estimator) != 1:
    raise SystemExit('public projection estimator anchor changed')
helper = estimator + '''\n\ndef docs_context_budget_tokens(value: Any) -> int:\n    """Conservative provider-free admission reserve for docs_context payloads.\n\n    ``estimated_tokens`` remains the stable public engineering estimate. This\n    reserve is intentionally separate so structured JSON-heavy context is\n    trimmed before it can exceed the hard model-input envelope.\n    """\n\n    size = len(canonical_projection_bytes(value))\n    return max(1, math.ceil(size / 3))\n'''
text = text.replace(estimator, helper, 1)
validation = '''    actual = estimate_projection_tokens(payload)\n    if payload.get("estimated_tokens") != actual or actual > limit:\n        errors.append("projection estimate mismatch or budget exceeded")\n'''
if text.count(validation) != 1:
    raise SystemExit('projection validator anchor changed')
validation_new = validation + '''    if (\n        kind == "docs_context"\n        and status in {"ok", "truncated"}\n        and docs_context_budget_tokens(payload) > max_tokens\n    ):\n        errors.append("docs_context conservative budget exceeded")\n'''
text = text.replace(validation, validation_new, 1)
projection.write_text(text, encoding='utf-8')

docs_context = Path('docmancer/docs/application/docs_context_projection.py')
text = docs_context.read_text(encoding='utf-8')
if text.count('estimate_projection_tokens(') != 4:
    raise SystemExit('docs-context admission call inventory changed')
if text.count('    estimate_projection_tokens,\n') != 1:
    raise SystemExit('docs-context budget import anchor changed')
text = text.replace('    estimate_projection_tokens,\n', '    docs_context_budget_tokens,\n', 1)
text = text.replace('estimate_projection_tokens(', 'docs_context_budget_tokens(')
docs_context.write_text(text, encoding='utf-8')

active = Path('docmancer/core/_sqlite_store_active_fts.py')
text = active.read_text(encoding='utf-8')
text = text.replace('import json\n', '', 1)
start = text.find('    def fetch_section_filter_metadata(')
end = text.find('    def _ensure_schema(self) -> None:', start)
if start < 0 or end < 0:
    raise SystemExit('active-FTS duplicate metadata boundary not found')
active.write_text(text[:start] + text[end:], encoding='utf-8')

store = Path('docmancer/core/sqlite_store.py')
text = store.read_text(encoding='utf-8')
if 'from ._sqlite_store_filter_metadata import _SQLiteStoreFilterMetadata' not in text:
    text = text.replace(
        'from ._sqlite_store_active_fts import _SQLiteStoreActiveFTS\n',
        'from ._sqlite_store_active_fts import _SQLiteStoreActiveFTS\nfrom ._sqlite_store_filter_metadata import _SQLiteStoreFilterMetadata\n',
        1,
    )
old_class = 'class SQLiteStore(_SQLiteStoreActiveFTS, _SQLiteStorePart01,'
new_class = 'class SQLiteStore(_SQLiteStoreActiveFTS, _SQLiteStoreFilterMetadata, _SQLiteStorePart01,'
if old_class not in text and new_class not in text:
    raise SystemExit('SQLiteStore inheritance anchor changed')
text = text.replace(old_class, new_class, 1)
bridge_old = "'docmancer.core._sqlite_store_shared', 'docmancer.core._sqlite_store_active_fts', 'docmancer.core._sqlite_store_part01'"
bridge_new = "'docmancer.core._sqlite_store_shared', 'docmancer.core._sqlite_store_active_fts', 'docmancer.core._sqlite_store_filter_metadata', 'docmancer.core._sqlite_store_part01'"
if bridge_old not in text and bridge_new not in text:
    raise SystemExit('SQLiteStore shard bridge anchor changed')
text = text.replace(bridge_old, bridge_new, 1)
store.write_text(text, encoding='utf-8')

dispatch = Path('docmancer/retrieval/_dispatch_part02.py')
text = dispatch.read_text(encoding='utf-8')
start = text.find('    def _filter_section_ids_before_hydration(')
end = text.find('    def _hydrate_policy_filtered(', start)
if start < 0 or end < 0:
    raise SystemExit('dispatcher pre-hydration boundary not found')
replacement = '''    def _filter_section_ids_before_hydration(\n        self, section_ids: list[int], filters: dict | None,\n    ) -> list[int]:\n        if not section_ids or not filters:\n            return section_ids\n        metadata_for = getattr(self.store, "section_filter_metadata_for", None)\n        if not callable(metadata_for):\n            # Compatibility stores still retain the post-hydration policy check.\n            return section_ids\n        try:\n            metadata_by_id = metadata_for(section_ids)\n        except Exception as exc:\n            logger.warning(\n                "pre-hydration source-policy metadata failed (%s)",\n                type(exc).__name__,\n            )\n            return []\n        return [\n            section_id\n            for section_id in section_ids\n            if (metadata := metadata_by_id.get(int(section_id))) is not None\n            and metadata_matches_filters(\n                metadata, filters, source=str(metadata.get("source") or ""),\n            )\n        ]\n\n'''
dispatch.write_text(text[:start] + replacement + text[end:], encoding='utf-8')
PY
rm -f tests/test_prehydration_policy.py tests/diagnostic_labels.prehydration_policy.json
git diff --check


python - <<'PY'
from pathlib import Path

path = Path('scripts/run_systemic_retrieval_plan_gate.py')
text = path.read_text(encoding='utf-8')
if 'def _candidate_pool_fingerprint(' not in text:
    raise SystemExit('semantic candidate-pool fingerprint is missing')

old = '''    output = work / name\n    shutil.rmtree(output, ignore_errors=True)\n    lane_protocol = _single_variant_protocol(protocol)\n    started_cpu = time.process_time()\n    started_wall = time.perf_counter()\n    with ExitStack() as stack:\n        stack.enter_context(patch.object(evidence, "load_protocol", return_value=(lane_protocol, deepcopy(cases), deepcopy(manifest))))\n        if cap == "off":\n            stack.enter_context(patch.object(RetrievalDispatcher, "_limit_sections_per_source", _no_source_cap))\n        elif cap == "strict":\n            stack.enter_context(patch.object(RetrievalDispatcher, "_limit_sections_per_source", _strict_source_cap))\n        elif cap != "bounded":\n            raise ValueError(f"unknown cap mode: {cap}")\n'''
new = '''    output = work / name\n    shutil.rmtree(output, ignore_errors=True)\n    lane_protocol = _single_variant_protocol(protocol)\n    cap_inputs: list[str] = []\n    original_cap = RetrievalDispatcher._limit_sections_per_source\n\n    def observed_cap(self: Any, chunks: list[Any], *, limit: int | None = None, expand: str | None = None) -> list[Any]:\n        cap_inputs.append(_candidate_pool_fingerprint(chunks))\n        if cap == "off":\n            return _no_source_cap(self, chunks, limit=limit, expand=expand)\n        if cap == "strict":\n            return _strict_source_cap(self, chunks, limit=limit, expand=expand)\n        if cap == "bounded":\n            return original_cap(self, chunks, limit=limit, expand=expand)\n        raise ValueError(f"unknown cap mode: {cap}")\n\n    started_cpu = time.process_time()\n    started_wall = time.perf_counter()\n    with ExitStack() as stack:\n        stack.enter_context(patch.object(evidence, "load_protocol", return_value=(lane_protocol, deepcopy(cases), deepcopy(manifest))))\n        stack.enter_context(patch.object(RetrievalDispatcher, "_limit_sections_per_source", observed_cap))\n'''
if text.count(old) != 1:
    raise SystemExit('run-lane cap patch anchor changed')
text = text.replace(old, new, 1)

old = '''    return {"name": name, "output": output, "summary": summary, "metrics": metrics, "rows": rows}\n'''
new = '''    return {"name": name, "output": output, "summary": summary, "metrics": metrics, "rows": rows, "cap_inputs": cap_inputs}\n'''
if text.count(old) != 1:
    raise SystemExit('run-lane return anchor changed')
text = text.replace(old, new, 1)

old = '''    exact_recoveries: list[str] = []\n    beam_recoveries: list[str] = []\n'''
new = '''    exact_recoveries: list[str] = []\n    simple_recoveries: list[str] = []\n    beam_recoveries: list[str] = []\n'''
if text.count(old) != 1:
    raise SystemExit('selection recovery list anchor changed')
text = text.replace(old, new, 1)

old = '''        exact = min(exact_candidates, key=lambda item: (item["tokens"], item["sources"], item["indices"]), default=None)\n\n        beam_states: list[tuple[int, ...]] = [()]\n'''
new = '''        exact = min(exact_candidates, key=lambda item: (item["tokens"], item["sources"], item["indices"]), default=None)\n\n        simple_success: dict[str, Any] | None = None\n        for size in range(1, min(SELECTION_PACKAGE_LIMIT, len(pool)) + 1):\n            candidate = project(tuple(range(size)))\n            if candidate["sufficient"]:\n                simple_success = candidate\n                break\n\n        beam_states: list[tuple[int, ...]] = [()]\n'''
if text.count(old) != 1:
    raise SystemExit('simple selector insertion anchor changed')
text = text.replace(old, new, 1)

old = '''        if exact is not None:\n            exact_recoveries.append(case_id)\n        if beam_success is not None:\n            beam_recoveries.append(case_id)\n        results.append({"id": case_id, "current_sufficient": False, "pool": _candidate_structure(pool), "exact_recovery": exact, "beam_recovery": beam_success, "enumerated_packages": len(cache)})\n'''
new = '''        if exact is not None:\n            exact_recoveries.append(case_id)\n        if simple_success is not None:\n            simple_recoveries.append(case_id)\n        if beam_success is not None:\n            beam_recoveries.append(case_id)\n        results.append({"id": case_id, "current_sufficient": False, "pool": _candidate_structure(pool), "exact_recovery": exact, "simple_recovery": simple_success, "beam_recovery": beam_success, "enumerated_packages": len(cache)})\n'''
if text.count(old) != 1:
    raise SystemExit('selection result anchor changed')
text = text.replace(old, new, 1)

old = '''        "exact_recoveries": exact_recoveries,\n        "beam_recoveries": beam_recoveries,\n        "proxy_exact_gap": sorted(set(exact_recoveries) - set(beam_recoveries)),\n'''
new = '''        "exact_recoveries": exact_recoveries,\n        "simple_recoveries": simple_recoveries,\n        "beam_recoveries": beam_recoveries,\n        "exact_simple_gap": sorted(set(exact_recoveries) - set(simple_recoveries)),\n        "proxy_exact_gap": sorted(set(exact_recoveries) - set(beam_recoveries)),\n'''
if text.count(old) != 1:
    raise SystemExit('selection summary anchor changed')
text = text.replace(old, new, 1)

old = '''    current = lanes["cap_on_requal_on"]\n    paired = {name: _paired(current["rows"], lane["rows"], seed=seed, resamples=resamples) for name, lane in lanes.items() if name != "cap_on_requal_on"}\n'''
new = '''    current = lanes["cap_on_requal_on"]\n    fixed_pool = {\n        name: {\n            "calls": len(lane["cap_inputs"]),\n            "same_as_current": Counter(lane["cap_inputs"]) == Counter(current["cap_inputs"]),\n            "ordered_same_as_current": lane["cap_inputs"] == current["cap_inputs"],\n        }\n        for name, lane in lanes.items()\n    }\n    paired = {name: _paired(current["rows"], lane["rows"], seed=seed, resamples=resamples) for name, lane in lanes.items() if name != "cap_on_requal_on"}\n'''
if text.count(old) != 1:
    raise SystemExit('fixed-pool comparison anchor changed')
text = text.replace(old, new, 1)

old = '''    full80_valid_rows = [row for row in full80["rows"] if "error" not in row]\n    full80_max_tokens = max((int(row.get("size", {}).get("actual_tokens") or 0) for row in full80_valid_rows), default=0)\n'''
new = '''    full80_valid_rows = [row for row in full80["rows"] if "error" not in row]\n    full80_budget_rows = [row for row in full80_valid_rows if row.get("answerability") == "within_budget"]\n    full80_budget_max_tokens = max((int(row.get("size", {}).get("actual_tokens") or 0) for row in full80_budget_rows), default=0)\n    full80_all_valid_max_tokens = max((int(row.get("size", {}).get("actual_tokens") or 0) for row in full80_valid_rows), default=0)\n'''
if text.count(old) != 1:
    raise SystemExit('DTO budget scope anchor changed')
text = text.replace(old, new, 1)

text = text.replace(
    '            "contextualization_control": "same end-to-end call with final snippet expansion disabled",\n',
    '            "contextualization_control": "same end-to-end call with final snippet expansion disabled",\n            "performance_metrics_frozen": ["process_cpu_seconds", "cpu_seconds_per_case", "latency_seconds.p95"],\n',
    1,
)
old = '''            "max_actual_model_visible_tokens": full80_max_tokens,\n            "actual_full_dto_budget": full80_max_tokens <= MAX_TOKENS,\n'''
new = '''            "within_budget_max_actual_model_visible_tokens": full80_budget_max_tokens,\n            "all_valid_max_actual_model_visible_tokens_diagnostic": full80_all_valid_max_tokens,\n            "actual_full_dto_budget": full80_budget_max_tokens <= MAX_TOKENS,\n'''
if text.count(old) != 1:
    raise SystemExit('report DTO budget anchor changed')
text = text.replace(old, new, 1)
old = '''        "causal_2x2": {"cells": cells, "paired_against_current": paired, "difference_in_differences_success_rate": interaction, "interpretation": "Counterfactual diagnostic only; no causal claim extends beyond this fixed exposed corpus."},\n'''
new = '''        "causal_2x2": {"cells": cells, "paired_against_current": paired, "fixed_pre_cap_candidate_pool": fixed_pool, "difference_in_differences_success_rate": interaction, "interpretation": "Counterfactual diagnostic only; no causal claim extends beyond this fixed exposed corpus."},\n'''
if text.count(old) != 1:
    raise SystemExit('causal report anchor changed')
text = text.replace(old, new, 1)
old = '''    if full80_max_tokens > MAX_TOKENS:\n        failures.append("full model-visible DTO exceeded the 800-token ceiling")\n'''
new = '''    if len(full80_budget_rows) != 48:\n        failures.append("within-budget valid DTO inventory changed")\n    if full80_budget_max_tokens > MAX_TOKENS:\n        failures.append("within-budget full model-visible DTO exceeded the 800-token ceiling")\n    if not all(value["same_as_current"] for value in fixed_pool.values()):\n        failures.append("2x2/contextualization lanes did not share the same semantic pre-cap candidate-pool multiset")\n'''
if text.count(old) != 1:
    raise SystemExit('acceptance DTO budget anchor changed')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
PY
git diff --check


python -m pytest -q \
  tests/docs/test_docs_context_budget_reserve.py \
  tests/test_systemic_retrieval_candidate_pool.py \
  tests/test_pre_hydration_source_policy.py \
  tests/test_retrieval_diversity_policy.py \
  tests/test_active_fts_projection.py \
  tests/test_retrieval_features.py \
  tests/test_query_planning.py \
  tests/test_public_vector_retrieval.py \
  tests/docs/test_subject_binding_strength.py \
  tests/docs/test_project_answer_contract_v2.py \
  tests/docs/test_project_answer_contract_v3.py \
  tests/docs/test_question_plan_v4.py
python -m compileall -q docmancer tests scripts eval/systemic_retrieval_plan
git diff --check


python scripts/run_systemic_retrieval_plan_gate.py \
  --work /tmp/docatlas-systemic-plan \
  --report experiments/finalization/PR186_SYSTEMIC_RETRIEVAL_ACCEPTANCE.json


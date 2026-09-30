"""Preparation-unit tests. Synthetic fixtures are NOT model/holdout results.

The injected token counter tests control flow only, not the production codec.
The CLI always uses docs_context_budget_tokens from the repository.
"""
from copy import deepcopy
import json

import pytest
from experiments.crosslingual_relevance import m6_weak_model as m6


@pytest.fixture
def inputs():
    text = "Default behavior.\n\nOnly when enabled, run ` /-S`, not `/-S`.\n"
    docs = {"docs/rule.md": text}
    task = {"id": "unit-only-task", "project": "unit-only", "formulation": "mixed",
        "question": "Что делать when enabled?", "gold_path": "docs/rule.md", "gold_lines": [(1, 1), (3, 3)]}
    claims = [{"id": "rule", "alternatives": [{"path": "docs/rule.md",
        "document_sha256": m6.text_digest(text), "clauses": ["Only when enabled", "` /-S`, not `/-S`"]}]}]
    source = {"path_or_url": "docs/rule.md", "line_start": 3, "line_end": 3,
        "snippet": text.splitlines(keepends=True)[2]}
    packet = {"status": "ok", "sources": [source], "answer_supported": False}
    rows = [{"task_id": task["id"], "condition": condition, "payload": deepcopy(packet),
        "evaluation_kind": "real_model_replay", "gold_oracle_used": False,
        "assessment": {"source_policy_status": "PASS", "canonical_errors": []},
        "source_policy_errors": [], "scorer_summary": {"degraded": False}, "model_executed": False}
        for condition in ("lexical_baseline", "dense_rescue")]
    settings = {"weak_model": {"model_id": "unit/weak", "revision": "1"*40, "manifest_sha256": "2"*64},
        "judge": {"model_id": "unit/judge", "revision": "3"*40, "manifest_sha256": "4"*64},
        "decoding": {"temperature": 0, "max_output_tokens": 512, "seed": 42, "n_runs": 1},
        "order_seed": 42, "runtime": {k: "TEST_ONLY_NOT_A_REAL_RUNTIME"
            for k in ("python", "transformers", "torch", "device", "dtype")}}
    replay = {"schema_version": 2, "evaluation_kind": "real_model_replay", "rows": rows}
    return replay, [task], {"unit-only": docs}, {task["id"]: claims}, settings


def prepare(inputs, counter=lambda _: 100):
    return m6.prepare_controls(*inputs, budget_counter=counter)


def test_no_context_has_identical_instruction():
    question = "Different ` /-S` and `/-S`?"
    empty = m6._build_prompt(question, None)
    provided = m6._build_prompt(question, "source text")
    assert empty.split("Context:\n")[0] == provided.split("Context:\n")[0]
    assert empty.split("Question: ")[1] == provided.split("Question: ")[1]


def test_four_real_context_slots_not_placeholders(inputs):
    public, private = prepare(inputs)
    assert len(public["prompts"]) == 4
    assert {p["blind_id"] for p in public["prompts"]} == {r["blind_id"] for r in private["rows"]}
    assert private["status"] == "PREPARED_NOT_EXECUTED"
    assert private["independent_holdout"] is False
    assert private["real_model_answers"] == private["blind_judgments"] == 0
    for prompt in public["prompts"]:
        assert set(prompt) == {"blind_id", "prompt"}
        assert not any(arm in prompt["prompt"] for arm in m6.CONDITIONS)
        assert "requires re-running" not in prompt["prompt"]
    oracle = next(r for r in private["rows"] if r["condition"] == "oracle_context")
    assert oracle["all_required_facts"] is True


def test_oracle_searches_all_labelled_ranges_not_only_first(inputs):
    _, tasks, documents, claims, _ = inputs
    packet = m6._build_oracle_packet(tasks[0], documents["unit-only"],
        claims=claims[tasks[0]["id"]], budget_counter=lambda _: 100)
    assert packet["sources"][0]["line_start"] == 3
    assert "` /-S`, not `/-S`" in packet["sources"][0]["snippet"]
    assert packet["answer_supported"] is False and packet["edit_ready"] is False


def test_oracle_cannot_silently_clip_or_omit_fact(inputs):
    with pytest.raises(ValueError, match="no complete canonical oracle"):
        prepare(inputs, counter=lambda p: 801 if p.get("edit_ready") is False else 100)


def test_budget_counter_error_is_not_replaced_by_len_estimate(inputs):
    with pytest.raises(RuntimeError, match="codec unavailable"):
        prepare(inputs, counter=lambda _: (_ for _ in ()).throw(RuntimeError("codec unavailable")))


def test_missing_condition_is_blocker(inputs):
    inputs[0]["rows"].pop()
    with pytest.raises(ValueError, match="missing .* dense_rescue"):
        prepare(inputs)


def test_duplicate_condition_is_blocker(inputs):
    inputs[0]["rows"].append(deepcopy(inputs[0]["rows"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        prepare(inputs)


@pytest.mark.parametrize("change", ["handler", "policy", "canonical", "oracle", "missing_audit", "snapshot"])
def test_untrusted_replay_rows_cannot_become_context(inputs, change):
    row = inputs[0]["rows"][1]
    if change == "handler": row["payload"]["status"] = "failed"
    if change == "policy": row["assessment"]["source_policy_status"] = "FAIL"
    if change == "missing_audit": row.pop("source_policy_errors")
    if change == "oracle": row["gold_oracle_used"] = True
    if change == "canonical": row["payload"]["sources"][0]["snippet"] = "invented"
    if change == "snapshot": row["payload"]["sources"][0]["source_content_hash"] = "0"*64
    with pytest.raises(ValueError): prepare(inputs)


def test_degraded_condition_is_kept_and_disclosed_not_filtered(inputs):
    inputs[0]["rows"][1]["scorer_summary"] = {"degraded": True, "degraded_reason": "timeout"}
    public, private = prepare(inputs)
    row = next(r for r in private["rows"] if r["condition"] == "new_context")
    assert row["runtime_observation"]["scorer_summary"]["degraded"] is True
    assert len(public["prompts"]) == 4


@pytest.mark.parametrize("change", ["placeholder", "moving_revision", "same_judge", "no_manifest", "decoding"])
def test_unfrozen_model_settings_rejected(inputs, change):
    settings = inputs[-1]
    if change == "placeholder": settings["weak_model"]["model_id"] = "[to be filled]"
    if change == "moving_revision": settings["weak_model"]["revision"] = "main"
    if change == "same_judge": settings["judge"] = deepcopy(settings["weak_model"])
    if change == "no_manifest": settings["weak_model"].pop("manifest_sha256")
    if change == "decoding": settings["decoding"]["temperature"] = 0.5
    with pytest.raises(ValueError): prepare(inputs)


def test_refuse_overwrite_and_separate_private_key(inputs, tmp_path):
    public, private = prepare(inputs)
    output = tmp_path / "experiment"
    m6.write_controls(output, public, private)
    assert m6.digest(json.loads((output / "blinded_prompts.json").read_text())) == private["blinded_prompts_sha256"]
    assert (output / "PRIVATE_KEY.json").stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError): m6.write_controls(output, public, private)


def test_failed_preparation_writes_no_protocol(tmp_path, capsys):
    output = tmp_path / "should-not-exist"
    assert m6.main(["--replay", str(tmp_path / "missing.json"),
        "--settings", str(tmp_path / "settings.json"), "--output-dir", str(output)]) == 2
    assert not output.exists()
    assert '"status": "BLOCKED"' in capsys.readouterr().out

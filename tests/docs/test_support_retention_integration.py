from __future__ import annotations

from eval.evidence_quality_v2.run import documents_for, load_protocol, registry_for
from eval.evidence_quality_v2.semantic import assess_context
from tests.docs._reference_binding_fixtures import capture_reference_case


def test_two_supported_remedies_survive_same_query_attribution(tmp_path) -> None:
    _protocol, cases, manifest = load_protocol()
    case = next(item for item in cases if item["id"] == "uv-03")
    cap = capture_reference_case(
        tmp_path,
        documents_for("uv", manifest),
        case["question"],
    )
    result = assess_context(case, cap["public_payload"], registry_for("uv", manifest))

    assert result["context_sufficiency"] == "sufficient"
    visible = "\n".join(row["snippet"] for row in cap["public_payload"].get("sources") or ())
    assert "--prerelease allow" in visible
    assert "requirements.in" in visible


def test_same_origin_upgrade_survives_three_source_cap_after_required_lookups(tmp_path) -> None:
    cap = capture_reference_case(
        tmp_path,
        {
            "a.md": (
                "# Retry\n\nA transport retry uses `--relay-retry`.\n\n"
                "A transport retry can alternatively use `--backup-relay`.\n"
            ),
            "b.md": "# Database\n\nA database migration command uses `db migrate`.\n",
            "c.md": "# Cache\n\nA cache cleanup command uses `cache clean`.\n",
        },
        "What command handles a transport retry?",
        lookups=("database migration command", "cache cleanup command"),
    )
    payload = cap["public_payload"]
    assert len(payload["sources"]) == 3
    assert payload["missing_query_ids"] == []
    retry = next(row for row in payload["sources"] if row["path_or_url"] == "a.md")
    assert "--relay-retry" in retry["snippet"]
    assert "--backup-relay" in retry["snippet"]


def test_projector_uses_prepared_snapshot_without_source_io(tmp_path, monkeypatch) -> None:
    from copy import deepcopy
    from pathlib import Path

    from docmancer.docs.application import _docs_context_projection_core as core
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection

    cap = capture_reference_case(
        tmp_path,
        {"Guide.md": "# Retry\n\nA transport retry uses `--relay-retry`.\n\nA transport retry uses `--backup-relay`.\n"},
        "What command handles a transport retry?",
    )
    retrieval = deepcopy(cap["projection_attempts"][0]["before_projection"])
    retrieval.pop("_source_continuation_project_root", None)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("projector attempted source I/O")

    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr("builtins.open", forbidden)
    payload, snapshot = core.project_docs_context(retrieval=retrieval, max_tokens=800)
    # Validation is pure over the matching final snapshot as well.
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
    assert "_delivery_footprint" not in repr(payload)

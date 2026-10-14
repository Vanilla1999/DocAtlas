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

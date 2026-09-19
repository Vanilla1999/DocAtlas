from pathlib import Path
from typing import Any

from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.project_context_quality.capture_public_context import capture_public_call
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens


def capture_fixture(
    tmp_path: Path,
    documents: dict[str, str],
    question: str,
    lookups: tuple[str, ...] = (),
) -> dict[str, Any]:
    root = tmp_path / "corpus"
    write_project(root, documents)
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, root)
        request: dict[str, Any] = {
            "project_path": str(root), "scope": "project", "question": question,
        }
        if lookups:
            request["lookup_queries"] = list(lookups)
        capture = capture_public_call(service, request)
        payload = capture["public_payload"]
        assert docs_context_budget_tokens(payload) <= 800
        assert len(payload.get("sources") or []) <= 3
        if payload.get("kind") == "docs_context":
            for key in ("answer_supported", "answer_available", "edit_ready"):
                assert payload[key] is False
        for source in payload.get("sources") or []:
            path = (root / source["path_or_url"]).resolve()
            assert path.is_relative_to(root.resolve())
            lines = path.read_text(encoding="utf-8").splitlines()
            start, end = source["line_start"], source["line_end"]
            assert type(start) is int and type(end) is int
            assert 1 <= start <= end <= len(lines)
            assert source["snippet"] in "\n".join(lines[start - 1:end])
        for attempt in capture.get("projection_attempts") or []:
            assert validate_model_visible_projection(
                attempt["projected_payload"], snapshot=attempt["snapshot"], max_tokens=800,
            ) == []
        return capture


def visible(capture: dict[str, Any]) -> str:
    return "\n".join(
        source["snippet"]
        for source in capture["public_payload"].get("sources") or []
    )

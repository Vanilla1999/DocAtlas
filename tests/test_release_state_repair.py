from __future__ import annotations

import json
from pathlib import Path

from docmancer._version import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_release_state_is_semantic_clean_and_consistent() -> None:
    assert __version__ == "1.3.1"

    leaked_workflows = sorted(
        path.name
        for path in (ROOT / ".github/workflows").glob("materialize-*.yml")
    )
    leaked_scripts = sorted(
        path.name for path in (ROOT / "scripts").glob("materialize_*.py")
    )
    assert leaked_workflows == []
    assert leaked_scripts == []

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.index("## [1.3.1]") < changelog.index("## [1.3.0]")
    assert "invalid-publisher" in changelog

    workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    assert "for example v1.3.1" in workflow
    assert "    environment: release-current" in workflow
    assert "    environment: release\n" not in workflow

    identity = (ROOT / "docs/release-identity.md").read_text(encoding="utf-8")
    assert "current source release candidate is **DocAtlas 1.3.1**" in identity
    assert "v1.3.0" in identity
    assert "must not be moved, replaced, or reused" in identity
    assert "environment: release-current" in identity
    assert "unpublished historical milestone" in identity.lower()
    assert "no public `doc-atlas==1.3.1` release is claimed" in identity.lower()

    scorecard = (ROOT / "docs/public-truth-scorecard.md").read_text(encoding="utf-8")
    assert "Status: **INCOMPLETE**" in scorecard
    assert "Trusted Publisher identity | `pending`" in scorecard
    assert "Exact public artifact identity | `pending`" in scorecard
    assert "Exact public MCP behavior | `pending`" in scorecard
    assert "Cross-platform public install | `pending`" in scorecard
    assert "doc-atlas==1.3.1" in scorecard

    roadmap = (ROOT / "roadmap/README.md").read_text(encoding="utf-8")
    assert "P0.5 — Publish and verify public `1.3.1`" in roadmap
    assert "superseded pre-public attempt" in roadmap


def test_tag_evidence_cannot_be_confused_with_public_release_closure() -> None:
    evidence_path = ROOT / "docs/release-evidence/v1.3.1-tag.json"
    if not evidence_path.exists():
        identity = (ROOT / "docs/release-identity.md").read_text(encoding="utf-8")
        assert "The tag is created only after" in identity
        return

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["tag"] == "v1.3.1"
    assert evidence["target_commit_sha"] == evidence["peeled_commit_sha"]
    assert evidence["public_artifact_status"] in {"pending", "green"}

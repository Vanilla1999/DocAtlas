from pathlib import Path

from docmancer._version import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_patch_release_identity_is_single_source_and_preserves_failed_tag_audit():
    assert __version__ == "1.3.1"
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.index("## [1.3.1]") < changelog.index("## [1.3.0]")

    identity = (ROOT / "docs/release-identity.md").read_text(encoding="utf-8")
    assert "current source release candidate is **DocAtlas 1.3.1**" in identity
    assert "v1.3.0" in identity
    assert "must not be moved, replaced, or reused" in identity
    assert "invalid-publisher" in identity
    assert "environment: release-current" in identity

    roadmap = (ROOT / "roadmap/README.md").read_text(encoding="utf-8")
    assert "P0.5 — Publish and verify public `1.3.1`" in roadmap
    assert "superseded pre-public attempt" in roadmap

    scorecard = (ROOT / "docs/public-truth-scorecard.md").read_text(encoding="utf-8")
    assert "Status: **INCOMPLETE**" in scorecard
    assert "Trusted Publisher identity | `pending`" in scorecard
    assert "doc-atlas==1.3.1" in scorecard


def test_publish_workflow_uses_replacement_identity_not_failed_environment():
    workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    assert "for example v1.3.1" in workflow
    assert "    environment: release-current" in workflow
    assert "    environment: release\n" not in workflow

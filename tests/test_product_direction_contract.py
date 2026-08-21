from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_product_direction_is_evidence_authority_not_general_code_intelligence() -> None:
    brief = (ROOT / "docs" / "DOCMANCER_PRODUCT_BRIEF.md").read_text(encoding="utf-8")
    adr = (ROOT / "docs" / "adr" / "0002-evidence-authority-direction.md").read_text(encoding="utf-8")

    product_statement = "local, version-bound documentation authority and evidence delivery layer for coding agents"
    assert product_statement in brief.lower()
    assert product_statement in adr.lower()

    for text in (brief, adr):
        lowered = text.lower()
        assert "does **not** replace" in lowered or "does **not** try to replace" in lowered
        assert "source-code search" in lowered or "source-code search or an lsp" in lowered
        assert "code graph" in lowered
        assert "context7 parity" in lowered
        assert "not demonstrated" in lowered or "unproven" in lowered
        assert "beta" in lowered


def test_active_roadmap_orders_public_agent_and_product_truth() -> None:
    roadmap = (ROOT / "roadmap" / "README.md").read_text(encoding="utf-8")

    public_truth = roadmap.index("# P0 — PUBLIC TRUTH")
    agent_truth = roadmap.index("# P1 — AGENT TRUTH")
    product_truth = roadmap.index("# P2 — PRODUCT TRUTH")
    conditional = roadmap.index("# P3 — PRODUCTIZATION / CONDITIONAL EXPANSION")

    assert public_truth < agent_truth < product_truth < conditional
    assert "Installed-MCP live benchmark harness" in roadmap
    assert "Agent Developer 0/11 first-divergence atlas" in roadmap
    assert "Agent Contract v2 ablation" in roadmap
    assert "Real-repository coding benchmark" in roadmap
    assert "P0 freeze rule" in roadmap

    for frozen_work in (
        "new public MCP tool",
        "Context7 parity expansion",
        "first-party code graph",
        "relaxing `insufficient_evidence`",
    ):
        assert frozen_work in roadmap


def test_historical_roadmap_is_bound_to_exact_pre_reset_commit() -> None:
    history = (ROOT / "roadmap" / "history" / "README.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "roadmap" / "README.md").read_text(encoding="utf-8")
    expected = "d565d8e75af2cbc56bc00fdc9df19dd1ae66863a"

    assert expected in history
    assert expected in roadmap
    assert f"git show {expected}:roadmap/README.md" in history


def test_release_identity_defers_public_version_to_1_3_0() -> None:
    release = (ROOT / "docs" / "release-identity.md").read_text(encoding="utf-8")
    version_source = (ROOT / "docmancer" / "_version.py").read_text(encoding="utf-8")

    assert "1.2.0" in release
    assert "unpublished repository milestone" in release.lower()
    assert "next intended public release" in release.lower()
    assert "doc-atlas 1.3.0" in release
    assert "remains **Beta**" in release

    # This roadmap-reset PR records release identity but deliberately does not
    # perform the later release-preparation version bump.
    assert '__version__ = "1.2.0"' in version_source


def test_product_brief_keeps_live_and_patch_value_claims_honest() -> None:
    brief = (ROOT / "docs" / "DOCMANCER_PRODUCT_BRIEF.md").read_text(encoding="utf-8")

    assert "recorded model-backed Agent Developer result is 0/11" in brief
    assert "historical Task 23 product decision is formally `INCONCLUSIVE`" in brief
    assert "Context7 parity is **not demonstrated**" in brief
    assert "Stable" in brief
    assert "out-of-scope public claims" in brief

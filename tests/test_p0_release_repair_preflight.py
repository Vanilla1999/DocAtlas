from pathlib import Path

from docmancer._version import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_release_repair_has_exact_1_3_1_candidate_identity():
    assert __version__ == "1.3.1"
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.index("## [1.3.1] - 2026-08-22") < changelog.index(
        "## [1.3.0] - 2026-08-21"
    )

    identity = (ROOT / "docs/release-identity.md").read_text(encoding="utf-8")
    assert "current source release candidate is **DocAtlas 1.3.1**" in identity
    assert "v1.3.0" in identity
    assert "invalid-publisher" in identity
    assert "environment: release-current" in identity
    assert "one-time token fallback" in identity
    assert "product maturity remains **Beta**" in identity


def test_no_abandoned_materializer_carriers_remain():
    workflows = sorted(ROOT.glob(".github/workflows/materialize-*"))
    scripts = sorted(ROOT.glob("scripts/materialize_*"))
    assert workflows == []
    assert scripts == []


def test_one_shot_closure_is_exact_tag_bound_and_fail_closed():
    workflow = (
        ROOT / ".github/workflows/close-p0-after-public-1.3.1.yml"
    ).read_text(encoding="utf-8")
    assert "RELEASE_TAG: v1.3.1" in workflow
    assert "RELEASE_VERSION: 1.3.1" in workflow
    assert "required-ci" in workflow
    assert "git tag -a" in workflow
    assert "git tag -f" not in workflow
    assert "inputs[publisher_mode]=token" in workflow
    assert "Refuse an existing public 1.3.1 before launch" in workflow
    assert "public-platform-smoke (ubuntu-latest)" in workflow
    assert "public-platform-smoke (macos-latest)" in workflow
    assert "public-platform-smoke (windows-latest)" in workflow
    assert "Capture exact public artifact bytes" in workflow
    assert "scripts/close_p0_after_release.py" in workflow
    assert "git push origin HEAD:main" in workflow


def test_token_fallback_is_explicit_nondefault_and_self_erasing():
    workflow = (ROOT / ".github/workflows/publish.yml").read_text(
        encoding="utf-8"
    )
    assert "publisher_mode:" in workflow
    assert "default: oidc" in workflow
    assert "Publish to PyPI with OIDC" in workflow
    assert "Publish to PyPI with reviewed one-time token fallback" in workflow
    assert "password: ${{ secrets.PYPI_API_TOKEN }}" in workflow
    assert "inputs.publisher_mode == 'token'" in workflow
    assert (
        "inputs.publisher_mode == 'token' && 'release' || 'release-current'"
        in workflow
    )

    closer = (ROOT / "scripts/close_p0_after_release.py").read_text(
        encoding="utf-8"
    )
    assert "restore_oidc_only_publish_workflow" in closer
    assert 'Path(__file__).unlink()' in closer
    assert "Publisher authentication | `accepted_risk`" in closer
    assert "product_maturity" in closer
    assert "Beta" in closer


def test_public_truth_remains_pending_before_real_public_evidence():
    scorecard = (ROOT / "docs/public-truth-scorecard.md").read_text(
        encoding="utf-8"
    )
    assert "Status: **INCOMPLETE**" in scorecard
    assert "Exact public artifact identity | `pending`" in scorecard
    assert "Exact public MCP behavior | `pending`" in scorecard
    assert "Cross-platform public install | `pending`" in scorecard
    assert "Status: **CLOSED**" not in scorecard
    assert not (ROOT / "docs/release-evidence/v1.3.1-public.json").exists()

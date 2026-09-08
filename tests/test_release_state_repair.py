from __future__ import annotations

import json
from pathlib import Path

from docmancer._version import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_release_state_is_semantic_clean_and_consistent() -> None:
    assert __version__ == "1.3.2"

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
    assert changelog.index("## [1.3.2]") < changelog.index("## [1.3.1]") < changelog.index("## [1.3.0]")
    assert "invalid-publisher" in changelog

    workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    assert "for example v1.3.2" in workflow
    assert "    environment: release-current" in workflow
    assert "    environment: release\n" not in workflow

    identity = (ROOT / "docs/release-identity.md").read_text(encoding="utf-8")
    assert "current source release candidate is **DocAtlas 1.3.2**" in identity
    assert "v1.3.1" in identity
    assert "must not be moved, replaced, or reused" in identity
    assert "environment: release-current" in identity
    assert "unpublished historical milestone" in identity.lower()
    assert "no public `doc-atlas==1.3.2`" in identity.lower()

    scorecard = (ROOT / "docs/public-truth-scorecard.md").read_text(encoding="utf-8")
    assert "Status: **INCOMPLETE**" in scorecard
    assert "Trusted Publisher identity | `pending`" in scorecard
    assert "Exact public artifact identity | `pending`" in scorecard
    assert "Exact public MCP behavior | `pending`" in scorecard
    assert "Cross-platform public install | `pending`" in scorecard
    assert "doc-atlas==1.3.2" in scorecard

    roadmap = (ROOT / "roadmap/README.md").read_text(encoding="utf-8")
    assert "P0.5 — Publish and verify public `1.3.2`" in roadmap
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



def test_official_mcp_registry_metadata_matches_release_identity() -> None:
    payload = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    server_name = "io.github.Vanilla1999/docatlas"
    assert payload["$schema"] == (
        "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
    )
    assert payload["name"] == server_name
    assert payload["version"] == __version__
    assert payload["repository"] == {
        "url": "https://github.com/Vanilla1999/DocAtlas",
        "source": "github",
    }
    assert len(payload["packages"]) == 1
    package = payload["packages"][0]
    assert package["registryType"] == "pypi"
    assert package["registryBaseUrl"] == "https://pypi.org"
    assert package["identifier"] == "doc-atlas"
    assert package["version"] == __version__
    assert package["runtimeHint"] == "uvx"
    assert package["transport"] == {"type": "stdio"}
    assert package["packageArguments"] == [
        {"type": "positional", "value": "mcp"},
        {"type": "positional", "value": "docs-serve"},
    ]

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"<!-- mcp-name: {server_name} -->" in readme


def test_registry_publish_is_oidc_only_and_after_public_platform_smoke() -> None:
    workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    assert "publish-official-mcp-registry" in workflow
    assert "needs: [public-platform-smoke]" in workflow
    assert "id-token: write" in workflow
    assert "./mcp-publisher validate server.json" in workflow
    assert "./mcp-publisher login github-oidc" in workflow
    assert "./mcp-publisher publish server.json" in workflow
    assert "releases/download/v1.7.9/mcp-publisher_linux_amd64.tar.gz" in workflow
    assert (
        "ab128162b0616090b47cf245afe0a23f3ef08936fdce19074f5ba0a4469281ac"
        in workflow
    )
    assert "MCP_GITHUB_TOKEN" not in workflow
    assert "MCP_PRIVATE_KEY" not in workflow

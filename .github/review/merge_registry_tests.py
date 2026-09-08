from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

standalone = ROOT / "tests/test_mcp_registry_metadata.py"
if not standalone.exists():
    raise SystemExit("expected generated registry test module is missing")
standalone.unlink()

release_test = ROOT / "tests/test_release_state_repair.py"
text = release_test.read_text(encoding="utf-8")
marker = "def test_official_mcp_registry_metadata_matches_release_identity()"
if marker in text:
    raise SystemExit("registry release assertions are already present")

text += r'''


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
    assert "./mcp-publisher login github-oidc" in workflow
    assert "./mcp-publisher publish server.json" in workflow
    assert "releases/download/v1.7.9/mcp-publisher_linux_amd64.tar.gz" in workflow
    assert (
        "ab128162b0616090b47cf245afe0a23f3ef08936fdce19074f5ba0a4469281ac"
        in workflow
    )
    assert "MCP_GITHUB_TOKEN" not in workflow
    assert "MCP_PRIVATE_KEY" not in workflow
'''
release_test.write_text(text, encoding="utf-8")

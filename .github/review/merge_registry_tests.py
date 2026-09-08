from __future__ import annotations

import re
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

# Preserve the explicit immutable-history wording while changing only the
# active candidate from unpublished 1.3.1 to launch-capable 1.3.2.
identity = ROOT / "docs/release-identity.md"
identity_text = identity.read_text(encoding="utf-8")
needle = (
    "Do not move or recreate `v1.3.1`, and do not present a newer tree as that tag."
)
replacement = (
    "`v1.3.1` must never be moved, replaced, or reused. "
    "Do not move or recreate `v1.3.1`, and do not present a newer tree as that tag."
)
if identity_text.count(needle) != 1:
    raise SystemExit("expected historical v1.3.1 immutability sentence exactly once")
identity.write_text(identity_text.replace(needle, replacement, 1), encoding="utf-8")

roadmap = ROOT / "roadmap/README.md"
roadmap_text = roadmap.read_text(encoding="utf-8")
needle = (
    "`v1.3.0` and `v1.3.1` remain immutable pre-public audit identities whose "
    "PyPI OIDC uploads failed before publication."
)
replacement = (
    "`v1.3.0` and `v1.3.1` are superseded pre-public attempt identities; both "
    "remain immutable, and their PyPI OIDC uploads failed before publication."
)
if roadmap_text.count(needle) != 1:
    raise SystemExit("expected P0.5 historical release sentence exactly once")
roadmap.write_text(roadmap_text.replace(needle, replacement, 1), encoding="utf-8")

# The canonical maturity test derives current release truth from the source
# version. Move only its current-candidate assertions to 1.3.2; historical
# 1.3.1 audit checks remain in the dedicated release tests.
branding_test = ROOT / "tests/docs/test_user_facing_docs_branding.py"
branding = branding_test.read_text(encoding="utf-8")
for old, new in (
    ('assert source_version.group(1) == "1.3.1"', 'assert source_version.group(1) == "1.3.2"'),
    ('assert "no public `doc-atlas==1.3.1` release is claimed" in release_identity.lower()', 'assert "no public `doc-atlas==1.3.2`" in release_identity.lower()'),
    ('assert f"## [{source_version.group(1)}] - 2026-08-22" in changelog', 'assert f"## [{source_version.group(1)}] - 2026-09-08" in changelog'),
):
    if branding.count(old) != 1:
        raise SystemExit(f"branding release assertion drifted: {old}")
    branding = branding.replace(old, new, 1)
branding_test.write_text(branding, encoding="utf-8")

# The diagnostic inventory is deliberately hash-bound to the exact collected
# node IDs. These two new behavioral release tests therefore require an exact
# reviewed hash refresh rather than bypassing collection hardening.
manifest = ROOT / "tests/diagnostic_labels.json"
manifest_text = manifest.read_text(encoding="utf-8")
pattern = re.compile(
    r'("tests/test_release_state_repair\.py"\s*:\s*")([0-9a-f]{64})(")'
)
replacement_digest = "9e6a44ac6abc3eeaf0e55d9ea6df3f0da90cd7982412e664b9589262277ff9dc"
manifest_text, count = pattern.subn(
    rf"\g<1>{replacement_digest}\g<3>", manifest_text, count=1
)
if count != 1:
    raise SystemExit(
        "expected exactly one hash-bound diagnostic manifest entry for "
        "tests/test_release_state_repair.py"
    )
manifest.write_text(manifest_text, encoding="utf-8")

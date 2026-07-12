from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_publish_workflow_is_manual_build_once_and_oidc() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    assert "workflow_dispatch:" in text
    assert "pull_request:" in text
    assert "release:" not in text and "tags:" not in text
    assert text.count("python -m build") == 1
    assert 'python: ["3.11", "3.12", "3.13"]' in text
    assert "id-token: write" in text
    assert "PYPI_API_TOKEN" not in text
    assert "environment: release" in text
    assert "if: github.event_name == 'workflow_dispatch'" in text
    assert "refs/tags/${{ inputs.tag }}" in text
    for line in text.splitlines():
        if "uses:" in line:
            ref = line.split("@", 1)[1].split()[0]
            assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref)


def test_installer_smoke_passes_an_existing_wheel_path() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    assert 'DOCATLAS_INSTALL_SOURCE="$(find "$PWD/dist" -name \'*.whl\' -print -quit)"' in text


def test_publish_excludes_release_manifest_from_pypi_upload() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    remove_manifest = text.index("rm dist/release-manifest.json")
    publish_action = text.index("pypa/gh-action-pypi-publish@")
    assert remove_manifest < publish_action


def test_sdist_gate_builds_and_smokes_its_own_wheel() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    assert "python -m pip wheel --no-deps --wheel-dir sdist-wheel dist/*.tar.gz" in text
    assert "python -m pip install --force-reinstall sdist-wheel/*.whl" in text
    assert "python scripts/release_gate.py --dist sdist-wheel" in text


def test_publish_runs_exact_public_version_smoke() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    publish = text[text.index("  publish:"):]
    assert "DOCATLAS_INSTALL_VERSION=\"$RELEASE_VERSION\"" in publish
    assert "scripts/docs_mcp_stdio_smoke.py" in publish


def test_stdio_smoke_requires_cited_content() -> None:
    text = (ROOT / "scripts/docs_mcp_stdio_smoke.py").read_text()
    assert "assert NEEDLE in rendered" in text


def test_installer_compares_exact_version_output() -> None:
    text = (ROOT / "scripts/install.sh").read_text()
    assert '[ "$INSTALLED_VERSION" = "doc-atlas $EXPECTED_VERSION" ]' in text


def test_installer_accepts_pinned_and_local_sources() -> None:
    text = (ROOT / "scripts/install.sh").read_text()
    assert "DOCATLAS_INSTALL_SOURCE" in text
    assert "DOCATLAS_INSTALL_VERSION" in text
    assert "DOCATLAS_EXPECT_VERSION" in text


def test_release_gate_help() -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts/release_gate.py"), "--help"], check=True)

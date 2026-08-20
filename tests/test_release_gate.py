from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_publish_workflow_is_manual_build_once_and_oidc() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    trigger_block = text.split("\non:\n", 1)[1].split("\npermissions:\n", 1)[0]
    trigger_events = {
        line.strip()[:-1]
        for line in trigger_block.splitlines()
        if line.startswith("  ")
        and not line.startswith("    ")
        and line.strip().endswith(":")
    }
    assert trigger_events == {"workflow_dispatch", "pull_request"}
    assert "    tags:" not in trigger_block
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
    assert "RELEASE_TAG: ${{ inputs.tag }}" in publish
    assert 'RELEASE_VERSION="${RELEASE_TAG#v}"' in publish
    assert 'RELEASE_VERSION="${{ inputs.tag }}"' not in publish
    assert "DOCATLAS_INSTALL_VERSION=\"$RELEASE_VERSION\"" in publish
    assert "for attempt in 1 2 3 4 5" in publish
    assert "scripts/docs_mcp_stdio_smoke.py" in publish


def test_stdio_smoke_requires_cited_content() -> None:
    text = (ROOT / "scripts/docs_mcp_stdio_smoke.py").read_text()
    assert "assert NEEDLE in rendered" in text
    assert 'assert set(canonical_query) == {"question", "project_path", "mode"}' in text
    canonical_block = text[text.index("canonical_query = {"):text.index("compatibility_query =", text.index("canonical_query = {"))]
    assert "output_mode" not in canonical_block
    assert 'compatibility_query = {**canonical_query, "output_mode": "compact"}' in text


def test_stdio_smoke_accepts_structured_content_and_legacy_json_text() -> None:
    from scripts.docs_mcp_stdio_smoke import payload, text_payload

    class Text:
        def __init__(self, text: str) -> None:
            self.text = text

    class Result:
        def __init__(self, *, structured=None, text: str = "") -> None:
            if structured is not None:
                self.structuredContent = structured
            self.content = [Text(text)]

    expected = {"status": "ok", "kind": "docs_answer"}
    assert payload(Result(structured=expected, text="not JSON")) is expected
    assert payload(Result(text='{"status": "ok", "kind": "docs_answer"}')) == expected
    assert text_payload(Result(text='{"status": "ok", "kind": "docs_answer"}')) == expected
    with pytest.raises(AssertionError, match="included structuredContent"):
        text_payload(Result(structured=expected, text='{"status": "ok"}'))


def test_opencode_installer_enables_text_fallback_without_overwriting_other_environment() -> None:
    text = (ROOT / "scripts/install.sh").read_text()
    assert '"DOCATLAS_MCP_TEXT_FALLBACK": "1"' in text
    assert '"environment": {**environment, **desired["environment"]}' in text
    assert "has a different command; refusing to overwrite it" in text


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

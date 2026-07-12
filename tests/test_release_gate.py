from __future__ import annotations

import subprocess
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
    for line in text.splitlines():
        if "uses:" in line:
            ref = line.split("@", 1)[1].split()[0]
            assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref)


def test_installer_accepts_pinned_and_local_sources() -> None:
    text = (ROOT / "scripts/install.sh").read_text()
    assert "DOCATLAS_INSTALL_SOURCE" in text
    assert "DOCATLAS_INSTALL_VERSION" in text
    assert "DOCATLAS_EXPECT_VERSION" in text


def test_release_gate_help() -> None:
    subprocess.run(["python", str(ROOT / "scripts/release_gate.py"), "--help"], check=True)

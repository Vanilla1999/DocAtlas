from __future__ import annotations

import hashlib
import io
import json
import subprocess
from pathlib import Path

import pytest

from scripts import release_request as rr


ROOT = Path(__file__).resolve().parents[1]
REQUEST_PATH = Path(".github/release-requests/v1.3.1.json")


def _payload(base_sha: str, *, delta: list[str] | None = None) -> dict:
    return {
        "schema_version": 1,
        "state": "approved",
        "execute_on_merge": True,
        "product": "DocAtlas",
        "distribution": "doc-atlas",
        "version": "1.3.1",
        "tag": "v1.3.1",
        "expected_base_commit": base_sha,
        "allowed_release_delta": delta or [REQUEST_PATH.as_posix()],
        "publisher": {
            "owner": "Vanilla1999",
            "repository": "DocAtlas",
            "workflow": "publish.yml",
            "environment": "release-current",
        },
        "public_tools": ["docs_status", "get_docs_context", "prepare_docs"],
        "source_prs": [131, 132],
    }


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=root, text=True, encoding="utf-8"
    ).strip()


def _synthetic_repo(tmp_path: Path) -> tuple[Path, str, str]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.invalid")
    _write(root / "docmancer/_version.py", '__version__ = "1.3.1"\n')
    _write(root / "CHANGELOG.md", "## [1.3.1]\n\nSynthetic release.\n")
    _write(
        root / ".github/workflows/publish.yml",
        "on:\n  workflow_dispatch:\n"
        "jobs:\n  publish:\n"
        "    environment: release-current\n"
        "    steps:\n"
        "      - uses: pypa/gh-action-pypi-publish@pinned\n",
    )
    _write(
        root / "scripts/docs_mcp_stdio_smoke.py",
        'TOOLS = {"get_docs_context", "prepare_docs", "docs_status"}\n',
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "base")
    base = _git(root, "rev-parse", "HEAD")

    request = _payload(base)
    _write(
        root / REQUEST_PATH,
        json.dumps(request, indent=2, sort_keys=True) + "\n",
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "reviewed release request")
    target = _git(root, "rev-parse", "HEAD")
    return root, base, target


def test_committed_request_and_release_controller_are_fail_closed() -> None:
    request = rr.load_request(ROOT / REQUEST_PATH)
    assert request.execute is True
    assert request.version == "1.3.1"
    assert request.tag == "v1.3.1"
    assert request.publisher == rr.EXPECTED_PUBLISHER
    assert request.public_tools == rr.EXPECTED_PUBLIC_TOOLS

    workflow = (ROOT / ".github/workflows/release-request.yml").read_text(
        encoding="utf-8"
    )
    assert 'paths:\n      - ".github/release-requests/*.json"' in workflow
    assert "contents: write" in workflow
    assert "actions: write" in workflow
    assert "checks: read" in workflow
    assert "required-ci" in workflow
    assert "require-pypi-absent" in workflow
    assert 'git tag -a "$RELEASE_TAG"' in workflow
    assert "git tag -f" not in workflow
    assert "gh workflow run publish.yml" in workflow
    assert "PYPI_API_TOKEN" not in workflow
    assert "P0.6 remains unchanged in Git" in workflow


def test_release_checklist_uses_reviewed_request_and_current_environment() -> None:
    checklist = (ROOT / "docs/RELEASE_CHECKLIST.md").read_text(encoding="utf-8")
    assert ".github/release-requests/v1.3.1.json" in checklist
    assert "`release-current` environment" in checklist
    assert "protected `release` environment" not in checklist


def test_request_rejects_publisher_and_path_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    path = REQUEST_PATH
    bad = _payload("a" * 40)
    bad["publisher"]["environment"] = "release"
    _write(path, json.dumps(bad))
    with pytest.raises(rr.ReleaseRequestError, match="publisher identity mismatch"):
        rr.load_request(path)

    unsafe = _payload("a" * 40, delta=["../escape.json"])
    _write(path, json.dumps(unsafe))
    with pytest.raises(rr.ReleaseRequestError, match="unsafe repository path"):
        rr.load_request(path)


def test_preflight_binds_exact_reviewed_delta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, base, target = _synthetic_repo(tmp_path)
    monkeypatch.chdir(root)
    request = rr.load_request(REQUEST_PATH)

    result = rr.validate_repository(request, root=root, target_sha=target)
    assert result["target_sha"] == target
    assert result["expected_base_commit"] == base
    assert result["changed_files"] == [REQUEST_PATH.as_posix()]
    assert result["publisher"]["environment"] == "release-current"

    _write(root / "unexpected.txt", "not reviewed\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "unexpected")
    moved = _git(root, "rev-parse", "HEAD")
    with pytest.raises(rr.ReleaseRequestError, match="release delta mismatch"):
        rr.validate_repository(request, root=root, target_sha=moved)


def test_public_evidence_requires_exact_bytes_and_successful_platforms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    request_payload = _payload("a" * 40)
    _write(REQUEST_PATH, json.dumps(request_payload, sort_keys=True))
    request = rr.load_request(REQUEST_PATH)

    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "doc_atlas-1.3.1-py3-none-any.whl"
    sdist = dist / "doc_atlas-1.3.1.tar.gz"
    wheel.write_bytes(b"reviewed wheel bytes")
    sdist.write_bytes(b"reviewed sdist bytes")

    jobs = {
        "jobs": [
            {
                "name": "required-release",
                "conclusion": "success",
                "html_url": "https://github.invalid/jobs/required",
            },
            {
                "name": "publish",
                "conclusion": "success",
                "html_url": "https://github.invalid/jobs/publish",
            },
            *[
                {
                    "name": f"public-platform-smoke ({os_name})",
                    "conclusion": "success",
                    "html_url": f"https://github.invalid/jobs/{os_name}",
                }
                for os_name in (
                    "ubuntu-latest",
                    "macos-latest",
                    "windows-latest",
                )
            ],
        ]
    }
    jobs_path = tmp_path / "jobs.json"
    jobs_path.write_text(json.dumps(jobs), encoding="utf-8")

    files = {
        "https://files.invalid/wheel": wheel.read_bytes(),
        "https://files.invalid/sdist": sdist.read_bytes(),
    }
    metadata = {
        "info": {"version": "1.3.1"},
        "urls": [
            {
                "filename": wheel.name,
                "packagetype": "bdist_wheel",
                "url": "https://files.invalid/wheel",
                "digests": {
                    "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()
                },
            },
            {
                "filename": sdist.name,
                "packagetype": "sdist",
                "url": "https://files.invalid/sdist",
                "digests": {
                    "sha256": hashlib.sha256(sdist.read_bytes()).hexdigest()
                },
            },
        ],
    }

    def fake_urlopen(request_object, timeout=0):
        url = getattr(request_object, "full_url", str(request_object))
        if url.endswith("/pypi/doc-atlas/1.3.1/json"):
            return io.BytesIO(json.dumps(metadata).encode("utf-8"))
        return io.BytesIO(files[url])

    monkeypatch.setattr(rr.urllib.request, "urlopen", fake_urlopen)
    evidence = rr.build_public_evidence(
        request,
        target_sha="b" * 40,
        tag_object_sha="c" * 40,
        dist_dir=dist,
        jobs_path=jobs_path,
        run_id="123",
        run_url="https://github.invalid/runs/123",
    )

    assert evidence["public_artifact_status"] == "green"
    assert (
        evidence["artifacts"]["wheel"]["gated_sha256"]
        == evidence["artifacts"]["wheel"]["downloaded_sha256"]
    )
    assert (
        evidence["artifacts"]["sdist"]["gated_sha256"]
        == evidence["artifacts"]["sdist"]["pypi_metadata_sha256"]
    )
    assert set(evidence["public_smoke"]) == {"linux", "macos", "windows"}
    assert evidence["mcp"]["expected_tools"] == list(rr.EXPECTED_PUBLIC_TOOLS)

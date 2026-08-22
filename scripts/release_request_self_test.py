#!/usr/bin/env python3
"""Provider-free self-test for the reviewed release-request controller."""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import release_request as rr


ROOT = Path(__file__).resolve().parents[1]
REQUEST_PATH = Path(".github/release-requests/v1.3.1.json")


def payload(base_sha: str, *, delta: list[str] | None = None) -> dict:
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


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=root, text=True, encoding="utf-8"
    ).strip()


def expect_error(fragment: str, callback) -> None:
    try:
        callback()
    except rr.ReleaseRequestError as exc:
        if fragment not in str(exc):
            raise AssertionError(
                f"expected error containing {fragment!r}, got {str(exc)!r}"
            ) from exc
    else:
        raise AssertionError(f"expected ReleaseRequestError containing {fragment!r}")


@contextmanager
def synthetic_repo() -> Iterator[tuple[Path, str, str]]:
    with tempfile.TemporaryDirectory(prefix="docatlas-release-request-") as raw:
        root = Path(raw) / "repo"
        root.mkdir()
        git(root, "init")
        git(root, "config", "user.name", "Test")
        git(root, "config", "user.email", "test@example.invalid")
        write(root / "docmancer/_version.py", '__version__ = "1.3.1"\n')
        write(root / "CHANGELOG.md", "## [1.3.1]\n\nSynthetic release.\n")
        write(
            root / ".github/workflows/publish.yml",
            "on:\n  workflow_dispatch:\n"
            "jobs:\n  publish:\n"
            "    environment: release-current\n"
            "    steps:\n"
            "      - uses: pypa/gh-action-pypi-publish@pinned\n",
        )
        write(
            root / "scripts/docs_mcp_stdio_smoke.py",
            'TOOLS = {"get_docs_context", "prepare_docs", "docs_status"}\n',
        )
        git(root, "add", "-A")
        git(root, "commit", "-m", "base")
        base = git(root, "rev-parse", "HEAD")

        request = payload(base)
        write(
            root / REQUEST_PATH,
            json.dumps(request, indent=2, sort_keys=True) + "\n",
        )
        git(root, "add", "-A")
        git(root, "commit", "-m", "reviewed release request")
        target = git(root, "rev-parse", "HEAD")
        yield root, base, target


def test_committed_contract() -> None:
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

    checklist = (ROOT / "docs/RELEASE_CHECKLIST.md").read_text(encoding="utf-8")
    assert REQUEST_PATH.as_posix() in checklist
    assert "`release-current` environment" in checklist
    assert "protected `release` environment" not in checklist


def test_request_rejects_identity_and_path_drift() -> None:
    with tempfile.TemporaryDirectory(prefix="docatlas-release-request-invalid-") as raw:
        root = Path(raw)
        request_path = root / REQUEST_PATH
        bad = payload("a" * 40)
        bad["publisher"]["environment"] = "release"
        write(request_path, json.dumps(bad))
        expect_error(
            "publisher identity mismatch",
            lambda: rr.load_request(request_path),
        )

        unsafe = payload("a" * 40, delta=["../escape.json"])
        write(request_path, json.dumps(unsafe))
        expect_error("unsafe repository path", lambda: rr.load_request(request_path))


def test_preflight_binds_exact_reviewed_delta() -> None:
    with synthetic_repo() as (root, base, target):
        request = rr.load_request(root / REQUEST_PATH)
        result = rr.validate_repository(request, root=root, target_sha=target)
        assert result["target_sha"] == target
        assert result["expected_base_commit"] == base
        assert result["changed_files"] == [REQUEST_PATH.as_posix()]
        assert result["publisher"]["environment"] == "release-current"

        write(root / "unexpected.txt", "not reviewed\n")
        git(root, "add", "-A")
        git(root, "commit", "-m", "unexpected")
        moved = git(root, "rev-parse", "HEAD")
        expect_error(
            "release delta mismatch",
            lambda: rr.validate_repository(request, root=root, target_sha=moved),
        )


def test_public_evidence_requires_exact_bytes_and_platforms() -> None:
    with tempfile.TemporaryDirectory(prefix="docatlas-release-evidence-") as raw:
        root = Path(raw)
        request_path = root / REQUEST_PATH
        write(request_path, json.dumps(payload("a" * 40), sort_keys=True))
        request = rr.load_request(request_path)

        dist = root / "dist"
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
        jobs_path = root / "jobs.json"
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

        original_urlopen = rr.urllib.request.urlopen

        def fake_urlopen(request_object, timeout=0):
            del timeout
            url = getattr(request_object, "full_url", str(request_object))
            if url.endswith("/pypi/doc-atlas/1.3.1/json"):
                return io.BytesIO(json.dumps(metadata).encode("utf-8"))
            return io.BytesIO(files[url])

        rr.urllib.request.urlopen = fake_urlopen
        try:
            evidence = rr.build_public_evidence(
                request,
                target_sha="b" * 40,
                tag_object_sha="c" * 40,
                dist_dir=dist,
                jobs_path=jobs_path,
                run_id="123",
                run_url="https://github.invalid/runs/123",
            )
        finally:
            rr.urllib.request.urlopen = original_urlopen

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


def main() -> int:
    checks = (
        test_committed_contract,
        test_request_rejects_identity_and_path_drift,
        test_preflight_binds_exact_reviewed_delta,
        test_public_evidence_requires_exact_bytes_and_platforms,
    )
    for check in checks:
        check()
        print(f"PASS: {check.__name__}")
    print(f"Reviewed release request self-test: PASS ({len(checks)}/{len(checks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

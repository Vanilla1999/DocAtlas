#!/usr/bin/env python3
"""Validate reviewed DocAtlas release requests and build public release evidence."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

REQUEST_SCHEMA_VERSION = 1
EXPECTED_PRODUCT = "DocAtlas"
EXPECTED_DISTRIBUTION = "doc-atlas"
EXPECTED_PUBLISHER = {
    "owner": "Vanilla1999",
    "repository": "DocAtlas",
    "workflow": "publish.yml",
    "environment": "release-current",
}
EXPECTED_PUBLIC_TOOLS = ("docs_status", "get_docs_context", "prepare_docs")
SHA_RE = re.compile(r"[0-9a-f]{40}")
VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
PYPI_VERSION_URL = "https://pypi.org/pypi/{distribution}/{version}/json"
USER_AGENT = "DocAtlas-reviewed-release/1"


class ReleaseRequestError(ValueError):
    """Raised when a reviewed release request violates its fail-closed contract."""


@dataclass(frozen=True, slots=True)
class ReleaseRequest:
    path: Path
    repo_path: str
    state: str
    execute_on_merge: bool
    version: str
    tag: str
    expected_base_commit: str
    allowed_release_delta: tuple[str, ...]
    publisher: dict[str, str]
    public_tools: tuple[str, ...]
    source_prs: tuple[int, ...]
    raw: dict[str, Any]

    @property
    def execute(self) -> bool:
        return self.state == "approved" and self.execute_on_merge


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseRequestError(f"invalid release request {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReleaseRequestError("release request must be a JSON object")
    return payload


def _safe_repo_path(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    path = PurePosixPath(text)
    if (
        not text
        or text.startswith("/")
        or ".." in path.parts
        or (path.parts and path.parts[0].endswith(":"))
        or str(path) != text
    ):
        raise ReleaseRequestError(f"unsafe repository path: {value!r}")
    return text


def load_request(path: Path) -> ReleaseRequest:
    payload = _read_json(path)
    required = {
        "schema_version",
        "state",
        "execute_on_merge",
        "product",
        "distribution",
        "version",
        "tag",
        "expected_base_commit",
        "allowed_release_delta",
        "publisher",
        "public_tools",
        "source_prs",
    }
    unknown = set(payload) - required
    missing = required - set(payload)
    if missing or unknown:
        raise ReleaseRequestError(
            f"release request keys mismatch: missing={sorted(missing)} unknown={sorted(unknown)}"
        )
    if payload["schema_version"] != REQUEST_SCHEMA_VERSION:
        raise ReleaseRequestError("unsupported release request schema_version")
    if payload["product"] != EXPECTED_PRODUCT:
        raise ReleaseRequestError("release request product identity mismatch")
    if payload["distribution"] != EXPECTED_DISTRIBUTION:
        raise ReleaseRequestError("release request distribution identity mismatch")

    state = str(payload["state"])
    if state not in {"approved", "published"}:
        raise ReleaseRequestError(f"unsupported release request state: {state!r}")
    if not isinstance(payload["execute_on_merge"], bool):
        raise ReleaseRequestError("execute_on_merge must be boolean")

    version = str(payload["version"])
    tag = str(payload["tag"])
    if not VERSION_RE.fullmatch(version) or tag != f"v{version}":
        raise ReleaseRequestError("version/tag identity mismatch")

    expected_base = str(payload["expected_base_commit"])
    if not SHA_RE.fullmatch(expected_base):
        raise ReleaseRequestError("expected_base_commit must be a lowercase 40-character SHA")

    raw_delta = payload["allowed_release_delta"]
    if not isinstance(raw_delta, list) or not 1 <= len(raw_delta) <= 32:
        raise ReleaseRequestError("allowed_release_delta must contain 1..32 paths")
    delta = tuple(_safe_repo_path(value) for value in raw_delta)
    if list(delta) != sorted(set(delta)):
        raise ReleaseRequestError("allowed_release_delta must be sorted and unique")

    publisher = payload["publisher"]
    if publisher != EXPECTED_PUBLISHER:
        raise ReleaseRequestError(
            f"publisher identity mismatch: expected {EXPECTED_PUBLISHER!r}"
        )

    raw_tools = payload["public_tools"]
    if not isinstance(raw_tools, list):
        raise ReleaseRequestError("public_tools must be a list")
    tools = tuple(sorted(str(value) for value in raw_tools))
    if tools != EXPECTED_PUBLIC_TOOLS:
        raise ReleaseRequestError(
            f"public tool contract mismatch: expected {EXPECTED_PUBLIC_TOOLS!r}"
        )

    raw_prs = payload["source_prs"]
    if (
        not isinstance(raw_prs, list)
        or not raw_prs
        or any(
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
            for value in raw_prs
        )
        or raw_prs != sorted(set(raw_prs))
    ):
        raise ReleaseRequestError("source_prs must be sorted unique positive integers")

    path_text = path.as_posix()
    if path.is_absolute():
        parts = path.parts
        try:
            marker = max(index for index, part in enumerate(parts) if part == ".github")
        except ValueError as exc:
            raise ReleaseRequestError(
                "absolute request path must contain .github/release-requests"
            ) from exc
        path_text = PurePosixPath(*parts[marker:]).as_posix()
    request_repo_path = _safe_repo_path(path_text)
    if not request_repo_path.startswith(".github/release-requests/"):
        raise ReleaseRequestError("release request must live under .github/release-requests")
    if request_repo_path not in delta:
        raise ReleaseRequestError("allowed_release_delta must include the request file itself")

    return ReleaseRequest(
        path=path,
        repo_path=request_repo_path,
        state=state,
        execute_on_merge=payload["execute_on_merge"],
        version=version,
        tag=tag,
        expected_base_commit=expected_base,
        allowed_release_delta=delta,
        publisher=dict(publisher),
        public_tools=tools,
        source_prs=tuple(raw_prs),
        raw=payload,
    )


def _run_git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=root,
            text=True,
            encoding="utf-8",
            stderr=subprocess.STDOUT,
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise ReleaseRequestError(
            f"git {' '.join(args)} failed: {exc.output.strip()}"
        ) from exc


def _source_version(root: Path) -> str:
    text = (root / "docmancer/_version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)', text)
    if not match:
        raise ReleaseRequestError("source version not found")
    return match.group(1)


def _smoke_tools(root: Path) -> tuple[str, ...]:
    tree = ast.parse(
        (root / "scripts/docs_mcp_stdio_smoke.py").read_text(encoding="utf-8")
    )
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "TOOLS"
            for target in node.targets
        ):
            continue
        if not isinstance(node.value, (ast.Set, ast.Tuple, ast.List)):
            break
        values: list[str] = []
        for item in node.value.elts:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                raise ReleaseRequestError("TOOLS smoke contract must contain only strings")
            values.append(item.value)
        return tuple(sorted(values))
    raise ReleaseRequestError("TOOLS smoke contract not found")


def validate_repository(
    request: ReleaseRequest,
    *,
    root: Path,
    target_sha: str,
) -> dict[str, Any]:
    if not request.execute:
        raise ReleaseRequestError("only an approved executable request can cut a release")
    if not SHA_RE.fullmatch(target_sha):
        raise ReleaseRequestError("target_sha must be a lowercase 40-character SHA")

    head = _run_git(root, "rev-parse", "HEAD")
    if head != target_sha:
        raise ReleaseRequestError(f"checkout HEAD {head} does not match target {target_sha}")

    try:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", request.expected_base_commit, target_sha],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ReleaseRequestError(
            f"expected base {request.expected_base_commit} is not an ancestor of {target_sha}"
        ) from exc

    changed = tuple(
        line
        for line in _run_git(
            root, "diff", "--name-only", request.expected_base_commit, target_sha
        ).splitlines()
        if line
    )
    if tuple(sorted(changed)) != request.allowed_release_delta:
        raise ReleaseRequestError(
            "release delta mismatch: "
            f"expected={list(request.allowed_release_delta)!r} actual={sorted(changed)!r}"
        )

    subprocess.run(
        ["git", "diff", "--check", request.expected_base_commit, target_sha],
        cwd=root,
        check=True,
    )

    if _source_version(root) != request.version:
        raise ReleaseRequestError("source version does not match release request")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{request.version}]" not in changelog:
        raise ReleaseRequestError("release changelog entry is missing")

    publish_text = (root / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    if "workflow_dispatch:" not in publish_text:
        raise ReleaseRequestError("publish workflow has no explicit dispatch trigger")
    expected_environment = f"    environment: {request.publisher['environment']}"
    if expected_environment not in publish_text:
        raise ReleaseRequestError("publish environment does not match request")
    if "PYPI_API_TOKEN" in publish_text:
        raise ReleaseRequestError("long-lived PyPI token path is forbidden")
    if "pypa/gh-action-pypi-publish@" not in publish_text:
        raise ReleaseRequestError("canonical PyPA Trusted Publisher action is missing")
    if _smoke_tools(root) != request.public_tools:
        raise ReleaseRequestError("installed MCP smoke tool inventory does not match request")

    request_digest = hashlib.sha256(request.path.read_bytes()).hexdigest()
    return {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "execute": True,
        "request_path": request.repo_path,
        "request_sha256": request_digest,
        "version": request.version,
        "tag": request.tag,
        "target_sha": target_sha,
        "expected_base_commit": request.expected_base_commit,
        "changed_files": list(request.allowed_release_delta),
        "publisher": request.publisher,
        "public_tools": list(request.public_tools),
    }


def pypi_version_exists(request: ReleaseRequest, *, timeout: int = 30) -> bool:
    url = PYPI_VERSION_URL.format(
        distribution=request.raw["distribution"], version=request.version
    )
    query = urllib.request.Request(
        url,
        headers={
            "Cache-Control": "no-cache",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(query, timeout=timeout) as response:
            metadata = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise ReleaseRequestError(f"PyPI preflight failed with HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ReleaseRequestError(f"PyPI preflight failed: {exc}") from exc
    info = metadata.get("info") if isinstance(metadata, dict) else None
    if not isinstance(info, dict) or str(info.get("version") or "") != request.version:
        raise ReleaseRequestError("PyPI returned malformed version metadata")
    return True


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download_sha256(url: str, *, timeout: int = 60) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for block in iter(lambda: response.read(1024 * 1024), b""):
                digest.update(block)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ReleaseRequestError(f"public artifact download failed: {exc}") from exc
    return digest.hexdigest()


def _job(rows: Iterable[dict[str, Any]], suffix: str) -> dict[str, Any]:
    matches = [
        row
        for row in rows
        if str(row.get("name") or "") == suffix
        or str(row.get("name") or "").endswith(f" / {suffix}")
    ]
    if len(matches) != 1:
        raise ReleaseRequestError(
            f"expected one workflow job ending with {suffix!r}, found {len(matches)}"
        )
    row = matches[0]
    if row.get("conclusion") != "success":
        raise ReleaseRequestError(
            f"workflow job {row.get('name')!r} is not successful: "
            f"{row.get('conclusion')!r}"
        )
    return row


def build_public_evidence(
    request: ReleaseRequest,
    *,
    target_sha: str,
    tag_object_sha: str,
    dist_dir: Path,
    jobs_path: Path,
    run_id: str,
    run_url: str,
) -> dict[str, Any]:
    if not SHA_RE.fullmatch(target_sha) or not SHA_RE.fullmatch(tag_object_sha):
        raise ReleaseRequestError("target/tag object SHA is invalid")
    jobs_payload = _read_json(jobs_path)
    rows = jobs_payload.get("jobs")
    if not isinstance(rows, list):
        raise ReleaseRequestError("workflow jobs payload is malformed")

    required_release = _job(rows, "required-release")
    publish = _job(rows, "publish")
    platforms = {
        "linux": _job(rows, "public-platform-smoke (ubuntu-latest)"),
        "macos": _job(rows, "public-platform-smoke (macos-latest)"),
        "windows": _job(rows, "public-platform-smoke (windows-latest)"),
    }

    local_artifacts = sorted(
        [
            *dist_dir.glob("*.whl"),
            *dist_dir.glob("*.tar.gz"),
        ],
        key=lambda path: path.name,
    )
    if len(local_artifacts) != 2:
        raise ReleaseRequestError(
            "expected exactly one wheel and one sdist, found "
            f"{[p.name for p in local_artifacts]!r}"
        )
    local = {path.name: _sha256(path) for path in local_artifacts}

    url = PYPI_VERSION_URL.format(
        distribution=request.raw["distribution"], version=request.version
    )
    metadata_request = urllib.request.Request(
        url,
        headers={"Cache-Control": "no-cache", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(metadata_request, timeout=30) as response:
            metadata = json.load(response)
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        json.JSONDecodeError,
    ) as exc:
        raise ReleaseRequestError(f"cannot fetch public PyPI metadata: {exc}") from exc

    urls = metadata.get("urls") if isinstance(metadata, dict) else None
    if not isinstance(urls, list):
        raise ReleaseRequestError("PyPI metadata does not contain artifact rows")
    public_rows = {
        str(row.get("filename")): row
        for row in urls
        if isinstance(row, dict)
        and row.get("packagetype") in {"bdist_wheel", "sdist"}
    }
    if set(public_rows) != set(local):
        raise ReleaseRequestError(
            "public artifact names differ from gated build: "
            f"local={sorted(local)!r} public={sorted(public_rows)!r}"
        )

    artifacts: dict[str, Any] = {}
    for filename, gated_sha in sorted(local.items()):
        row = public_rows[filename]
        metadata_sha = str((row.get("digests") or {}).get("sha256") or "")
        downloaded_sha = _download_sha256(str(row.get("url") or ""))
        if not metadata_sha or metadata_sha != downloaded_sha or gated_sha != downloaded_sha:
            raise ReleaseRequestError(
                f"artifact SHA mismatch for {filename}: "
                f"gated={gated_sha} metadata={metadata_sha} "
                f"downloaded={downloaded_sha}"
            )
        kind = "wheel" if filename.endswith(".whl") else "sdist"
        artifacts[kind] = {
            "filename": filename,
            "gated_sha256": gated_sha,
            "pypi_metadata_sha256": metadata_sha,
            "downloaded_sha256": downloaded_sha,
            "url": str(row.get("url") or ""),
        }

    def job_evidence(row: dict[str, Any]) -> dict[str, str]:
        return {
            "name": str(row.get("name") or ""),
            "conclusion": str(row.get("conclusion") or ""),
            "url": str(row.get("html_url") or row.get("url") or ""),
        }

    return {
        "schema_version": 1,
        "release": {
            "product": EXPECTED_PRODUCT,
            "distribution": EXPECTED_DISTRIBUTION,
            "version": request.version,
            "tag": request.tag,
            "maturity": "Beta",
        },
        "git": {
            "target_commit_sha": target_sha,
            "tag_object_sha": tag_object_sha,
            "reachable_from_main": True,
        },
        "publisher": {
            **request.publisher,
            "mode": "oidc",
            "workflow_run_id": str(run_id),
            "workflow_run_url": run_url,
            "required_release_job": job_evidence(required_release),
            "publish_job": job_evidence(publish),
        },
        "artifacts": artifacts,
        "public_smoke": {
            key: job_evidence(row) for key, row in sorted(platforms.items())
        },
        "mcp": {
            "expected_tools": list(request.public_tools),
            "tool_count": len(request.public_tools),
            "smoke_contract": "scripts/docs_mcp_stdio_smoke.py",
        },
        "request": {
            "path": request.repo_path,
            "sha256": hashlib.sha256(request.path.read_bytes()).hexdigest(),
            "source_prs": list(request.source_prs),
        },
        "public_artifact_status": "green",
    }


def _write_json(payload: dict[str, Any], output: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(rendered, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect")
    inspect.add_argument("--request", type=Path, required=True)

    preflight = sub.add_parser("preflight")
    preflight.add_argument("--request", type=Path, required=True)
    preflight.add_argument("--repo-root", type=Path, default=Path("."))
    preflight.add_argument("--target-sha", required=True)
    preflight.add_argument("--output", type=Path)

    absent = sub.add_parser("require-pypi-absent")
    absent.add_argument("--request", type=Path, required=True)

    evidence = sub.add_parser("build-evidence")
    evidence.add_argument("--request", type=Path, required=True)
    evidence.add_argument("--target-sha", required=True)
    evidence.add_argument("--tag-object-sha", required=True)
    evidence.add_argument("--dist-dir", type=Path, required=True)
    evidence.add_argument("--jobs-json", type=Path, required=True)
    evidence.add_argument("--run-id", required=True)
    evidence.add_argument("--run-url", required=True)
    evidence.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    request = load_request(args.request)
    if args.command == "inspect":
        _write_json(
            {
                "schema_version": REQUEST_SCHEMA_VERSION,
                "state": request.state,
                "execute": request.execute,
                "version": request.version,
                "tag": request.tag,
                "request_path": request.repo_path,
            },
            None,
        )
        return 0
    if args.command == "preflight":
        payload = validate_repository(
            request,
            root=args.repo_root.resolve(),
            target_sha=args.target_sha,
        )
        _write_json(payload, args.output)
        return 0
    if args.command == "require-pypi-absent":
        if pypi_version_exists(request):
            raise SystemExit(
                f"public {request.raw['distribution']}=={request.version} already "
                "exists; refusing duplicate release"
            )
        print(
            f"PyPI preflight: {request.raw['distribution']}=={request.version} "
            "is absent"
        )
        return 0
    if args.command == "build-evidence":
        payload = build_public_evidence(
            request,
            target_sha=args.target_sha,
            tag_object_sha=args.tag_object_sha,
            dist_dir=args.dist_dir,
            jobs_path=args.jobs_json,
            run_id=args.run_id,
            run_url=args.run_url,
        )
        _write_json(payload, args.output)
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())

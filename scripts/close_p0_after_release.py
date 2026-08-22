from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.3.1"
TAG = "v1.3.1"
EXPECTED_ARTIFACTS = {
    "doc_atlas-1.3.1-py3-none-any.whl",
    "doc_atlas-1.3.1.tar.gz",
}
EXPECTED_TOOLS = ["get_docs_context", "prepare_docs", "docs_status"]
CLOSURE_WORKFLOW = ROOT / ".github/workflows/close-p0-after-public-1.3.1.yml"
PREFLIGHT_TEST = ROOT / "tests/test_p0_release_repair_preflight.py"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def write(relative: str, content: str) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    if new in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(
            f"{label}: expected exactly one old block, found {text.count(old)}"
        )
    return text.replace(old, new, 1)


def load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_sha(value: str, *, label: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise SystemExit(f"{label} is not a full lowercase Git SHA: {value!r}")
    return value


def validate_artifacts(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict) or set(payload) != EXPECTED_ARTIFACTS:
        raise SystemExit(
            "public artifact evidence mismatch: "
            f"expected={sorted(EXPECTED_ARTIFACTS)} "
            f"actual={sorted(payload) if isinstance(payload, dict) else type(payload).__name__}"
        )
    result: dict[str, dict[str, Any]] = {}
    for filename, row in sorted(payload.items()):
        if not isinstance(row, dict):
            raise SystemExit(f"artifact row is not an object: {filename}")
        digest = str(row.get("sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise SystemExit(f"artifact SHA-256 is invalid: {filename}")
        size = row.get("size")
        if not isinstance(size, int) or size <= 0:
            raise SystemExit(f"artifact size is invalid: {filename}")
        url = str(row.get("url") or "")
        if not url.startswith("https://files.pythonhosted.org/"):
            raise SystemExit(f"artifact URL is not a PyPI file URL: {filename}")
        result[filename] = {
            "sha256": digest,
            "size": size,
            "url": url,
            "upload_time_iso_8601": row.get("upload_time_iso_8601"),
        }
    return result


def validate_jobs(payload: Any) -> dict[str, dict[str, Any]]:
    rows = payload.get("jobs", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        raise SystemExit("workflow jobs payload is malformed")
    jobs = {
        str(row.get("name")): row
        for row in rows
        if isinstance(row, dict) and str(row.get("name") or "")
    }
    required = {
        "required-release",
        "publish",
        "public-platform-smoke (ubuntu-latest)",
        "public-platform-smoke (macos-latest)",
        "public-platform-smoke (windows-latest)",
    }
    missing = sorted(required - jobs.keys())
    failed = sorted(
        name for name in required & jobs.keys()
        if jobs[name].get("conclusion") != "success"
    )
    if missing or failed:
        raise SystemExit(
            f"release job evidence incomplete: missing={missing} failed={failed}"
        )
    return jobs


def public_job_evidence(jobs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for platform in ("ubuntu-latest", "macos-latest", "windows-latest"):
        name = f"public-platform-smoke ({platform})"
        row = jobs[name]
        result[platform] = {
            "status": "success",
            "job_id": row.get("id"),
            "html_url": row.get("html_url"),
        }
    return result


def restore_oidc_only_publish_workflow() -> None:
    path = ROOT / ".github/workflows/publish.yml"
    text = path.read_text(encoding="utf-8")
    input_block = """      publisher_mode:
        description: Publication credential path
        required: true
        default: oidc
        type: choice
        options:
          - oidc
          - token
"""
    if input_block not in text:
        raise SystemExit("publish workflow is missing the reviewed publisher_mode block")
    text = text.replace(input_block, "", 1)

    environment_block = """    environment:
      name: ${{ inputs.publisher_mode == 'token' && 'release' || 'release-current' }}
"""
    if environment_block not in text:
        raise SystemExit("publish workflow is missing the reviewed dynamic environment")
    text = text.replace(environment_block, "    environment: release-current\n", 1)

    publish_block = """      - name: Publish to PyPI with OIDC
        if: inputs.publisher_mode != 'token'
        uses: pypa/gh-action-pypi-publish@ed0c53931b1dc9bd32cbe73a98c7f6766f8a527e # release/v1
      - name: Publish to PyPI with reviewed one-time token fallback
        if: inputs.publisher_mode == 'token'
        uses: pypa/gh-action-pypi-publish@ed0c53931b1dc9bd32cbe73a98c7f6766f8a527e # release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
"""
    oidc_block = """      - name: Publish to PyPI with OIDC
        uses: pypa/gh-action-pypi-publish@ed0c53931b1dc9bd32cbe73a98c7f6766f8a527e # release/v1
"""
    if publish_block not in text:
        raise SystemExit("publish workflow is missing the reviewed one-time publisher block")
    text = text.replace(publish_block, oidc_block, 1)
    path.write_text(text, encoding="utf-8")


def write_release_identity(
    *,
    target_sha: str,
    release_run_id: str,
    release_run_url: str,
    artifacts: dict[str, dict[str, Any]],
) -> None:
    wheel = artifacts["doc_atlas-1.3.1-py3-none-any.whl"]
    sdist = artifacts["doc_atlas-1.3.1.tar.gz"]
    write(
        "docs/release-identity.md",
        f"""# Release identity

## Current public release

The current verified public release is **DocAtlas {VERSION}**.

```text
product: DocAtlas
distribution: doc-atlas
source version: {VERSION}
immutable tag: {TAG}
release commit: {target_sha}
maturity: Beta
```

Canonical release workflow: `{release_run_id}` ({release_run_url}).

Public artifacts:

```text
doc_atlas-1.3.1-py3-none-any.whl
sha256 {wheel["sha256"]}

doc_atlas-1.3.1.tar.gz
sha256 {sdist["sha256"]}
```

The workflow downloaded the exact PyPI bytes, verified the PyPI metadata hashes,
performed a no-cache installed Docs MCP smoke, and passed the exact public package
on Linux, macOS, and Windows. The installed public tool inventory is exactly:

```text
get_docs_context
prepare_docs
docs_status
```

## Publisher authentication evidence

The intended long-lived publication path remains GitHub OIDC/Trusted Publishing
through `publish.yml` and environment `release-current`.

For this release only, the maintainer-authorized one-MR closure used the
historical repository/environment `PYPI_API_TOKEN` path after the earlier OIDC
attempt failed with `invalid-publisher`. The reviewed token branch was
non-automatic, exact-tag-bound, and removed from the canonical workflow
immediately after successful public verification. This is recorded as an
accepted operational risk, not represented as Trusted Publishing evidence.

## Superseded pre-public `v1.3.0` attempt

`v1.3.0` remains an immutable pre-public audit identity at
`42c3bf1fccc839dad4be4077b0b2c6a203f9bbac`. Workflow run `32541487735`
built and validated its artifacts, but PyPI rejected OIDC before upload. No
public `doc-atlas==1.3.0` release is claimed, and that tag must not be moved,
replaced, or reused.

## Claim boundary

Public release truth is closed for `{VERSION}`, while product maturity remains
**Beta**. Autonomous model evidence acquisition, real coding-task improvement,
and Context7 parity remain unproven P1/P2 questions.
""",
    )


def write_scorecard(
    *,
    target_sha: str,
    release_run_id: str,
    release_run_url: str,
    artifacts: dict[str, dict[str, Any]],
) -> None:
    wheel = artifacts["doc_atlas-1.3.1-py3-none-any.whl"]
    sdist = artifacts["doc_atlas-1.3.1.tar.gz"]
    write(
        "docs/public-truth-scorecard.md",
        f"""# P0 public-truth closure scorecard

Status: **CLOSED** — public `doc-atlas=={VERSION}` exists and the exact artifacts
and installed three-tool MCP surface passed public verification on Linux, macOS,
and Windows.

This is the single P0.6 closure record. `accepted_risk` never means that a
missing control exists.

| Public-truth row | State | Evidence |
|---|---|---|
| Release source identity | `green` | Immutable `{TAG}` resolves to `{target_sha}`; source, changelog, wheel, sdist, and public metadata agree on `{VERSION}`. |
| Branch protection | `accepted_risk` | Maintainer decision on 2026-08-21: remote `main` remains unprotected. Release ancestry and exact-tag checks are compensating controls, not branch protection. |
| Namespace / state isolation | `green` | Public installed smoke uses `DOCATLAS_HOME`, rejects implicit foreign `~/.docmancer` writes, and preserves the `docatlas` integration identity. |
| Installed agent contract | `green` | Public Docs MCP inventory is exactly `get_docs_context`, `prepare_docs`, `docs_status`; documentary support and local-source recovery remain distinct. |
| Publisher authentication | `accepted_risk` | Release `{VERSION}` used the reviewed one-time historical token fallback because the PyPI Trusted Publisher was not configured. The token path removed itself after success; future canonical publication is OIDC-only through `release-current`. |
| Exact public artifact identity | `green` | Workflow [{release_run_id}]({release_run_url}) verified public bytes. Wheel `{wheel["sha256"]}`; sdist `{sdist["sha256"]}`. |
| Exact public MCP behavior | `green` | A no-cache installation of `doc-atlas=={VERSION}` passed `doc-atlas --version`, stdio initialization, and exact three-tool inventory. |
| Cross-platform public install | `green` | The exact public package passed `public-platform-smoke` on `ubuntu-latest`, `macos-latest`, and `windows-latest`. |
| Product claim boundary | `green` | Public maturity remains **Beta**. Autonomous live agent behavior, coding-task improvement, and Context7 parity remain unproven. |

## Closure rule result

Every row is now either `green` or an explicitly documented `accepted_risk`;
no row is `pending`. P0 is closed and the active roadmap may proceed to P1.
""",
    )


def update_roadmap(*, release_run_id: str, release_run_url: str) -> None:
    path = ROOT / "roadmap/README.md"
    text = path.read_text(encoding="utf-8")

    old_truth = (
        "| Public release truth for current `main` | "
        "Incomplete until a new public release is published and verified |"
    )
    new_truth = (
        f"| Public release truth for current `main` | Verified public "
        f"`doc-atlas=={VERSION}` with exact artifacts and Linux/macOS/Windows "
        f"installed MCP smoke |"
    )
    text = replace_once(text, old_truth, new_truth, label="roadmap public truth")

    p0_intro = (
        "# P0 — PUBLIC TRUTH\n\n"
        "P0 establishes one trustworthy public product before further R&D."
    )
    p0_closed = (
        "# P0 — PUBLIC TRUTH\n\n"
        f"**Status: CLOSED.** Public `{VERSION}` evidence is recorded in "
        "`docs/public-truth-scorecard.md` and "
        "`docs/release-evidence/v1.3.1-public.json`.\n\n"
        "P0 establishes one trustworthy public product before further R&D."
    )
    text = replace_once(text, p0_intro, p0_closed, label="roadmap P0 status")

    p05 = "## P0.5 — Publish and verify public `1.3.1`\n"
    p05_closed = (
        "## P0.5 — Publish and verify public `1.3.1`\n\n"
        f"**Status: closed.** Canonical release workflow "
        f"[{release_run_id}]({release_run_url}) published and verified the exact "
        "public package and cross-platform installed MCP surface.\n"
    )
    text = replace_once(text, p05, p05_closed, label="roadmap P0.5 status")

    p06 = "## P0.6 — Public-truth closure scorecard\n"
    p06_closed = (
        "## P0.6 — Public-truth closure scorecard\n\n"
        "**Status: closed.** Every scorecard row is `green` or an explicit "
        "`accepted_risk`; no row remains `pending`.\n"
    )
    text = replace_once(text, p06, p06_closed, label="roadmap P0.6 status")

    p1 = (
        "# P1 — AGENT TRUTH\n\n"
        "P1 asks whether a real coding model can acquire the intended evidence "
        "through the installed public product."
    )
    p1_active = (
        "# P1 — AGENT TRUTH\n\n"
        "**Current next step: P1.1 — Installed-MCP live benchmark harness.**\n\n"
        "P1 asks whether a real coding model can acquire the intended evidence "
        "through the installed public product."
    )
    text = replace_once(text, p1, p1_active, label="roadmap P1 activation")

    freeze = "## P0 freeze rule\n\nUntil P0 closes,"
    freeze_closed = (
        "## P0 freeze rule\n\n"
        f"P0 closed with verified public `{VERSION}`. The following rule is "
        "retained as historical policy for the pre-closure interval:\n\n"
        "Until P0 closes,"
    )
    text = replace_once(text, freeze, freeze_closed, label="roadmap freeze status")
    path.write_text(text, encoding="utf-8")


def update_release_checklist() -> None:
    path = ROOT / "docs/RELEASE_CHECKLIST.md"
    text = path.read_text(encoding="utf-8")
    old_environment = (
        "- [ ] The protected `release` environment approval is granted only "
        "after all artifact jobs pass; this is the explicit human publication "
        "authorization."
    )
    new_environment = (
        "- [ ] The protected `release-current` environment approval is granted "
        "only after all artifact jobs pass; this is the explicit human "
        "publication authorization."
    )
    if old_environment in text:
        text = text.replace(old_environment, new_environment, 1)
    elif new_environment not in text:
        raise SystemExit("release checklist environment line was not found")
    trusted = (
        "- [ ] Trusted Publishing is configured for the repository/environment "
        "in PyPI; no long-lived PyPI token is stored."
    )
    replacement = (
        "- [ ] Trusted Publishing is configured for the repository/environment "
        "in PyPI; no long-lived PyPI token is stored. Release 1.3.1 is the "
        "documented one-time exception: its reviewed exact-tag token fallback "
        "self-erased after public verification and remains an `accepted_risk` "
        "in the P0.6 scorecard."
    )
    if trusted in text:
        text = text.replace(trusted, replacement, 1)
    elif replacement not in text:
        raise SystemExit("release checklist Trusted Publishing line was not found")
    path.write_text(text, encoding="utf-8")


def write_evidence(
    *,
    target_sha: str,
    tag_object_sha: str,
    peeled_commit_sha: str,
    release_run_id: str,
    release_run_url: str,
    artifacts: dict[str, dict[str, Any]],
    jobs: dict[str, dict[str, Any]],
) -> None:
    payload = {
        "schema_version": 1,
        "product": "DocAtlas",
        "distribution": "doc-atlas",
        "version": VERSION,
        "tag": TAG,
        "tag_object_sha": tag_object_sha,
        "target_commit_sha": target_sha,
        "peeled_commit_sha": peeled_commit_sha,
        "release_workflow": {
            "id": int(release_run_id),
            "url": release_run_url,
            "required_release": "success",
            "publish": "success",
            "publisher_mode": "reviewed_one_time_token_fallback",
        },
        "artifacts": artifacts,
        "public_install": {
            "pip_cache": "disabled",
            "mcp_tools": EXPECTED_TOOLS,
            "platforms": public_job_evidence(jobs),
        },
        "accepted_risks": [
            "remote_main_unprotected",
            "v1.3.1_one_time_token_publisher_fallback",
        ],
        "product_maturity": "Beta",
    }
    if payload["target_commit_sha"] != payload["peeled_commit_sha"]:
        raise SystemExit("tag peeled commit does not match the release target")
    write(
        "docs/release-evidence/v1.3.1-public.json",
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
    )


def write_final_tests(
    *,
    target_sha: str,
    release_run_id: str,
    artifacts: dict[str, dict[str, Any]],
) -> None:
    wheel_sha = artifacts["doc_atlas-1.3.1-py3-none-any.whl"]["sha256"]
    sdist_sha = artifacts["doc_atlas-1.3.1.tar.gz"]["sha256"]
    write(
        "tests/test_patch_release_identity.py",
        f"""import json
from pathlib import Path

from docmancer._version import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_public_patch_release_identity_is_exact_and_beta():
    assert __version__ == "{VERSION}"
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.index("## 1.3.1") < changelog.index("## 1.3.0")

    evidence = json.loads(
        (ROOT / "docs/release-evidence/v1.3.1-public.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["target_commit_sha"] == "{target_sha}"
    assert evidence["peeled_commit_sha"] == "{target_sha}"
    assert evidence["release_workflow"]["id"] == {int(release_run_id)}
    assert evidence["release_workflow"]["publisher_mode"] == (
        "reviewed_one_time_token_fallback"
    )
    assert evidence["artifacts"]["doc_atlas-1.3.1-py3-none-any.whl"]["sha256"] == (
        "{wheel_sha}"
    )
    assert evidence["artifacts"]["doc_atlas-1.3.1.tar.gz"]["sha256"] == (
        "{sdist_sha}"
    )
    assert evidence["public_install"]["mcp_tools"] == [
        "get_docs_context",
        "prepare_docs",
        "docs_status",
    ]
    assert set(evidence["public_install"]["platforms"]) == {{
        "ubuntu-latest",
        "macos-latest",
        "windows-latest",
    }}
    assert all(
        row["status"] == "success"
        for row in evidence["public_install"]["platforms"].values()
    )
    assert evidence["product_maturity"] == "Beta"


def test_canonical_publish_workflow_is_oidc_only_after_closure():
    workflow = (ROOT / ".github/workflows/publish.yml").read_text(
        encoding="utf-8"
    )
    assert "for example v1.3.1" in workflow
    assert "    environment: release-current" in workflow
    assert "publisher_mode:" not in workflow
    assert "PYPI_API_TOKEN" not in workflow
    assert "Publish to PyPI with OIDC" in workflow
""",
    )

    write(
        "tests/test_public_release_closure.py",
        """import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_p0_scorecard_is_closed_without_hiding_accepted_risks():
    scorecard = (ROOT / "docs/public-truth-scorecard.md").read_text(
        encoding="utf-8"
    )
    assert "Status: **CLOSED**" in scorecard
    assert "`pending`" not in "\\n".join(
        line for line in scorecard.splitlines() if line.startswith("| ")
    )
    assert "Branch protection | `accepted_risk`" in scorecard
    assert "Publisher authentication | `accepted_risk`" in scorecard
    assert "Exact public artifact identity | `green`" in scorecard
    assert "Exact public MCP behavior | `green`" in scorecard
    assert "Cross-platform public install | `green`" in scorecard
    assert "Product claim boundary | `green`" in scorecard


def test_public_release_evidence_is_bounded_and_complete():
    evidence = json.loads(
        (ROOT / "docs/release-evidence/v1.3.1-public.json").read_text(
            encoding="utf-8"
        )
    )
    assert set(evidence["artifacts"]) == {
        "doc_atlas-1.3.1-py3-none-any.whl",
        "doc_atlas-1.3.1.tar.gz",
    }
    assert evidence["release_workflow"]["required_release"] == "success"
    assert evidence["release_workflow"]["publish"] == "success"
    assert evidence["accepted_risks"] == [
        "remote_main_unprotected",
        "v1.3.1_one_time_token_publisher_fallback",
    ]


def test_one_shot_release_carriers_are_absent_after_closure():
    forbidden = [
        *ROOT.glob(".github/workflows/materialize-*"),
        *ROOT.glob("scripts/materialize_*"),
        ROOT / ".github/workflows/close-p0-after-public-1.3.1.yml",
        ROOT / "scripts/close_p0_after_release.py",
        ROOT / "tests/test_p0_release_repair_preflight.py",
    ]
    assert not [path for path in forbidden if path.exists()]
""",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-sha", required=True)
    parser.add_argument("--tag-object-sha", required=True)
    parser.add_argument("--peeled-commit-sha", required=True)
    parser.add_argument("--release-run-id", required=True)
    parser.add_argument("--release-run-url", required=True)
    parser.add_argument("--artifacts-json", required=True)
    parser.add_argument("--jobs-json", required=True)
    args = parser.parse_args()

    target_sha = validate_sha(args.target_sha, label="target_sha")
    tag_object_sha = validate_sha(args.tag_object_sha, label="tag_object_sha")
    peeled_commit_sha = validate_sha(
        args.peeled_commit_sha, label="peeled_commit_sha"
    )
    if target_sha != peeled_commit_sha:
        raise SystemExit("release target and peeled tag commit differ")
    if not args.release_run_id.isdigit():
        raise SystemExit("release_run_id must be numeric")
    expected_url = (
        f"https://github.com/Vanilla1999/DocAtlas/actions/runs/"
        f"{args.release_run_id}"
    )
    if args.release_run_url != expected_url:
        raise SystemExit("release_run_url does not match release_run_id")

    version_text = read("docmancer/_version.py")
    if '__version__ = "1.3.1"' not in version_text:
        raise SystemExit("source version is not 1.3.1")

    artifacts = validate_artifacts(load_json(args.artifacts_json))
    jobs = validate_jobs(load_json(args.jobs_json))

    write_evidence(
        target_sha=target_sha,
        tag_object_sha=tag_object_sha,
        peeled_commit_sha=peeled_commit_sha,
        release_run_id=args.release_run_id,
        release_run_url=args.release_run_url,
        artifacts=artifacts,
        jobs=jobs,
    )
    write_release_identity(
        target_sha=target_sha,
        release_run_id=args.release_run_id,
        release_run_url=args.release_run_url,
        artifacts=artifacts,
    )
    write_scorecard(
        target_sha=target_sha,
        release_run_id=args.release_run_id,
        release_run_url=args.release_run_url,
        artifacts=artifacts,
    )
    update_roadmap(
        release_run_id=args.release_run_id,
        release_run_url=args.release_run_url,
    )
    update_release_checklist()
    restore_oidc_only_publish_workflow()
    write_final_tests(
        target_sha=target_sha,
        release_run_id=args.release_run_id,
        artifacts=artifacts,
    )

    if CLOSURE_WORKFLOW.exists():
        CLOSURE_WORKFLOW.unlink()
    if PREFLIGHT_TEST.exists():
        PREFLIGHT_TEST.unlink()
    Path(__file__).unlink()


if __name__ == "__main__":
    main()

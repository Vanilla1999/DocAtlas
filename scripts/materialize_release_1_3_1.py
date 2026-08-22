from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def write(relative: str, content: str) -> None:
    (ROOT / relative).write_text(content, encoding="utf-8")


def replace_all(relative: str, old: str, new: str) -> None:
    text = read(relative)
    if old not in text and new in text:
        return
    if old not in text:
        raise SystemExit(f"expected {old!r} in {relative}")
    write(relative, text.replace(old, new))


version_path = ROOT / "docmancer/_version.py"
version_text = version_path.read_text(encoding="utf-8")
if '__version__ = "1.3.1"' not in version_text:
    if '__version__ = "1.3.0"' not in version_text:
        raise SystemExit("unexpected source version")
    version_path.write_text(
        version_text.replace('__version__ = "1.3.0"', '__version__ = "1.3.1"', 1),
        encoding="utf-8",
    )

changelog_path = ROOT / "CHANGELOG.md"
changelog = changelog_path.read_text(encoding="utf-8")
if not re.search(r"^## \[?1\.3\.1\]?\b", changelog, re.MULTILINE):
    section = """## 1.3.1 - 2026-08-22

### Fixed

- Made project-specific documentation failures recoverable without converting them into documentary support: one bounded rephrase is allowed, then the coding agent may inspect local source/tests when no authoritative hard stop exists.
- Added exact named-document recovery from the active SQLite generation when ordinary lexical retrieval misses the explicitly selected source.
- Hardened `edit_ready` so only a complete, coding-agent-owned, non-automatic local `code_search` handoff can continue editing while the documentation claim remains unsupported.
- Preserved fail-closed behavior for authoritative conflicts, stale/wrong-scope evidence, confirmation boundaries, unsafe actions, and incomplete source-search handoffs.

### Release identity

- `v1.3.0` remains an immutable pre-public attempt. Its gated build passed, but PyPI rejected OIDC before upload with `invalid-publisher`; no public `doc-atlas==1.3.0` artifact is claimed.
- `1.3.1` is the replacement public candidate. Publication uses the canonical `publish.yml` workflow with the new `release-current` environment so the failed `v1.3.0` run cannot be accidentally resumed under the new Trusted Publisher identity.

"""
    match = re.search(r"^## \[?1\.3\.0\]?\b", changelog, re.MULTILINE)
    if not match:
        raise SystemExit("1.3.0 changelog anchor not found")
    changelog = changelog[: match.start()] + section + changelog[match.start() :]
    changelog_path.write_text(changelog, encoding="utf-8")

publish = read(".github/workflows/publish.yml")
publish = publish.replace("Existing release tag (for example v1.3.0)", "Existing release tag (for example v1.3.1)")
publish = publish.replace("    environment: release\n", "    environment: release-current\n")
if "environment: release-current" not in publish:
    raise SystemExit("publish workflow environment was not updated")
write(".github/workflows/publish.yml", publish)

write(
    "docs/release-identity.md",
    """# Release identity

## Current public candidate

The current source release candidate is **DocAtlas 1.3.1**.

Canonical identity:

```text
product: DocAtlas
distribution: doc-atlas
source version: 1.3.1
intended tag: v1.3.1
maturity: Beta
```

The tag is created only after the release-preparation PR is merged and all required CI/release gates are green. It must point to that exact reviewed `main` commit and must never be moved.

## Superseded pre-public `v1.3.0` attempt

`v1.3.0` is retained as an immutable audit identity at commit `42c3bf1fccc839dad4be4077b0b2c6a203f9bbac`. Canonical workflow run `32541487735` built and validated the wheel/sdist, but PyPI rejected the OIDC publisher with `invalid-publisher` before upload. Therefore:

- no public `doc-atlas==1.3.0` release is claimed;
- the tag must not be moved, replaced, or reused;
- the failed publish job must not be rerun after configuring the replacement publisher;
- its artifact hashes are pre-public engineering evidence only, not public-release evidence.

Recorded gated artifacts from that failed attempt:

```text
doc_atlas-1.3.0-py3-none-any.whl
sha256 2e1a0f58e34ea9c175b8d93839a6dcc8a54a7e36d4329157f9378791a0341e26

doc_atlas-1.3.0.tar.gz
sha256 e5bb4eb1f2b3221bcd3e8e9db719fe8f11596a88bd000e3d922bd6826c6683ab
```

## Trusted Publisher identity for 1.3.1+

Configure the PyPI project `doc-atlas` with exactly:

```text
owner: Vanilla1999
repository: DocAtlas
workflow filename: publish.yml
environment: release-current
```

The new environment name intentionally differs from the failed `v1.3.0` run (`release`). Publication still uses GitHub OIDC/Trusted Publishing and no long-lived PyPI token.

## Claim boundary

Until the exact public version is downloadable and passes the post-publish Linux/macOS/Windows MCP smoke, release truth remains incomplete and product maturity remains **Beta**.
""",
)

write(
    "docs/public-truth-scorecard.md",
    """# P0 public-truth closure scorecard

Status: **INCOMPLETE** — the reviewed `1.3.1` source candidate is being prepared, but the exact public PyPI release and post-publish verification do not exist yet.

This document is the P0.6 closure record. It distinguishes proven public truth, pending public evidence, and explicitly accepted operational risk. `accepted_risk` never means that the missing control exists.

## Superseded attempt

The immutable `v1.3.0` attempt at `42c3bf1fccc839dad4be4077b0b2c6a203f9bbac` reached canonical workflow run `32541487735`. Build, wheel/sdist/install gates and provenance passed, but PyPI rejected OIDC with `invalid-publisher` before upload. Its two gated SHA-256 values are recorded in `docs/release-identity.md`; they are not public-artifact closure evidence and the failed job must not be resumed.

| Public-truth row | State | Evidence / closure requirement |
|---|---|---|
| Release source identity | `green` | Source, changelog, build metadata, release docs, and workflow examples identify `1.3.1`; `v1.3.0` remains a superseded pre-public audit tag. |
| Branch protection | `accepted_risk` | Maintainer decision on 2026-08-21: do not activate remote `protect-main`. The release workflow instead requires the tag commit to be reachable from remote `main`. |
| Namespace / state isolation | `green` | Fresh release smoke uses `DOCATLAS_HOME`, removes inherited `DOCMANCER_HOME`, checks `docatlas` MCP registration identity, and rejects implicit foreign `~/.docmancer` writes. |
| Installed agent contract | `green` | The default public Docs MCP inventory remains exactly `get_docs_context`, `prepare_docs`, `docs_status`; documentary support stays fail closed while bounded local-source recovery is explicitly separated from support. |
| Trusted Publisher identity | `pending` | Configure PyPI `doc-atlas` for owner `Vanilla1999`, repository `DocAtlas`, workflow `publish.yml`, environment `release-current`; do not rerun the failed `v1.3.0` job. |
| Exact public artifact identity | `pending` | After publication, record immutable `v1.3.1`, PyPI wheel/sdist filenames, gated SHA-256 values, downloaded public SHA-256 values, and the successful publish workflow run. |
| Exact public MCP behavior | `pending` | No-cache install of `doc-atlas==1.3.1` from public PyPI must pass installed Docs MCP stdio smoke and exact three-tool inventory. |
| Cross-platform public install | `pending` | The exact public package must pass post-publish smoke on Linux, macOS, and Windows. Pre-public PR platform smoke is supporting evidence only. |
| Product claim boundary | `green` | Public maturity remains **Beta**. Autonomous live evidence planning, real coding-task improvement, and Context7 parity remain unproven and belong to P1/P2. |

## Closure rule

P0 closes only when every `pending` row is replaced by concrete `green` evidence. The `accepted_risk` branch-protection row remains visible and does not become proof that protection exists.
""",
)

roadmap_path = ROOT / "roadmap/README.md"
roadmap = roadmap_path.read_text(encoding="utf-8").replace("1.3.0", "1.3.1")
anchor = "## P0.5 — Publish and verify public `1.3.1`\n"
note = """

The immutable `v1.3.0` tag records a superseded pre-public attempt whose OIDC upload failed before publication. It must not be moved or rerun. `1.3.1` is the replacement public candidate because current `main` contains reviewed recovery fixes that are not part of that old tag.
"""
if note.strip() not in roadmap:
    if anchor not in roadmap:
        raise SystemExit("P0.5 roadmap anchor not found")
    roadmap = roadmap.replace(anchor, anchor + note, 1)
roadmap_path.write_text(roadmap, encoding="utf-8")

for relative in (
    "README.md",
    "docs/RELEASE_CHECKLIST.md",
    "tests/docs/test_user_facing_docs_branding.py",
    "tests/test_release_gate.py",
):
    path = ROOT / relative
    if path.exists():
        path.write_text(path.read_text(encoding="utf-8").replace("1.3.0", "1.3.1"), encoding="utf-8")

identity_test = ROOT / "tests/test_patch_release_identity.py"
identity_test.write_text(
    '''from pathlib import Path

from docmancer._version import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_patch_release_identity_is_single_source_and_preserves_failed_tag_audit():
    assert __version__ == "1.3.1"
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.index("## 1.3.1") < changelog.index("## 1.3.0")

    identity = (ROOT / "docs/release-identity.md").read_text(encoding="utf-8")
    assert "current source release candidate is **DocAtlas 1.3.1**" in identity
    assert "v1.3.0" in identity
    assert "must not be moved, replaced, or reused" in identity
    assert "invalid-publisher" in identity
    assert "environment: release-current" in identity

    roadmap = (ROOT / "roadmap/README.md").read_text(encoding="utf-8")
    assert "P0.5 — Publish and verify public `1.3.1`" in roadmap
    assert "superseded pre-public attempt" in roadmap

    scorecard = (ROOT / "docs/public-truth-scorecard.md").read_text(encoding="utf-8")
    assert "Status: **INCOMPLETE**" in scorecard
    assert "Trusted Publisher identity | `pending`" in scorecard
    assert "doc-atlas==1.3.1" in scorecard


def test_publish_workflow_uses_replacement_identity_not_failed_environment():
    workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    assert "for example v1.3.1" in workflow
    assert "    environment: release-current" in workflow
    assert "    environment: release\n" not in workflow
''',
    encoding="utf-8",
)

from __future__ import annotations

import re
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def write(relative: str, content: str) -> None:
    (ROOT / relative).write_text(content, encoding="utf-8")


def replace_once(relative: str, old: str, new: str) -> None:
    text = read(relative)
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"expected exactly one replacement in {relative}: "
            f"count={count}, old={old!r}"
        )
    write(relative, text.replace(old, new, 1))


def replace_function(relative: str, name: str, replacement: str) -> None:
    text = read(relative)
    pattern = re.compile(
        rf"^def {re.escape(name)}\(.*?(?=^def |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise SystemExit(
            f"expected exactly one function {name!r} in {relative}, "
            f"found {len(matches)}"
        )
    match = matches[0]
    write(relative, text[: match.start()] + replacement.rstrip() + "\n\n\n" + text[match.end() :])


# Reuse the already-reviewed release-preparation transformation that was
# accidentally committed as a carrier instead of being materialized.
runpy.run_path(str(ROOT / "scripts/materialize_release_1_3_1.py"), run_name="__main__")

# Keep Keep-a-Changelog formatting aligned with the historical file.
replace_once(
    "CHANGELOG.md",
    "## 1.3.1 - 2026-08-22\n",
    "## [1.3.1] - 2026-08-22\n",
)

# OIDC remains the default and canonical long-lived path.  The token path is an
# explicit, maintainer-authorized one-release escape hatch using the historical
# protected `release` environment.  The post-public closure materializer removes
# this branch from publish.yml after exact public verification succeeds.
publish = read(".github/workflows/publish.yml")
input_anchor = """      tag:
        description: Existing release tag (for example v1.3.1)
        required: true
        type: string
"""
input_block = input_anchor + """      publisher_mode:
        description: Publication credential path
        required: true
        default: oidc
        type: choice
        options:
          - oidc
          - token
"""
if "      publisher_mode:\n" not in publish:
    if publish.count(input_anchor) != 1:
        raise SystemExit("publish workflow tag input anchor is not unique")
    publish = publish.replace(input_anchor, input_block, 1)

environment_old = "    environment: release-current\n"
environment_new = """    environment:
      name: ${{ inputs.publisher_mode == 'token' && 'release' || 'release-current' }}
"""
if environment_new not in publish:
    if publish.count(environment_old) != 1:
        raise SystemExit("publish environment anchor is not unique")
    publish = publish.replace(environment_old, environment_new, 1)

publish_old = """      - uses: pypa/gh-action-pypi-publish@ed0c53931b1dc9bd32cbe73a98c7f6766f8a527e # release/v1
"""
publish_new = """      - name: Publish to PyPI with OIDC
        if: inputs.publisher_mode != 'token'
        uses: pypa/gh-action-pypi-publish@ed0c53931b1dc9bd32cbe73a98c7f6766f8a527e # release/v1
      - name: Publish to PyPI with reviewed one-time token fallback
        if: inputs.publisher_mode == 'token'
        uses: pypa/gh-action-pypi-publish@ed0c53931b1dc9bd32cbe73a98c7f6766f8a527e # release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
"""
if publish_new not in publish:
    if publish.count(publish_old) != 1:
        raise SystemExit("PyPI publish action anchor is not unique")
    publish = publish.replace(publish_old, publish_new, 1)
write(".github/workflows/publish.yml", publish)

identity_path = ROOT / "docs/release-identity.md"
identity = identity_path.read_text(encoding="utf-8")
closure_section = """
## One-MR closure authorization

The canonical long-lived publisher remains OIDC through `publish.yml` and the
`release-current` environment. For the exact `v1.3.1` recovery only, this
reviewed merge request carries a one-time token fallback through the historical
protected `release` environment because the earlier OIDC attempt proved that the
PyPI Trusted Publisher identity is not configured.

The fallback is non-default, exact-tag-bound, refuses an existing public
`1.3.1`, and is exercised only after the merged release commit reports green
`required-ci`. The same one-shot workflow requires public wheel/sdist byte
verification, no-cache installed MCP smoke, and Linux/macOS/Windows success,
then removes the token branch and its own carrier before recording P0 closure.
If `PYPI_API_TOKEN` is absent or invalid, publication fails closed and P0 remains
incomplete.
"""
if "## One-MR closure authorization" not in identity:
    marker = "## Claim boundary\n"
    if identity.count(marker) != 1:
        raise SystemExit("release identity claim-boundary anchor is not unique")
    identity = identity.replace(marker, closure_section + "\n" + marker, 1)
    identity_path.write_text(identity, encoding="utf-8")

scorecard_path = ROOT / "docs/public-truth-scorecard.md"
scorecard = scorecard_path.read_text(encoding="utf-8")
trusted_row = (
    "| Trusted Publisher identity | `pending` | Configure PyPI `doc-atlas` for "
    "owner `Vanilla1999`, repository `DocAtlas`, workflow `publish.yml`, "
    "environment `release-current`; do not rerun the failed `v1.3.0` job. |"
)
publisher_row = (
    "| Publisher authentication | `pending` | Canonical OIDC through "
    "`release-current` remains preferred. This exact `v1.3.1` recovery may use "
    "the reviewed one-time historical `release` / `PYPI_API_TOKEN` fallback; "
    "closure requires its self-removal and records the exception as "
    "`accepted_risk`. |"
)
if publisher_row not in scorecard:
    if scorecard.count(trusted_row) != 1:
        raise SystemExit("scorecard publisher row is not unique")
    scorecard = scorecard.replace(trusted_row, publisher_row, 1)
    scorecard_path.write_text(scorecard, encoding="utf-8")

checklist_path = ROOT / "docs/RELEASE_CHECKLIST.md"
checklist = checklist_path.read_text(encoding="utf-8")
checklist = checklist.replace(
    "- [ ] The protected `release` environment approval is granted only after "
    "all artifact jobs pass; this is the explicit human publication authorization.",
    "- [ ] The protected `release-current` environment is the canonical OIDC "
    "publisher. The exact `v1.3.1` recovery may select the historical protected "
    "`release` environment only through the reviewed one-time token mode.",
)
checklist = checklist.replace(
    "- [ ] Trusted Publishing is configured for the repository/environment in "
    "PyPI; no long-lived PyPI token is stored.",
    "- [ ] Trusted Publishing is the normal publication path. Release `1.3.1` "
    "has one reviewed exception: if OIDC remains externally unconfigured, an "
    "existing protected-environment token may publish the exact immutable tag; "
    "the workflow must self-remove that path after public verification and "
    "record it as `accepted_risk`.",
)
checklist = checklist.replace(
    "- [ ] A maintainer creates the immutable version tag from the reviewed "
    "release commit, then manually dispatches `Release artifact gate and "
    "publish` with that exact tag.",
    "- [ ] A maintainer-authorized workflow creates or idempotently verifies the "
    "immutable version tag at the reviewed release commit and dispatches "
    "`Release artifact gate and publish` with that exact tag only after "
    "`required-ci` is green.",
)
checklist_path.write_text(checklist, encoding="utf-8")

replace_function(
    "tests/test_release_gate.py",
    "test_publish_workflow_is_manual_build_once_and_oidc",
    '''def test_publish_workflow_is_manual_build_once_and_oidc() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    trigger_block = text.split("\\non:\\n", 1)[1].split("\\npermissions:\\n", 1)[0]
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
    assert "publisher_mode:" in text
    assert "default: oidc" in text
    assert "Publish to PyPI with OIDC" in text
    assert "Publish to PyPI with reviewed one-time token fallback" in text
    assert "password: ${{ secrets.PYPI_API_TOKEN }}" in text
    assert "inputs.publisher_mode == 'token'" in text
    assert "inputs.publisher_mode != 'token'" in text
    assert "inputs.publisher_mode == 'token' && 'release' || 'release-current'" in text
    assert "if: github.event_name == 'workflow_dispatch'" in text
    assert "refs/tags/${{ inputs.tag }}" in text
    for line in text.splitlines():
        if "uses:" in line:
            ref = line.split("@", 1)[1].split()[0]
            assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref)''',
)

replace_function(
    "tests/docs/test_user_facing_docs_branding.py",
    "test_maturity_docs_name_the_remaining_stable_release_gates",
    '''def test_maturity_docs_name_the_remaining_stable_release_gates():
    brief = (ROOT / "docs" / "DOCMANCER_PRODUCT_BRIEF.md").read_text(encoding="utf-8")
    checklist = (ROOT / "docs" / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8")
    release_identity = (ROOT / "docs" / "release-identity.md").read_text(encoding="utf-8")
    scorecard = (ROOT / "docs" / "public-truth-scorecard.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "roadmap" / "README.md").read_text(encoding="utf-8")
    history = (ROOT / "roadmap" / "history" / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    version_text = (ROOT / "docmancer" / "_version.py").read_text(encoding="utf-8")
    source_version = re.search(r'__version__\\s*=\\s*["\\\']([^"\\\']+)', version_text)
    historical_commit = "d565d8e75af2cbc56bc00fdc9df19dd1ae66863a"

    assert source_version is not None
    assert source_version.group(1) == "1.3.1"
    assert "Task 15" in brief
    assert "Task 14" in brief
    assert "post-publish" in brief
    assert "Task 14" in checklist
    assert "# P0 — PUBLIC TRUTH" in roadmap
    assert roadmap.index("# P0 — PUBLIC TRUTH") < roadmap.index("# P1 — AGENT TRUTH") < roadmap.index("# P2 — PRODUCT TRUTH")
    assert "Agent Developer 0/11 first-divergence atlas" in roadmap
    assert "Agent Contract v2 ablation" in roadmap
    assert "Real-repository coding benchmark" in roadmap
    assert historical_commit in roadmap
    assert historical_commit in history
    assert f"git show {historical_commit}:roadmap/README.md" in history
    assert "current source release candidate is **DocAtlas 1.3.1**" in release_identity
    assert "v1.3.0" in release_identity
    assert "invalid-publisher" in release_identity
    assert "release-current" in release_identity
    assert "one-time token fallback" in release_identity
    assert "Status: **INCOMPLETE**" in scorecard
    assert "Exact public artifact identity | `pending`" in scorecard
    assert "Cross-platform public install | `pending`" in scorecard
    assert "## [1.3.1] - 2026-08-22" in changelog
    assert "P0 public truth" in checklist
    assert "P1 agent truth" in checklist
    assert "P2 product truth" in checklist''',
)

write(
    "tests/test_patch_release_identity.py",
    '''from pathlib import Path

from docmancer._version import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_patch_release_identity_is_single_source_and_preserves_failed_tag_audit():
    assert __version__ == "1.3.1"
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.index("## [1.3.1]") < changelog.index("## [1.3.0]")

    identity = (ROOT / "docs/release-identity.md").read_text(encoding="utf-8")
    assert "current source release candidate is **DocAtlas 1.3.1**" in identity
    assert "v1.3.0" in identity
    assert "must not be moved, replaced, or reused" in identity
    assert "invalid-publisher" in identity
    assert "environment: release-current" in identity
    assert "one-time token fallback" in identity

    roadmap = (ROOT / "roadmap/README.md").read_text(encoding="utf-8")
    assert "P0.5 — Publish and verify public `1.3.1`" in roadmap
    assert "superseded pre-public attempt" in roadmap

    scorecard = (ROOT / "docs/public-truth-scorecard.md").read_text(encoding="utf-8")
    assert "Status: **INCOMPLETE**" in scorecard
    assert "Publisher authentication | `pending`" in scorecard
    assert "doc-atlas==1.3.1" in scorecard


def test_publish_workflow_defaults_to_oidc_and_bounds_the_release_exception():
    workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    assert "for example v1.3.1" in workflow
    assert "publisher_mode:" in workflow
    assert "default: oidc" in workflow
    assert "inputs.publisher_mode == 'token' && 'release' || 'release-current'" in workflow
    assert "Publish to PyPI with OIDC" in workflow
    assert "Publish to PyPI with reviewed one-time token fallback" in workflow
    assert "password: ${{ secrets.PYPI_API_TOKEN }}" in workflow
''',
)

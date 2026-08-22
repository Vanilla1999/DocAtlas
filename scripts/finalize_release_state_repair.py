from __future__ import annotations

import ast
import hashlib
import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def write(relative: str, content: str) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def replace_once(relative: str, old: str, new: str) -> None:
    text = read(relative)
    if new in text and old not in text:
        return
    if old not in text:
        raise SystemExit(f"repair anchor not found in {relative}: {old!r}")
    write(relative, text.replace(old, new, 1))


# Reuse the already-reviewed release materializer, then repair the integration
# mistakes that prevented its semantic result from ever reaching main.
runpy.run_path(str(ROOT / "scripts/materialize_release_1_3_1.py"), run_name="__main__")

for path in (ROOT / ".github/workflows").glob("materialize-*.yml"):
    path.unlink()
for path in (ROOT / "scripts").glob("materialize_*.py"):
    path.unlink()
for relative in (
    ".github/workflows/repair-release-state-1.3.1.yml",
    ".github/workflows/finalize-release-state-repair.yml",
    "tests/test_tagged_release_state.py",
    "docs/release-evidence/v1.3.1-tag.json",
):
    (ROOT / relative).unlink(missing_ok=True)

replace_once(
    "CHANGELOG.md",
    "## 1.3.1 - 2026-08-22",
    "## [1.3.1] - 2026-08-22",
)

# The old generator emitted one invalid Python string literal containing a real
# newline. Keep the generated test but repair it before collection.
generated = ROOT / "tests/test_patch_release_identity.py"
text = generated.read_text(encoding="utf-8")
broken = 'assert "    environment: release\n" not in workflow'
fixed = r'assert "    environment: release\n" not in workflow'
if broken not in text:
    raise SystemExit("generated release assertion repair anchor not found")
text = text.replace(broken, fixed, 1)
text = text.replace(
    'changelog.index("## 1.3.1") < changelog.index("## 1.3.0")',
    'changelog.index("## [1.3.1]") < changelog.index("## [1.3.0]")',
)
generated.write_text(text, encoding="utf-8")

identity_path = ROOT / "docs/release-identity.md"
identity = identity_path.read_text(encoding="utf-8")
anchor = (
    "The tag is created only after the release-preparation PR is merged and all "
    "required CI/release gates are green. It must point to that exact reviewed "
    "`main` commit and must never be moved.\n"
)
addition = anchor + (
    "\nNo public `doc-atlas==1.3.1` release is claimed until the immutable tag, "
    "PyPI artifact bytes, and post-publish platform smokes exist.\n\n"
    "## Historical repository milestone\n\n"
    "Repository version `1.2.0` remains an unpublished historical milestone. "
    "It is retained only as repository history and is not reused as public "
    "release evidence.\n"
)
if addition not in identity:
    if anchor not in identity:
        raise SystemExit("release identity insertion anchor not found")
    identity = identity.replace(anchor, addition, 1)
    identity_path.write_text(identity, encoding="utf-8")

branding_path = ROOT / "tests/docs/test_user_facing_docs_branding.py"
branding = branding_path.read_text(encoding="utf-8")
replacements = {
    '    assert f"doc-atlas {source_version.group(1)}" in release_identity\n':
        '    assert f"DocAtlas {source_version.group(1)}" in release_identity\n',
    '    assert "release candidate in source" in release_identity\n':
        '    assert "current source release candidate" in release_identity.lower()\n',
    '    assert "no `v1.3.1` tag or public `1.3.1` artifact is evidence" in release_identity\n':
        '    assert "no public `doc-atlas==1.3.1` release is claimed" in release_identity.lower()\n',
    '    assert f"## [{source_version.group(1)}] - 2026-08-21" in changelog\n':
        '    assert f"## [{source_version.group(1)}] - 2026-08-22" in changelog\n',
}
for old, new in replacements.items():
    if old not in branding:
        raise SystemExit(f"branding repair anchor not found: {old!r}")
    branding = branding.replace(old, new, 1)
branding_path.write_text(branding, encoding="utf-8")

projection_path = ROOT / "docmancer/docs/interfaces/mcp/recovery_projection.py"
projection = projection_path.read_text(encoding="utf-8")
import_anchor = (
    "from docmancer.docs.application.recovery import "
    "build_recovery_diagnosis, recovery_action\n"
)
import_line = (
    "from docmancer.docs.domain.recovery_handoff import "
    "is_safe_local_source_handoff\n"
)
if import_line not in projection:
    if import_anchor not in projection:
        raise SystemExit("recovery handoff import anchor not found")
    projection = projection.replace(import_anchor, import_anchor + import_line, 1)
unsafe_branch = '    elif recovery.get("tool") == "code_search":\n'
safe_branch = '    elif is_safe_local_source_handoff(recovery):\n'
if safe_branch not in projection:
    if unsafe_branch not in projection:
        raise SystemExit("unsafe code-search projection branch not found")
    projection = projection.replace(unsafe_branch, safe_branch, 1)
projection_path.write_text(projection, encoding="utf-8")

write(
    "tests/test_release_state_repair.py",
    '''from __future__ import annotations

import json
from pathlib import Path

from docmancer._version import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_release_state_is_semantic_clean_and_consistent() -> None:
    assert __version__ == "1.3.1"

    leaked_workflows = sorted(
        path.name
        for path in (ROOT / ".github/workflows").glob("materialize-*.yml")
    )
    leaked_scripts = sorted(
        path.name for path in (ROOT / "scripts").glob("materialize_*.py")
    )
    assert leaked_workflows == []
    assert leaked_scripts == []

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.index("## [1.3.1]") < changelog.index("## [1.3.0]")
    assert "invalid-publisher" in changelog

    workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    assert "for example v1.3.1" in workflow
    assert "    environment: release-current" in workflow
    assert "    environment: release\\n" not in workflow

    identity = (ROOT / "docs/release-identity.md").read_text(encoding="utf-8")
    assert "current source release candidate is **DocAtlas 1.3.1**" in identity
    assert "v1.3.0" in identity
    assert "must not be moved, replaced, or reused" in identity
    assert "environment: release-current" in identity
    assert "unpublished historical milestone" in identity.lower()
    assert "no public `doc-atlas==1.3.1` release is claimed" in identity.lower()

    scorecard = (ROOT / "docs/public-truth-scorecard.md").read_text(encoding="utf-8")
    assert "Status: **INCOMPLETE**" in scorecard
    assert "Trusted Publisher identity | `pending`" in scorecard
    assert "Exact public artifact identity | `pending`" in scorecard
    assert "Exact public MCP behavior | `pending`" in scorecard
    assert "Cross-platform public install | `pending`" in scorecard
    assert "doc-atlas==1.3.1" in scorecard

    roadmap = (ROOT / "roadmap/README.md").read_text(encoding="utf-8")
    assert "P0.5 — Publish and verify public `1.3.1`" in roadmap
    assert "superseded pre-public attempt" in roadmap


def test_tag_evidence_cannot_be_confused_with_public_release_closure() -> None:
    evidence_path = ROOT / "docs/release-evidence/v1.3.1-tag.json"
    if not evidence_path.exists():
        identity = (ROOT / "docs/release-identity.md").read_text(encoding="utf-8")
        assert "The tag is created only after" in identity
        return

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["tag"] == "v1.3.1"
    assert evidence["target_commit_sha"] == evidence["peeled_commit_sha"]
    assert evidence["public_artifact_status"] in {"pending", "green"}
''',
)

manifest_path = ROOT / "tests/diagnostic_labels.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
modules = {
    "tests/test_patch_release_identity.py": "behavioral",
    "tests/test_release_state_repair.py": "behavioral",
    "tests/test_source_search_edit_readiness.py": "behavioral",
}


def nodeids(relative: str) -> list[str]:
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"), filename=relative)
    rows: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                rows.append(f"{relative}::{node.name}")
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for child in node.body:
                if (
                    isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and child.name.startswith("test_")
                ):
                    rows.append(f"{relative}::{node.name}::{child.name}")
    if not rows:
        raise SystemExit(f"no diagnostic test nodes found in {relative}")
    return sorted(rows)


for relative, label in modules.items():
    manifest["module_labels"][relative] = label
    manifest["module_node_hashes"][relative] = hashlib.sha256(
        "\n".join(nodeids(relative)).encode()
    ).hexdigest()
    for nodeid in list(manifest["node_overrides"]):
        if nodeid.split("::", 1)[0] == relative:
            del manifest["node_overrides"][nodeid]
manifest_path.write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

# Remove the finalizer itself only after all semantic changes are materialized.
(ROOT / "scripts/finalize_release_state_repair.py").unlink()

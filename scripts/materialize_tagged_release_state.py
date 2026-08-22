from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"expected block not found in {relative}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "docs/release-identity.md",
    "The tag is created only after the release-preparation PR is merged and all required CI/release gates are green. It must point to that exact reviewed `main` commit and must never be moved.\n",
    "Immutable annotated tag `v1.3.1` now exists on the exact reviewed release-preparation `main` commit. `docs/release-evidence/v1.3.1-tag.json` binds the tag object SHA, peeled target commit, source version, publish environment, and successful post-merge `required-ci` / `required-release` checks. The tag must never be moved.\n",
)

replace_once(
    "docs/public-truth-scorecard.md",
    "Status: **INCOMPLETE** — the reviewed `1.3.1` source candidate is being prepared, but the exact public PyPI release and post-publish verification do not exist yet.\n",
    "Status: **INCOMPLETE** — immutable `v1.3.1` source/tag evidence exists, but the exact public PyPI release and post-publish verification do not exist yet.\n",
)
replace_once(
    "docs/public-truth-scorecard.md",
    "| Release source identity | `green` | Source, changelog, build metadata, release docs, and workflow examples identify `1.3.1`; `v1.3.0` remains a superseded pre-public audit tag. |\n",
    "| Release source identity | `green` | Source, changelog, build metadata, release docs, and workflow examples identify `1.3.1`; `docs/release-evidence/v1.3.1-tag.json` binds immutable tag object and peeled `main` commit after green required checks; `v1.3.0` remains a superseded pre-public audit tag. |\n",
)

roadmap = ROOT / "roadmap/README.md"
text = roadmap.read_text(encoding="utf-8")
checkpoint = "Current checkpoint: immutable `v1.3.1` tag evidence is recorded in `docs/release-evidence/v1.3.1-tag.json`. Public publication remains blocked only on the external PyPI Trusted Publisher identity and the resulting public verification.\n"
if checkpoint not in text:
    anchor = "The immutable `v1.3.0` tag records a superseded pre-public attempt whose OIDC upload failed before publication. It must not be moved or rerun. `1.3.1` is the replacement public candidate because current `main` contains reviewed recovery fixes that are not part of that old tag.\n"
    if anchor not in text:
        raise SystemExit("roadmap release checkpoint anchor not found")
    text = text.replace(anchor, anchor + "\n" + checkpoint, 1)
    roadmap.write_text(text, encoding="utf-8")

(ROOT / "tests/test_tagged_release_state.py").write_text(
    '''import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tagged_release_state_is_exact_but_not_public_closure():
    evidence = json.loads(
        (ROOT / "docs/release-evidence/v1.3.1-tag.json").read_text(encoding="utf-8")
    )
    assert evidence["tag"] == "v1.3.1"
    assert evidence["target_commit_sha"] == evidence["peeled_commit_sha"]
    assert evidence["required_checks"] == {
        "required-ci": "success",
        "required-release": "success",
    }
    assert evidence["public_artifact_status"] == "pending"

    identity = (ROOT / "docs/release-identity.md").read_text(encoding="utf-8")
    assert "Immutable annotated tag `v1.3.1` now exists" in identity
    assert "docs/release-evidence/v1.3.1-tag.json" in identity

    scorecard = (ROOT / "docs/public-truth-scorecard.md").read_text(encoding="utf-8")
    assert "immutable `v1.3.1` source/tag evidence exists" in scorecard
    assert "Exact public artifact identity | `pending`" in scorecard
    assert "Cross-platform public install | `pending`" in scorecard

    roadmap = (ROOT / "roadmap/README.md").read_text(encoding="utf-8")
    assert "Current checkpoint: immutable `v1.3.1` tag evidence" in roadmap
    assert "external PyPI Trusted Publisher" in roadmap
''',
    encoding="utf-8",
)

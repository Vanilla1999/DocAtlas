from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "8e9919c0d411e3f9dd55ec0da2f0f191bee18398"
TEST_SOURCE_SHA = "eadacfeee93ea0f9dcd845f4812605c9588a1d71"


def git_show(spec: str) -> str:
    return subprocess.check_output(
        ["git", "show", spec],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )


# Run the already-reviewed materializer from the exact PR base. Keeping the
# bootstrap tiny makes the final semantic output reviewable while this staging
# carrier deletes itself before merge.
source_path = ROOT / "scripts/materialize_release_1_3_1.py"
source = git_show(f"{BASE_SHA}:scripts/materialize_release_1_3_1.py")
namespace = {
    "__file__": str(source_path),
    "__name__": "__main__",
}
exec(compile(source, str(source_path), "exec"), namespace)

# Preserve an explicit, case-stable claim boundary. The next workflow step
# recognises this exact block and therefore does not create a duplicate.
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
case_stable_claim = (
    "\nFor clarity, no public `doc-atlas==1.3.1` release is claimed at this "
    "pre-public stage.\n"
)
if addition not in identity:
    if anchor not in identity:
        raise SystemExit("release identity insertion anchor not found")
    identity = identity.replace(anchor, addition, 1)
if case_stable_claim.strip() not in identity:
    identity += case_stable_claim
identity_path.write_text(identity, encoding="utf-8")

# The staging branch omits this test so ordinary PR collection remains valid.
# Materialization restores the exact reviewed test before the diagnostic
# manifest is regenerated and before any semantic commit is pushed.
test_path = ROOT / "tests/test_source_search_edit_readiness.py"
test_path.write_text(
    git_show(f"{TEST_SOURCE_SHA}:tests/test_source_search_edit_readiness.py"),
    encoding="utf-8",
)

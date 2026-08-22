import json
import os
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from docmancer._version import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_patch_release_identity_is_single_source_and_preserves_failed_tag_audit():
    assert __version__ == "1.3.1"
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.index("## [1.3.1]") < changelog.index("## [1.3.0]")

    identity = (ROOT / "docs/release-identity.md").read_text(encoding="utf-8")
    assert "current source release candidate is **DocAtlas 1.3.1**" in identity
    assert "v1.3.0" in identity
    assert "must never be moved, replaced, or reused" in identity
    assert "invalid-publisher" in identity
    assert "environment: release-current" in identity
    assert "32587903026" in identity
    assert "cfa9ab5c365a28d1a4af63afe9f1d53b19532d89" in identity
    assert "6b82e37ec8ac2a3d415f30aa51e48830afecd04386d34dab694ee6b6c697b6b0" in identity
    assert "6cbcdf8d947ca4f494fa3052d5012703c29386ec3e8f8629d7cabba58bb62aff" in identity

    roadmap = (ROOT / "roadmap/README.md").read_text(encoding="utf-8")
    assert "P0.5 — Publish and verify public `1.3.1`" in roadmap
    assert "superseded pre-public attempt" in roadmap
    assert "publication remains manual through the `release-current` environment" in roadmap
    assert "publication remains manual through the `release` environment" not in roadmap

    scorecard = (ROOT / "docs/public-truth-scorecard.md").read_text(encoding="utf-8")
    assert "Status: **INCOMPLETE**" in scorecard
    assert "reviewed `1.3.1` source and immutable tag exist" in scorecard
    assert "Trusted Publisher identity | `pending`" in scorecard
    assert "doc-atlas==1.3.1" in scorecard
    assert "rerun only the failed jobs" in scorecard

    tag_evidence = json.loads(
        (ROOT / "docs/release-evidence/v1.3.1-tag.json").read_text(
            encoding="utf-8"
        )
    )
    assert tag_evidence["tag"] == "v1.3.1"
    assert tag_evidence["tag_object_sha"] == (
        "77bced8c530c88c57d2e6c5f58cb717bfe837a9f"
    )
    assert tag_evidence["target_commit_sha"] == tag_evidence["peeled_commit_sha"]
    assert tag_evidence["target_commit_sha"] == (
        "cfa9ab5c365a28d1a4af63afe9f1d53b19532d89"
    )
    assert tag_evidence["public_artifact_status"] == "pending"

    evidence = json.loads(
        (ROOT / "docs/release-evidence/v1.3.1-publish-attempt-1.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["schema_version"] == 1
    assert evidence["release"] == {
        "distribution": "doc-atlas",
        "maturity": "Beta",
        "product": "DocAtlas",
        "version": "1.3.1",
    }
    assert evidence["git"] == {
        "tag": "v1.3.1",
        "tag_object_sha": "77bced8c530c88c57d2e6c5f58cb717bfe837a9f",
        "target_commit_sha": "cfa9ab5c365a28d1a4af63afe9f1d53b19532d89",
    }
    assert evidence["failure"] == {
        "code": "invalid-publisher",
        "oidc_token_valid": True,
        "public_upload_status": "rejected_before_upload",
        "stage": "pypa/gh-action-pypi-publish",
    }
    assert evidence["pypi_observation"]["version_1_3_1_exists"] is False
    assert evidence["workflow"]["run_id"] == 32587903026
    assert evidence["workflow"]["required_release_conclusion"] == "success"
    assert evidence["retry_contract"]["rerun_mode"] == "rerun_failed_jobs"
    assert evidence["retry_contract"]["tag_must_remain_immutable"] is True
    assert evidence["publisher_claims"]["sub"] == (
        "repo:Vanilla1999/DocAtlas:environment:release-current"
    )


def test_publish_workflow_uses_replacement_identity_not_failed_environment():
    workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    assert "for example v1.3.1" in workflow
    assert "    environment: release-current" in workflow
    assert "    environment: release\n" not in workflow
    assert "Record expected Trusted Publisher identity" in workflow
    assert "docatlas-publisher-context.json" in workflow
    assert "publisher-diagnostics-${{ github.run_id }}-${{ github.run_attempt }}" in workflow
    assert "if: steps.pypi_publish.outcome == 'failure'" in workflow
    assert "repo:Vanilla1999/DocAtlas:environment:release-current" in workflow
    assert "PYPI_API_TOKEN" not in workflow

    checklist = (ROOT / "docs/RELEASE_CHECKLIST.md").read_text(encoding="utf-8")
    assert "### `invalid-publisher` recovery" in checklist
    assert "Retry only the failed jobs of the original canonical run" in checklist
    assert "do not introduce `PYPI_API_TOKEN` as a fallback" in checklist

    publisher_section = workflow.split(
        "      - name: Record expected Trusted Publisher identity\n", 1
    )[1]
    embedded = publisher_section.split("          python - <<'PY'\n", 1)[1].split(
        "\n          PY\n", 1
    )[0]
    code = textwrap.dedent(embedded)
    compile(code, "publish.yml:publisher-context", "exec")

    good_env = {
        "EVENT_NAME": "workflow_dispatch",
        "REF_VALUE": "refs/heads/main",
        "RELEASE_TAG": "v1.3.1",
        "REPOSITORY": "Vanilla1999/DocAtlas",
        "REPOSITORY_OWNER": "Vanilla1999",
        "RUN_ATTEMPT": "2",
        "RUN_ID": "32587903026",
        "WORKFLOW_REF": (
            "Vanilla1999/DocAtlas/.github/workflows/publish.yml@refs/heads/main"
        ),
    }
    with tempfile.TemporaryDirectory() as raw, patch.dict(
        os.environ, {**good_env, "RUNNER_TEMP": raw}, clear=False
    ):
        exec(compile(code, "publish.yml:publisher-context", "exec"), {})
        payload = json.loads(
            (Path(raw) / "docatlas-publisher-context.json").read_text(
                encoding="utf-8"
            )
        )
    assert payload["secret_material_recorded"] is False
    assert payload["expected_publisher_claims"]["environment"] == "release-current"
    assert payload["github_context"]["release_tag"] == "v1.3.1"

    with tempfile.TemporaryDirectory() as raw, patch.dict(
        os.environ,
        {**good_env, "REPOSITORY": "Wrong/Repo", "RUNNER_TEMP": raw},
        clear=False,
    ):
        with pytest.raises(SystemExit, match="Trusted Publisher context mismatch"):
            exec(compile(code, "publish.yml:publisher-context", "exec"), {})

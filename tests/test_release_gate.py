from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import main_ruleset


ROOT = Path(__file__).resolve().parents[1]


def test_publish_workflow_is_manual_build_once_and_oidc() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    trigger_block = text.split("\non:\n", 1)[1].split("\npermissions:\n", 1)[0]
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
    assert "PYPI_API_TOKEN" not in text
    assert "environment: release" in text
    assert "if: github.event_name == 'workflow_dispatch'" in text
    assert "refs/tags/${{ inputs.tag }}" in text
    for line in text.splitlines():
        if "uses:" in line:
            ref = line.split("@", 1)[1].split()[0]
            assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref)


def test_dispatched_release_source_must_be_on_protected_main() -> None:
    # Historical node id retained for the diagnostic inventory. The release
    # policy now requires main ancestry while branch protection is an explicit
    # accepted risk rather than a hidden or falsely-green control.
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    build = text[text.index("  build:"):text.index("  wheel:")]
    assert "fetch-depth: 0" in build
    assert "if: github.event_name == 'workflow_dispatch'" in build
    assert "git fetch --no-tags origin main:refs/remotes/origin/main" in build
    assert "git merge-base --is-ancestor HEAD refs/remotes/origin/main" in build
    assert 'branch.get("protected")' not in build
    assert "remote main is not protected" not in build
    assert "Release source ancestry: PASS" in build

    roadmap = (ROOT / "roadmap" / "README.md").read_text(encoding="utf-8")
    scorecard = (ROOT / "docs" / "public-truth-scorecard.md").read_text(encoding="utf-8")
    assert "P0.1 — Remote `main` ruleset: accepted risk" in roadmap
    assert "| Branch protection | `accepted_risk` |" in scorecard
    assert "Status: **INCOMPLETE**" in scorecard


def test_installer_smoke_passes_an_existing_wheel_path() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    assert 'DOCATLAS_INSTALL_SOURCE="$(find "$PWD/dist" -name \'*.whl\' -print -quit)"' in text


def test_publish_excludes_release_manifest_from_pypi_upload() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    remove_manifest = text.index("rm dist/release-manifest.json")
    publish_action = text.index("pypa/gh-action-pypi-publish@")
    assert remove_manifest < publish_action


def test_sdist_gate_builds_and_smokes_its_own_wheel() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    assert "python -m pip wheel --no-deps --wheel-dir sdist-wheel dist/*.tar.gz" in text
    assert "python -m pip install --force-reinstall sdist-wheel/*.whl" in text
    assert "python scripts/release_gate.py --dist sdist-wheel" in text


def test_publish_runs_exact_public_version_smoke() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    publish = text[text.index("  publish:"):text.index("  public-platform-smoke:")]
    assert "RELEASE_TAG: ${{ inputs.tag }}" in publish
    assert 'RELEASE_VERSION="${RELEASE_TAG#v}"' in publish
    assert 'RELEASE_VERSION="${{ inputs.tag }}"' not in publish
    assert "DOCATLAS_INSTALL_VERSION=\"$RELEASE_VERSION\"" in publish
    assert "for attempt in 1 2 3 4 5" in publish
    assert "PIP_NO_CACHE_DIR=1" in publish
    assert "scripts/docs_mcp_stdio_smoke.py" in publish


def test_publish_verifies_exact_public_release_on_all_primary_platforms() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    public = text[text.index("  public-platform-smoke:"):]
    assert "if: github.event_name == 'workflow_dispatch'" in public
    assert "needs: [publish]" in public
    assert "os: [ubuntu-latest, macos-latest, windows-latest]" in public
    assert "ref: refs/tags/${{ inputs.tag }}" in public
    assert 'run: python scripts/public_release_smoke.py --tag "${{ inputs.tag }}"' in public


def test_public_release_smoke_is_exact_public_and_no_cache() -> None:
    text = (ROOT / "scripts/public_release_smoke.py").read_text()
    assert 'PYPI_INDEX = "https://pypi.org/simple"' in text
    assert '"--isolated"' in text
    assert '"--no-cache-dir"' in text
    assert 'f"doc-atlas=={version}"' in text
    assert "source_version() != version" in text
    assert 'expected = f"doc-atlas {version}"' in text
    assert 'ROOT / "scripts" / "docs_mcp_stdio_smoke.py"' in text


def test_stdio_smoke_requires_cited_content() -> None:
    text = (ROOT / "scripts/docs_mcp_stdio_smoke.py").read_text()
    assert "assert NEEDLE in rendered" in text
    assert 'assert set(canonical_query) == {"question", "project_path", "mode"}' in text
    canonical_block = text[
        text.index("canonical_query = {"):
        text.index("compatibility_query =", text.index("canonical_query = {"))
    ]
    assert "output_mode" not in canonical_block
    assert 'compatibility_query = {**canonical_query, "output_mode": "compact"}' in text
    assert "validate_context_payload(answer, required_fragment=NEEDLE)" in text


def test_stdio_smoke_uses_primary_docatlas_home_without_legacy_writes() -> None:
    text = (ROOT / "scripts/docs_mcp_stdio_smoke.py").read_text()
    assert '"HOME": str(user_home)' in text
    assert '"USERPROFILE": str(user_home)' in text
    assert '"DOCATLAS_HOME": str(docatlas_home)' in text
    assert 'env.pop("DOCMANCER_HOME", None)' in text
    assert 'not (user_home / ".docmancer").exists()' in text


def test_stdio_smoke_accepts_structured_content_and_legacy_json_text() -> None:
    from scripts.docs_mcp_stdio_smoke import payload, text_payload, validate_context_payload
    from scripts.run_project_docs_self_host_gate import GOLD_CASES, _validate_context_result

    class Text:
        def __init__(self, text: str) -> None:
            self.text = text

    class Result:
        def __init__(self, *, structured=None, text: str = "") -> None:
            if structured is not None:
                self.structuredContent = structured
            self.content = [Text(text)]

    expected = {"status": "ok", "kind": "docs_answer"}
    assert payload(Result(structured=expected, text="not JSON")) is expected
    assert payload(Result(text='{"status": "ok", "kind": "docs_answer"}')) == expected
    assert text_payload(Result(text='{"status": "ok", "kind": "docs_answer"}')) == expected
    with pytest.raises(AssertionError, match="included structuredContent"):
        text_payload(Result(structured=expected, text='{"status": "ok"}'))
    validate_context_payload({
        "status": "ok",
        "kind": "docs_context",
        "support_status": "retrieval_only",
        "context_status": "ready",
        "answer_supported": False,
        "answer_available": False,
        "sources": [{
            "path_or_url": "README.md",
            "snippet": "needle",
            "content_sha256": "a" * 64,
        }],
    }, required_fragment="needle")
    by_id = {case.surface_case_id: case for case in GOLD_CASES if case.surface_case_id is not None}
    assert set(by_id) == set(range(1, 21))
    assert all(case.relevant_paths and case.required_fragments for case in by_id.values())
    invalid_citation = {
        "kind": "docs_context",
        "context_status": "ready",
        "answer_supported": False,
        "answer_available": False,
        "edit_ready": False,
        "safe_to_answer_from_sources": True,
        "sources": [{"snippet": "grounded", "content_sha256": "z" * 64}],
    }
    assert _validate_context_result(invalid_citation) == "source lacks a grounded snippet or content hash"


def test_opencode_installer_enables_text_fallback_without_overwriting_other_environment() -> None:
    text = (ROOT / "scripts/install.sh").read_text()
    assert '"DOCATLAS_MCP_TEXT_FALLBACK": "1"' in text
    assert '"environment": {**environment, **desired["environment"]}' in text
    assert "has a different command; refusing to overwrite it" in text


def test_installer_compares_exact_version_output() -> None:
    text = (ROOT / "scripts/install.sh").read_text()
    assert '[ "$INSTALLED_VERSION" = "doc-atlas $EXPECTED_VERSION" ]' in text


def test_installer_accepts_pinned_and_local_sources() -> None:
    text = (ROOT / "scripts/install.sh").read_text()
    assert "DOCATLAS_INSTALL_SOURCE" in text
    assert "DOCATLAS_INSTALL_VERSION" in text
    assert "DOCATLAS_EXPECT_VERSION" in text


def _assert_main_ruleset_contract(monkeypatch, capsys) -> None:
    desired = main_ruleset._load(main_ruleset.DEFAULT_CONFIG)
    main_ruleset.validate_contract(desired)
    checks = main_ruleset._rule(
        main_ruleset.canonical_policy(desired),
        "required_status_checks",
    )["parameters"]["required_status_checks"]
    assert checks == [
        {
            "context": "required-ci",
            "integration_id": main_ruleset.GITHUB_ACTIONS_APP_ID,
        },
        {
            "context": "required-release",
            "integration_id": main_ruleset.GITHUB_ACTIONS_APP_ID,
        },
    ]

    mutations = [
        (
            lambda payload: payload["rules"][2]["parameters"].__setitem__(
                "dismiss_stale_reviews_on_push", True
            ),
            "pull request rule differs",
        ),
        (
            lambda payload: payload["rules"][3]["parameters"].__setitem__(
                "do_not_enforce_on_create", True
            ),
            "required checks must be strict",
        ),
        (
            lambda payload: payload["rules"][3]["parameters"][
                "required_status_checks"
            ][0].__setitem__("integration_id", None),
            "integration_id must be an integer",
        ),
    ]
    for mutator, message in mutations:
        payload = copy.deepcopy(desired)
        mutator(payload)
        with pytest.raises(ValueError, match=message):
            main_ruleset.validate_contract(payload)

    calls: list[tuple[str, str, str | None]] = []

    def fake_request(repo: str, path: str, *, token: str | None, **_: object):
        calls.append((repo, path, token))
        return [{"id": 7, "name": "protect-main"}]

    monkeypatch.setattr(main_ruleset, "_request", fake_request)
    result = main_ruleset._find_ruleset(
        "owner/repo",
        "protect-main",
        token="token",
    )
    assert result == {"id": 7, "name": "protect-main"}
    assert calls == [
        (
            "owner/repo",
            "/rulesets?includes_parents=false&per_page=100",
            "token",
        )
    ]

    remote = copy.deepcopy(desired)
    remote.pop("bypass_actors")
    monkeypatch.setattr(
        main_ruleset,
        "_find_ruleset",
        lambda *_args, **_kwargs: {"id": 7, "name": "protect-main"},
    )
    monkeypatch.setattr(
        main_ruleset,
        "_request",
        lambda *_args, **_kwargs: remote,
    )
    with pytest.raises(RuntimeError, match="omitted bypass_actors"):
        main_ruleset.check("owner/repo", desired, token="token")

    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert main_ruleset.main(["--check"]) == 1
    assert "Administration: write" in capsys.readouterr().err


def test_release_gate_help(monkeypatch, capsys) -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/release_gate.py"), "--help"],
        check=True,
    )
    _assert_main_ruleset_contract(monkeypatch, capsys)

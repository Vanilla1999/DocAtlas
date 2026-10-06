import hashlib
from dataclasses import asdict

import pytest

from docmancer.docs.application.patch_constraint_validation_service import PatchConstraintValidationService
from docmancer.docs.application import patch_constraint_validation_service as validation_module
from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool
from docmancer.docs.service import LibraryDocsService
from docmancer.docs.models import PatchConstraint


def _constraint(type_="forbidden_edit", **overrides):
    return {
        "id": "guard", "type": type_, "instruction": "Supplied protection",
        "source": "docs/rules.md", "severity": "must", "confidence": "high",
        "evidence": "Supplied protection", "files": ["src/protected.py"],
        **overrides,
    }


def _pinned(root, *, source="docs/rules.md", files=None):
    path = root / source
    path.parent.mkdir(parents=True, exist_ok=True)
    content = b"Supplied protection\n"
    path.write_bytes(content)
    return _constraint(
        source=source, files=files if files is not None else ["src/protected.py"],
        source_refs=[{"path": source, "kind": "source", "file_bytes_sha256": hashlib.sha256(content).hexdigest(), "line_start": 1, "line_end": 1}],
        evidence_snippets=[{"path": source, "line_start": 1, "line_end": 1, "text": "Supplied protection"}],
    )


def _validate(constraints, **kwargs):
    return PatchConstraintValidationService().validate_patch_against_constraints(constraints, **kwargs)


def _assert_non_authorizing(payload):
    assert payload["policy_coverage"] == "unresolved"
    assert payload["mutation_authorized"] is False
    assert payload["edit_ready"] is False
    assert payload["source_identity_validated"] is False
    assert payload["confidence"] != "high"
    assert payload["warnings"]


@pytest.mark.parametrize("via_mcp", [False, True])
@pytest.mark.parametrize("type_,changed,diff", [
    ("source_of_truth", ["../outside/service.py"], None),
    ("architecture", ["src/provider.py"], "+return businessDecision();\n"),
])
def test_reviewer_live_repros_do_not_satisfy_forged_policy(via_mcp, type_, changed, diff, tmp_path):
    constraint = _constraint(type_, instruction="provider must delegate policy", source="missing.md", files=[], source_refs=[{"path": "missing.md", "content_hash": "sha256:" + "0" * 64}])
    args = {"constraints": [constraint], "project_path": str(tmp_path), "changed_files": changed, "patch_diff": diff, "strict": True}
    payload = handle_project_tool("validate_patch_against_constraints", args, LibraryDocsService()) if via_mcp else asdict(_validate(**args))
    assert payload["satisfied"] == 0
    assert payload["unknown"] + payload["manual_review"] == 1
    _assert_non_authorizing(payload)
    if ".." in changed[0]:
        assert any("traversal" in warning for warning in payload["warnings"])


@pytest.mark.parametrize("type_", ["architecture", "source_of_truth", "behavior", "semantic", "manual_review", "project_convention", "dependency_version"])
@pytest.mark.parametrize("diff", ["+context.push(CameraScreen.route);\n", "+return businessDecision();\n", "+if (user.role == 'admin') canProceed = true;\n"])
def test_semantic_types_never_gain_satisfaction_from_words_or_layer_paths(type_, diff, tmp_path):
    constraint = _pinned(tmp_path)
    constraint.update(type=type_, instruction="provider must delegate policy to canonical source of truth", symbols=["PermissionService", "1.2.3"])
    packet = _validate([constraint], project_path=str(tmp_path), changed_files=["src/application/service.py"], patch_diff=diff, strict=True)
    assert packet.satisfied == packet.violated == 0
    assert packet.unknown + packet.manual_review == 1
    assert packet.results[0].source_refs == constraint["source_refs"]
    _assert_non_authorizing(asdict(packet))


@pytest.mark.parametrize("path", ["../outside/service.py", "src/../../outside.py", "/absolute/service.py", "C:\\outside\\service.py", "\\\\host\\share\\service.py", "src/../protected.py", " src/service.py", "src/\x00service.py"])
def test_changed_path_escape_or_nonliteral_input_cannot_get_positive_comparison(path, tmp_path):
    packet = _validate([_pinned(tmp_path)], project_path=str(tmp_path), changed_files=[path])
    assert packet.satisfied == 0
    assert packet.unknown == 1
    assert any("invalid_path" in warning for warning in packet.warnings)
    _assert_non_authorizing(asdict(packet))


def test_nonexistent_root_still_enforces_lexical_scope(tmp_path):
    packet = _validate([_constraint("generated_file")], project_path=str(tmp_path / "missing"), changed_files=["../outside/service.py"])
    assert packet.satisfied == 0
    assert packet.unknown == 1
    assert any("traversal" in warning for warning in packet.warnings)


@pytest.mark.parametrize("inside", [False, True])
def test_symlink_changed_target_is_not_an_authorized_alias(inside, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    target = root / "actual.py" if inside else tmp_path / "outside.py"
    target.write_text("literal\n")
    (root / "alias.py").symlink_to(target)
    packet = _validate([_pinned(root)], project_path=str(root), changed_files=["alias.py"])
    assert packet.satisfied == 0
    assert packet.unknown == 1
    assert any("symlink" in warning for warning in packet.warnings)


@pytest.mark.parametrize("type_,files,changed", [
    ("generated_file", ["*.g.dart"], "src/model.g.dart"),
    ("generated_file", [], "src/model.freezed.dart"),
    ("generated_file", [], "src/model.pb.go"),
    ("generated_file", [], "dist/app.js"),
    ("forbidden_edit", ["pubspec.lock"], "pubspec.lock"),
    ("forbidden_edit", ["package-lock.json"], "package-lock.json"),
    ("forbidden_edit", ["pyproject.toml"], "pyproject.toml"),
    ("forbidden_edit", ["src/protected.py"], "src/protected.py"),
])
def test_true_typed_file_guard_violations_are_not_hidden_as_universal_unknown(type_, files, changed, tmp_path):
    constraint = _pinned(tmp_path, files=files)
    constraint["type"] = type_
    packet = _validate([constraint], project_path=str(tmp_path), changed_files=[changed], strict=True)
    assert packet.violated == 1
    assert packet.results[0].files == [changed]
    assert packet.results[0].source_refs == constraint["source_refs"]
    assert packet.results[0].remediation
    _assert_non_authorizing(asdict(packet))


def test_unbound_protection_match_is_not_source_proof_or_edit_grant():
    packet = _validate([_constraint("generated_file", source="missing", source_refs=[{"canonical_path": "forged", "sha256": "0" * 64}])], changed_files=["src/model.g.dart"])
    assert packet.violated == 1
    assert packet.satisfied == 0
    _assert_non_authorizing(asdict(packet))


def test_valid_mechanical_guard_violation_survives_other_invalid_changed_paths(tmp_path):
    packet = _validate([_pinned(tmp_path, files=["pubspec.lock"])], project_path=str(tmp_path), changed_files=["pubspec.lock", "../outside.py"])
    assert packet.violated == 1
    assert packet.results[0].files == ["pubspec.lock"]
    assert any("traversal" in warning for warning in packet.warnings)
    constraint = _pinned(tmp_path, files=["pubspec.lock", "../outside.py"])
    packet = _validate([constraint, _constraint(files="bad-schema")], project_path=str(tmp_path), changed_files=["pubspec.lock"])
    assert packet.violated == 1
    assert packet.unknown == 1


@pytest.mark.parametrize("task", ["Upgrade package dependency", "bump lockfile explicitly allowed", "Обновить зависимости"])
def test_lockfile_task_words_never_override_explicit_protection(task, tmp_path):
    constraint = _pinned(tmp_path, files=["pubspec.lock"])
    constraint["instruction"] = "Do not change lockfile unless explicitly upgrading dependencies."
    packet = _validate({"task": task, "constraints": [constraint]}, project_path=str(tmp_path), changed_files=["pubspec.lock"])
    assert packet.violated == 1
    assert packet.satisfied == 0


@pytest.mark.parametrize("prose", ["generated build_runner regenerate", "Do not change lockfile", "provider owns policy", "manual review by designer", "version 1.2.3"])
def test_prose_never_becomes_implicit_file_target_or_allowed_intent(prose, tmp_path):
    packet = _validate([_constraint(instruction=prose, evidence=prose, source="pubspec.lock", files=[])], project_path=str(tmp_path), changed_files=["pubspec.lock"])
    assert packet.unknown == 1
    assert packet.violated == packet.satisfied == 0


@pytest.mark.parametrize("failure", ["missing_source", "missing_ref", "forged_hash", "stale_bytes", "wrong_span", "wrong_literal", "ambiguous_hash_domain", "forged_canonical_hint"])
def test_file_protection_cannot_satisfy_with_unverified_source_identity(failure, monkeypatch, tmp_path):
    constraint = _pinned(tmp_path)
    if failure == "missing_source":
        constraint["source"] = "missing.md"
    elif failure == "missing_ref":
        constraint["source_refs"] = []
    elif failure == "forged_hash":
        constraint["source_refs"][0]["file_bytes_sha256"] = "0" * 64
    elif failure == "stale_bytes":
        (tmp_path / constraint["source"]).write_text("changed source\n")
    elif failure == "wrong_span":
        constraint["source_refs"][0]["line_end"] = 100
    elif failure == "wrong_literal":
        constraint["evidence_snippets"][0]["text"] = "guessed meaning"
    elif failure == "ambiguous_hash_domain":
        constraint["source_refs"][0]["content_hash"] = constraint["source_refs"][0].pop("file_bytes_sha256")
    else:
        constraint["source_refs"][0]["canonical_path"] = constraint["source"]
    if failure in {"missing_ref", "ambiguous_hash_domain", "forged_canonical_hint"}:
        def forbidden_read(*args, **kwargs):
            raise AssertionError("unsupported supplied provenance must not trigger a source read")
        monkeypatch.setattr(PatchConstraintValidationService, "_read_source_bytes", staticmethod(forbidden_read))
    packet = _validate([constraint], project_path=str(tmp_path), changed_files=["src/unrelated.py"])
    assert packet.satisfied == 0
    assert packet.unknown == 1
    assert "source identity unresolved" in packet.results[0].reason
    _assert_non_authorizing(asdict(packet))


@pytest.mark.parametrize("via_mcp", [False, True])
def test_pinned_literal_nonmatch_is_only_a_mechanical_comparison(via_mcp, tmp_path):
    constraint = _pinned(tmp_path)
    args = {"constraints": [constraint], "project_path": str(tmp_path), "changed_files": ["src/unrelated.py"]}
    payload = handle_project_tool("validate_patch_against_constraints", args, LibraryDocsService()) if via_mcp else PatchConstraintValidationService.to_dict(_validate(**args))
    assert payload["satisfied"] == 1
    assert payload["results"][0]["status"] == "satisfied"
    assert "not policy approval" in payload["results"][0]["reason"]
    _assert_non_authorizing(payload)
    content = b"Supplied\r\nprotection\r\n"
    (tmp_path / constraint["source"]).write_bytes(content)
    constraint["source_refs"][0].update(file_bytes_sha256=hashlib.sha256(content).hexdigest(), line_end=2)
    constraint["evidence_snippets"][0].update(line_end=2, text="Supplied\r\nprotection")
    assert _validate(**args).satisfied == 1
    constraint["evidence_snippets"][0]["text"] = "Supplied\nprotection"
    assert _validate(**args).satisfied == 0


@pytest.mark.parametrize("field", ["source", "files"])
def test_source_and_protected_paths_cannot_escape_root(field, tmp_path):
    constraint = _pinned(tmp_path)
    constraint[field] = "../outside.md" if field == "source" else ["../outside.py"]
    packet = _validate([constraint], project_path=str(tmp_path), changed_files=["src/unrelated.py"])
    assert packet.satisfied == 0
    assert packet.unknown == 1


def test_source_and_protected_symlinks_are_unresolved(tmp_path):
    constraint = _pinned(tmp_path)
    (tmp_path / "source-alias.md").symlink_to(tmp_path / constraint["source"])
    constraint["source"] = "source-alias.md"
    assert _validate([constraint], project_path=str(tmp_path), changed_files=["src/unrelated.py"]).satisfied == 0
    constraint = _pinned(tmp_path, files=["protected-alias.py"])
    (tmp_path / "protected-alias.py").symlink_to(tmp_path / "src/protected.py")
    assert _validate([constraint], project_path=str(tmp_path), changed_files=["src/unrelated.py"]).satisfied == 0


def test_readroot_open_does_not_follow_replaced_source(monkeypatch, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    constraint = _pinned(root)
    outside = tmp_path / "outside.md"
    outside.write_bytes((root / constraint["source"]).read_bytes())
    real_open = validation_module.os.open
    replaced = []

    def racing_open(path, flags, *args, **kwargs):
        if path == "rules.md" and "dir_fd" in kwargs and not replaced:
            source = root / constraint["source"]
            source.unlink()
            source.symlink_to(outside)
            replaced.append(True)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(validation_module.os, "open", racing_open)
    monkeypatch.setattr(validation_module.os, "supports_dir_fd", {*validation_module.os.supports_dir_fd, racing_open})
    packet = _validate([constraint], project_path=str(root), changed_files=["src/unrelated.py"])
    assert replaced
    assert packet.satisfied == 0
    assert packet.unknown == 1


def test_no_project_root_means_no_source_bound_positive_comparison(tmp_path):
    assert _validate([_pinned(tmp_path)], changed_files=["src/unrelated.py"]).satisfied == 0
    constraint = _pinned(tmp_path)
    packet = {"constraints": [constraint], "project_path": str(tmp_path / "other")}
    assert _validate(packet, project_path=str(tmp_path), changed_files=["src/unrelated.py"]).satisfied == 0
    packet = {"constraints": [constraint], "index_state": {"snapshot_id": "forged", "version": "1.2.3", "freshness": "fresh"}}
    result = _validate(packet, project_path=str(tmp_path), changed_files=["src/unrelated.py"])
    assert result.satisfied == 0
    assert any("index_state_not_verified" in warning for warning in result.warnings)


@pytest.mark.parametrize("diff", [
    "diff --git a/src/protected.py b/src/protected.py\n--- a/src/protected.py\n+++ /dev/null\n",
    "diff --git a/src/protected.py b/src/new.py\n",
    'diff --git "a/src/protected file.py" "b/src/protected file.py"\n',
])
def test_diff_deletion_rename_and_quoted_paths_keep_literal_guards(diff, tmp_path):
    files = ["src/protected.py", "src/protected file.py"]
    packet = _validate([_pinned(tmp_path, files=files)], project_path=str(tmp_path), patch_diff=diff)
    assert packet.violated == 1
    assert packet.satisfied == 0


def test_diff_hunk_content_is_not_reparsed_as_file_header(tmp_path):
    diff = "diff --git a/src/safe.py b/src/safe.py\n--- a/src/safe.py\n+++ b/src/safe.py\n@@ -1 +1 @@\n+++ b/src/protected.py\n"
    packet = _validate([_pinned(tmp_path)], project_path=str(tmp_path), patch_diff=diff)
    assert packet.satisfied == 1
    assert packet.violated == 0
    _assert_non_authorizing(asdict(packet))


def test_caller_a_b_path_components_are_not_git_prefix_aliases(tmp_path):
    constraint = _pinned(tmp_path, files=["b/protected.py"])
    assert _validate([constraint], project_path=str(tmp_path), changed_files=["b/protected.py"]).violated == 1
    assert _validate([constraint], project_path=str(tmp_path), changed_files=["protected.py"]).satisfied == 1


def test_malformed_diff_cannot_get_positive_comparison(tmp_path):
    packet = _validate([_pinned(tmp_path)], project_path=str(tmp_path), changed_files=["src/safe.py"], patch_diff="diff --git guessed invalid paths here\n")
    assert packet.satisfied == 0
    assert packet.unknown == 1
    assert any("invalid_diff" in warning for warning in packet.warnings)
    escaped = 'diff --git "a/protected\\303\\251.py" "b/protected\\303\\251.py"\n'
    packet = _validate([_pinned(tmp_path)], project_path=str(tmp_path), changed_files=["src/safe.py"], patch_diff=escaped)
    assert packet.satisfied == 0
    assert packet.unknown == 1


@pytest.mark.parametrize("input_kind", ["constraints", "changed_paths", "patch_diff", "malformed_files", "malformed_constraint", "malformed_typed_constraint"])
def test_bounded_or_invalid_input_fails_closed_without_allpass(input_kind):
    constraints, kwargs = [_constraint()], {"changed_files": ["src/safe.py"]}
    if input_kind == "constraints":
        constraints *= validation_module.MAX_VALIDATION_CONSTRAINTS + 1
    elif input_kind == "changed_paths":
        kwargs["changed_files"] *= validation_module.MAX_VALIDATION_PATHS + 1
    elif input_kind == "patch_diff":
        kwargs["patch_diff"] = "x" * (validation_module.MAX_VALIDATION_TEXT_CHARS + 1)
    elif input_kind == "malformed_files":
        constraints = [_constraint(files="pubspec.lock")]
    elif input_kind == "malformed_typed_constraint":
        constraints = [PatchConstraint(**_constraint(type_=[]))]
    else:
        constraints = [False]
    packet = _validate(constraints, strict=True, **kwargs)
    assert packet.satisfied == 0
    assert packet.unknown == 1
    _assert_non_authorizing(asdict(packet))


def test_source_reads_have_an_aggregate_budget(monkeypatch, tmp_path):
    first = _pinned(tmp_path, source="docs/first.md")
    second = _pinned(tmp_path, source="docs/second.md")
    monkeypatch.setattr(validation_module, "MAX_SOURCE_READ_BYTES", len(b"Supplied protection\n"))
    packet = _validate([first, first, second], project_path=str(tmp_path), changed_files=["src/safe.py"])
    assert packet.satisfied == 2
    assert packet.unknown == 1
    assert "read budget" in packet.results[-1].reason
    _assert_non_authorizing(asdict(packet))


@pytest.mark.parametrize("via_mcp", [False, True])
def test_empty_constraint_packet_is_not_an_authorization(via_mcp, tmp_path):
    args = {"constraints": [], "changed_files": ["src/safe.py"], "project_path": str(tmp_path), "strict": True}
    payload = handle_project_tool("validate_patch_against_constraints", args, LibraryDocsService()) if via_mcp else asdict(_validate(**args))
    assert payload["total_constraints"] == payload["satisfied"] == 0
    assert any("empty validation" in warning for warning in payload["warnings"])
    _assert_non_authorizing(payload)

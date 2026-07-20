from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "lib/modules/permission/application/permission_service.dart"
BROWSER = ROOT / "lib/modules/browser/application/browser_permission_gate.dart"
SCAN = ROOT / "lib/modules/scan/application/scan_permission_gate.dart"
SYNC = ROOT / "lib/modules/sync/application/offline_sync_gate.dart"
REVIEW = ROOT / "lib/modules/review/application/permission_review_policy.dart"
PUBSPEC = ROOT / "pubspec.yaml"
LOCKFILE = ROOT / "pubspec.lock"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


_ENTRY_RECEIVER = r"(?:_permissionService|this\._permissionService)"
_METHOD_RETURN_TYPES = {
    "canAcceptQueuedWork": "bool",
    "canEnter": "bool",
    "evaluateFlowEntry": "PermissionDecision",
}


def _code_text(path: Path) -> str:
    return _strip_dart_non_code(_text(path))


def _delegates_and_requires_allow(
    source: str,
    *,
    required_fallback: bool | None = None,
) -> bool:
    if required_fallback is None:
        call_args = (
            r"\(\s*result\s*"
            r"(?:,\s*allowOfflineFallback\s*:\s*false\s*,?)?\s*\)"
        )
    else:
        fallback = str(required_fallback).lower()
        call_args = (
            r"\(\s*result\s*,\s*allowOfflineFallback\s*:\s*"
            + fallback
            + r"\s*,?\s*\)"
        )
    direct = re.fullmatch(
        rf"\s*return\s+{_ENTRY_RECEIVER}\.evaluateFlowEntry\s*"
        + call_args
        + r"\s*==\s*PermissionDecision\.allow\s*;\s*",
        source,
    )
    assigned = re.fullmatch(
        r"\s*final\s+(?:PermissionDecision\s+)?(\w+)\s*=\s*"
        rf"{_ENTRY_RECEIVER}\.evaluateFlowEntry\s*"
        + call_args
        + r"\s*;\s*return\s+\1\s*==\s*"
        r"PermissionDecision\.allow\s*;\s*",
        source,
    )
    return direct is not None or assigned is not None


def _blocks_missing_immediate(source: str) -> bool:
    pattern = re.compile(
        r"\s*if\s*\(\s*result\.hasMissingImmediatePermission\s*\)\s*"
        r"\{\s*return\s+PermissionDecision\.block\s*;\s*\}",
    )
    return pattern.match(source) is not None


def _changed_files() -> list[str]:
    result = subprocess.run(["git", "diff", "--name-only"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert result.returncode == 0, result.stderr
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _method_body(path: Path, class_name: str, method: str) -> str:
    code = _class_body(_code_text(path), class_name)
    return_type = _METHOD_RETURN_TYPES[method]
    match = re.search(
        rf"(?m)^[ \t]*{re.escape(return_type)}[ \t]+"
        rf"{re.escape(method)}\s*\([\s\S]*?\)\s*(\{{)",
        code,
    )
    assert match, f"{path.name} must expose {method}(...)"
    body_start = match.end(1)
    depth = 1
    for index in range(body_start, len(code)):
        if code[index] == "{":
            depth += 1
        elif code[index] == "}":
            depth -= 1
            if depth == 0:
                return code[body_start:index]
    raise AssertionError(f"{path.name} must close {method}(...) body")


def _class_body(code: str, class_name: str) -> str:
    match = re.search(rf"\bclass\s+{re.escape(class_name)}\b[^{{]*(\{{)", code)
    assert match, f"must expose class {class_name}"
    body_start = match.end(1)
    depth = 1
    for index in range(body_start, len(code)):
        if code[index] == "{":
            depth += 1
        elif code[index] == "}":
            depth -= 1
            if depth == 0:
                return code[body_start:index]
    raise AssertionError(f"must close class {class_name}")


def _has_permission_service_field(path: Path, class_name: str) -> bool:
    return re.search(
        r"(?m)^[ \t]*(?:(?:late|final)\s+)*PermissionService[ \t]+"
        r"_permissionService\s*;",
        _class_body(_code_text(path), class_name),
    ) is not None


def _strip_dart_non_code(text: str) -> str:
    masked = list(text)
    index = 0
    while index < len(text):
        if text.startswith("//", index):
            end = text.find("\n", index)
            end = len(text) if end < 0 else end
            for position in range(index, end):
                masked[position] = " "
            index = end
            continue
        if text.startswith("/*", index):
            depth = 1
            end = index + 2
            while end < len(text) and depth:
                if text.startswith("/*", end):
                    depth += 1
                    end += 2
                elif text.startswith("*/", end):
                    depth -= 1
                    end += 2
                else:
                    end += 1
            for position in range(index, end):
                if masked[position] != "\n":
                    masked[position] = " "
            index = end
            continue
        if text[index] in {"'", '"'}:
            quote = text[index]
            delimiter = quote * 3 if text.startswith(quote * 3, index) else quote
            end = index + len(delimiter)
            while end < len(text):
                if text.startswith(delimiter, end):
                    end += len(delimiter)
                    break
                end += 2 if len(delimiter) == 1 and text[end] == "\\" else 1
            for position in range(index, min(end, len(text))):
                if masked[position] != "\n":
                    masked[position] = " "
            index = end
            continue
        index += 1
    return "".join(masked)


def test_hidden_requirement_sources_are_visible():
    assert "canonical owner of permission result interpretation" in _text(ROOT / "docs/permission-architecture.md")
    assert "Browser and scan flows both share the same immediate-entry contract" in _text(ROOT / "docs/permission-architecture.md")
    assert "offline fallback still cannot bypass missing immediate-entry permissions" in _text(ROOT / "docs/permission-architecture.md")
    assert "Use `PermissionService.evaluateFlowEntry(result, allowOfflineFallback: false)`" in _text(ROOT / "docs/offline-sync.md")
    assert "must not be hand-edited" in _text(ROOT / "docs/generated-files.md")


def test_permission_service_blocks_partial_results_for_entry_even_when_offline_fallback_exists():
    service = _text(SERVICE)
    entry = _method_body(SERVICE, "PermissionService", "evaluateFlowEntry")

    assert "PermissionDecision evaluateFlowEntry" in service
    assert "allowOfflineFallback" in service
    assert _blocks_missing_immediate(entry)
    assert "PermissionDecision.deferFollowUp" not in entry


def test_browser_scan_and_sync_delegate_to_shared_entry_contract():
    browser = _method_body(BROWSER, "BrowserPermissionGate", "canEnter")
    scan = _method_body(SCAN, "ScanPermissionGate", "canEnter")
    sync = _method_body(SYNC, "OfflineSyncGate", "canAcceptQueuedWork")

    assert _has_permission_service_field(BROWSER, "BrowserPermissionGate")
    assert _has_permission_service_field(SCAN, "ScanPermissionGate")
    assert _has_permission_service_field(SYNC, "OfflineSyncGate")
    assert _delegates_and_requires_allow(browser, required_fallback=True)
    assert _delegates_and_requires_allow(scan)
    assert _delegates_and_requires_allow(sync, required_fallback=False)


def test_no_duplicate_immediate_permission_interpretation_in_flow_gates():
    flow_text = "\n".join(_code_text(path) for path in [BROWSER, SCAN, SYNC])

    forbidden = [
        "cameraGranted ||",
        "locationGranted ||",
        "nearbyGranted ||",
        "notificationGranted ||",
        "hasMissingImmediatePermission",
        "hasPartialImmediateGrant",
        "decision != PermissionDecision.block",
    ]
    for token in forbidden:
        assert token not in flow_text


def test_review_policy_stays_descriptive_and_background_location_remains_deferred_followup():
    service = _text(SERVICE)
    review = _text(REVIEW)

    assert "hasDeferredBackgroundLocation" in service
    assert "PermissionDecision.deferFollowUp" in service
    assert "evaluateReview" in review
    assert "canEnter" not in review


def test_generated_and_dependency_files_are_not_changed():
    changed = _changed_files()

    assert all(not path.endswith((".freezed.dart", ".g.dart")) for path in changed)
    assert "pubspec.yaml" not in changed
    assert "pubspec.lock" not in changed
    assert "permission_handler: 11.4.0" in _text(PUBSPEC)
    assert 'version: "11.4.0"' in _text(LOCKFILE)

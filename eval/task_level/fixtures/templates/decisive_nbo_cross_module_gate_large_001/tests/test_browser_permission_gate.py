from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "lib/modules/permission/application/permission_service.dart"
BROWSER = ROOT / "lib/modules/browser/application/browser_permission_gate.dart"
REVIEW = ROOT / "lib/modules/review/application/permission_review_policy.dart"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


_ENTRY_RECEIVER = r"(?:_permissionService|this\._permissionService)"
_METHOD_RETURN_TYPES = {
    "canEnter": "bool",
    "evaluateFlowEntry": "PermissionDecision",
}


def _code_text(path: Path) -> str:
    return _strip_dart_non_code(_text(path))


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


def _returns_only_allow(source: str) -> bool:
    direct = re.fullmatch(
        rf"\s*return\s+{_ENTRY_RECEIVER}\.evaluateFlowEntry\s*\([^()]*\)\s*"
        r"==\s*PermissionDecision\.allow\s*;\s*",
        source,
    )
    assigned = re.fullmatch(
        r"\s*final\s+(?:PermissionDecision\s+)?(\w+)\s*=\s*"
        rf"{_ENTRY_RECEIVER}\.evaluateFlowEntry\s*"
        r"\([^()]*\)\s*;\s*return\s+\1\s*==\s*"
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


def test_browser_blocks_partial_permission_result_even_with_offline_fallback():
    browser = _method_body(BROWSER, "BrowserPermissionGate", "canEnter")
    entry = _method_body(SERVICE, "PermissionService", "evaluateFlowEntry")

    assert "allowOfflineFallback: true" in browser
    assert _returns_only_allow(browser)
    assert _has_permission_service_field(BROWSER, "BrowserPermissionGate")
    assert _blocks_missing_immediate(entry)
    assert "PermissionDecision.deferFollowUp" not in browser
    assert "PermissionDecision.deferFollowUp" not in entry


def test_allowed_result_still_has_allow_and_block_decisions():
    service = _text(SERVICE)
    entry = _method_body(SERVICE, "PermissionService", "evaluateFlowEntry")

    assert "PermissionDecision allow" not in service
    assert "PermissionDecision.allow" in service
    assert "PermissionDecision.block" in service
    assert "hasMissingImmediatePermission" in service
    assert _blocks_missing_immediate(entry)


def test_review_policy_remains_descriptive_not_entry_gate():
    review = _text(REVIEW)

    assert "evaluateReview" in review
    assert "labelFor" in review
    assert "canEnter" not in review

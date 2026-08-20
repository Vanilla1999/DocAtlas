#!/usr/bin/env python3
"""Apply or verify the canonical GitHub ruleset protecting ``main``.

The repository stores the desired Rulesets API payload in
``.github/rulesets/protect-main.json``. This script is stdlib-only so an owner
can apply it with an already-authenticated token without installing DocAtlas or
placing a credential in repository files.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / ".github" / "rulesets" / "protect-main.json"
DEFAULT_REPO = "Vanilla1999/DocAtlas"
API_VERSION = "2022-11-28"
GITHUB_ACTIONS_APP_ID = 15368
EXPECTED_STATUS_CHECKS = {
    "required-ci": GITHUB_ACTIONS_APP_ID,
    "required-release": GITHUB_ACTIONS_APP_ID,
}
EXPECTED_RULE_TYPES = {"deletion", "non_fast_forward", "pull_request", "required_status_checks"}
_PULL_REQUEST_FIELDS = (
    "required_approving_review_count",
    "dismiss_stale_reviews_on_push",
    "require_code_owner_review",
    "require_last_push_approval",
    "required_review_thread_resolution",
    "allowed_merge_methods",
)
_STATUS_CHECK_FIELDS = (
    "required_status_checks",
    "strict_required_status_checks_policy",
    "do_not_enforce_on_create",
)
EXPECTED_PULL_REQUEST_PARAMETERS = {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews_on_push": False,
    "require_code_owner_review": False,
    "require_last_push_approval": False,
    "required_review_thread_resolution": True,
    "allowed_merge_methods": ["squash"],
}
EXPECTED_STATUS_CHECK_PARAMETERS = {
    "required_status_checks": [
        {"context": context, "integration_id": integration_id}
        for context, integration_id in sorted(EXPECTED_STATUS_CHECKS.items())
    ],
    "strict_required_status_checks_policy": True,
    "do_not_enforce_on_create": False,
}


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("ruleset config must be a JSON object")
    return payload


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    return list(value)


def _rules(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = _list(payload.get("rules"), "rules")
    if any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("every rules entry must be an object")
    return [dict(row) for row in rows]


def _rule(payload: Mapping[str, Any], rule_type: str) -> dict[str, Any]:
    rows = [row for row in _rules(payload) if row.get("type") == rule_type]
    if len(rows) != 1:
        raise ValueError(f"ruleset must contain exactly one {rule_type!r} rule")
    return rows[0]


def _canonical_rule(rule: Mapping[str, Any]) -> dict[str, Any]:
    rule_type = str(rule.get("type") or "")
    result: dict[str, Any] = {"type": rule_type}
    if rule_type not in {"pull_request", "required_status_checks"}:
        return result

    params = _mapping(rule.get("parameters"), f"{rule_type}.parameters")
    expected_fields = _PULL_REQUEST_FIELDS if rule_type == "pull_request" else _STATUS_CHECK_FIELDS
    missing = [field for field in expected_fields if field not in params]
    if missing:
        raise ValueError(f"{rule_type}.parameters is missing fields: {missing}")

    if rule_type == "pull_request":
        result["parameters"] = {field: params[field] for field in _PULL_REQUEST_FIELDS}
        return result

    checks = _list(params["required_status_checks"], "required_status_checks.parameters.required_status_checks")
    normalized_checks: list[dict[str, Any]] = []
    for index, row in enumerate(checks):
        row = _mapping(row, f"required_status_checks[{index}]")
        context = row.get("context")
        integration_id = row.get("integration_id")
        if not isinstance(context, str) or not context:
            raise ValueError(f"required_status_checks[{index}].context must be a non-empty string")
        if not isinstance(integration_id, int) or isinstance(integration_id, bool):
            raise ValueError(f"required_status_checks[{index}].integration_id must be an integer")
        normalized_checks.append({"context": context, "integration_id": integration_id})
    result["parameters"] = {
        "required_status_checks": sorted(normalized_checks, key=lambda row: row["context"]),
        "strict_required_status_checks_policy": params["strict_required_status_checks_policy"],
        "do_not_enforce_on_create": params["do_not_enforce_on_create"],
    }
    return result


def canonical_policy(payload: Mapping[str, Any]) -> dict[str, Any]:
    if "bypass_actors" not in payload:
        raise ValueError(
            "ruleset payload omitted bypass_actors; authenticated write visibility is required"
        )
    bypass_actors = _list(payload["bypass_actors"], "bypass_actors")
    conditions = _mapping(payload.get("conditions"), "conditions")
    ref_name = _mapping(conditions.get("ref_name"), "conditions.ref_name")
    include = _list(ref_name.get("include"), "conditions.ref_name.include")
    exclude = _list(ref_name.get("exclude"), "conditions.ref_name.exclude")
    return {
        "name": payload.get("name"),
        "target": payload.get("target"),
        "enforcement": payload.get("enforcement"),
        "bypass_actors": bypass_actors,
        "conditions": {"ref_name": {"include": include, "exclude": exclude}},
        "rules": sorted(
            [_canonical_rule(rule) for rule in _rules(payload)],
            key=lambda row: row["type"],
        ),
    }


def validate_contract(payload: Mapping[str, Any]) -> None:
    canonical = canonical_policy(payload)
    if canonical["name"] != "protect-main":
        raise ValueError("ruleset name must be protect-main")
    if canonical["target"] != "branch" or canonical["enforcement"] != "active":
        raise ValueError("ruleset must actively target branches")
    if canonical["bypass_actors"] != []:
        raise ValueError("ruleset must not bypass admins or other actors")

    ref = canonical["conditions"]["ref_name"]
    if ref["include"] != ["refs/heads/main"] or ref["exclude"] != []:
        raise ValueError("ruleset must target only refs/heads/main")

    rule_types = {row["type"] for row in canonical["rules"]}
    if rule_types != EXPECTED_RULE_TYPES:
        raise ValueError(f"unexpected rules: {sorted(rule_types)}")

    pr = _rule(canonical, "pull_request").get("parameters") or {}
    if pr != EXPECTED_PULL_REQUEST_PARAMETERS:
        raise ValueError(
            "pull request rule differs from the canonical squash/thread policy: "
            + json.dumps(pr, sort_keys=True)
        )

    checks = _rule(canonical, "required_status_checks").get("parameters") or {}
    if checks != EXPECTED_STATUS_CHECK_PARAMETERS:
        raise ValueError(
            "required checks must be strict, creation-enforced, and GitHub-Actions-bound: "
            + json.dumps(checks, sort_keys=True)
        )


def _headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "DocAtlas-main-ruleset/1",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _request(
    repo: str,
    path: str,
    *,
    token: str | None,
    method: str = "GET",
    body: Any = None,
) -> Any:
    url = f"https://api.github.com/repos/{repo}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            **_headers(token),
            **({"Content-Type": "application/json"} if data is not None else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(
            f"GitHub API {method} {path} failed: HTTP {exc.code}: {detail}"
        ) from exc
    return json.loads(raw) if raw else None


def _find_ruleset(repo: str, name: str, *, token: str) -> dict[str, Any] | None:
    rows = _request(
        repo,
        "/rulesets?includes_parents=false&per_page=100",
        token=token,
    )
    if not isinstance(rows, list):
        raise RuntimeError("GitHub rulesets API returned a non-list response")
    matches = [row for row in rows if isinstance(row, dict) and row.get("name") == name]
    if len(matches) > 1:
        raise RuntimeError(f"multiple repository rulesets named {name!r}")
    return matches[0] if matches else None


def check(repo: str, desired: dict[str, Any], *, token: str) -> None:
    summary = _find_ruleset(repo, desired["name"], token=token)
    if summary is None:
        raise RuntimeError(f"repository ruleset {desired['name']!r} is not configured")
    ruleset_id = summary.get("id")
    if not isinstance(ruleset_id, int) or isinstance(ruleset_id, bool):
        raise RuntimeError("repository ruleset has no numeric id")
    remote = _request(repo, f"/rulesets/{ruleset_id}", token=token)
    if not isinstance(remote, dict):
        raise RuntimeError("GitHub ruleset detail response is invalid")
    if "bypass_actors" not in remote:
        raise RuntimeError(
            "GitHub omitted bypass_actors; the token lacks ruleset write visibility, "
            "so no-bypass protection cannot be verified"
        )
    validate_contract(remote)
    expected_policy = canonical_policy(desired)
    actual_policy = canonical_policy(remote)
    if actual_policy != expected_policy:
        raise RuntimeError(
            "remote protect-main ruleset differs from the committed canonical policy\n"
            + json.dumps(
                {"expected": expected_policy, "actual": actual_policy},
                indent=2,
                sort_keys=True,
            )
        )
    print(f"Remote main ruleset: PASS (id={ruleset_id})")


def apply(repo: str, desired: dict[str, Any], *, token: str) -> None:
    summary = _find_ruleset(repo, desired["name"], token=token)
    if summary is None:
        created = _request(repo, "/rulesets", token=token, method="POST", body=desired)
        ruleset_id = (created or {}).get("id") if isinstance(created, dict) else None
        print(f"Created protect-main ruleset (id={ruleset_id})")
    else:
        ruleset_id = summary.get("id")
        if not isinstance(ruleset_id, int) or isinstance(ruleset_id, bool):
            raise RuntimeError("existing protect-main ruleset has no numeric id")
        _request(repo, f"/rulesets/{ruleset_id}", token=token, method="PUT", body=desired)
        print(f"Updated protect-main ruleset (id={ruleset_id})")
    check(repo, desired, token=token)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    try:
        desired = _load(args.config)
        validate_contract(desired)
        if args.self_test:
            print("Committed main ruleset contract: PASS")
            return 0

        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            raise RuntimeError(
                "--check/--apply require GH_TOKEN/GITHUB_TOKEN with Administration: write; "
                "without ruleset write visibility GitHub redacts bypass_actors"
            )
        if args.apply:
            apply(args.repo, desired, token=token)
        else:
            check(args.repo, desired, token=token)
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"main ruleset: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

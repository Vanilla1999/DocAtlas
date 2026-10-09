"""Public fixture reads and source-byte oracles for downstream retrieval gates."""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def bytes_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_identity(path: str | Path) -> str:
    return "local:" + hashlib.sha256(str(path).encode()).hexdigest()


def candidate_hash_material(source: dict) -> dict:
    """Public candidate hash domain, distinct from whole-document byte hashes."""
    return {
        "path": source.get("path") or source.get("source") or source.get("url") or source.get("source_url"),
        "section": source.get("heading_path") or source.get("title"),
        "content": source.get("content") or source.get("display_text"),
        "snippet": source.get("snippet") or source.get("code"),
        "version": source.get("version_binding") or source.get("version") or source.get("requested_version"),
    }


def capture_source_read(documents: dict[str, str], question: str, workspace: Path) -> dict:
    from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
    from scripts.run_project_docs_self_host_gate import _call_with_snapshot

    project = (workspace / "project").resolve()
    write_project(project, documents)
    request = {"question": question, "project_path": str(project), "scope": "project"}
    with isolated_service(workspace / "state") as (service, config):
        prepared = index_project(service, config, project)
        actual = service.materialize()
        policy = actual.member_storage_policy

        def read_state():
            return {
                "generation": policy.generation(),
                "store_sha256": bytes_sha256(policy.db_path),
                "catalog_sha256": bytes_sha256(project / "docatlas.project-docs.yaml"),
                "document_sha256": {path: bytes_sha256(project / path) for path in documents},
            }

        app = actual.unified_context
        retrieve = app.get_docs_context
        calls = []

        @wraps(retrieve)
        def observe(question_arg, **kwargs):
            calls.append({
                "question": question_arg, "scope": kwargs.get("scope"),
                "project_identity": project_identity(str(kwargs.get("project_path") or "")),
                "lookup_queries": list(kwargs.get("lookup_queries") or ()),
                "prepare_project_docs": kwargs.get("prepare_project_docs"),
                "allow_network": kwargs.get("allow_network"),
                "force_refresh": kwargs.get("force_refresh"),
            })
            return retrieve(question_arg, **kwargs)

        before = read_state()
        with patch.object(app, "get_docs_context", observe):
            payload, snapshot = _call_with_snapshot(request, service)
        after = read_state()
        payload = deepcopy(payload or {})
        diagnostics = payload.pop("diagnostics", {})
        bindings = {}
        for source in payload.get("sources") or ():
            if not isinstance(source, dict):
                continue
            evidence_id = str(source.get("evidence_id") or "")
            bound = snapshot.get(evidence_id) or {}
            bindings[evidence_id] = {
                "projected_source": deepcopy(bound.get("projected_source")),
                "candidate_hash_material": candidate_hash_material(bound.get("source") or {}),
            }
    return {
        "execution": "public_fixture_runtime",
        "project_identity": project_identity(project),
        "request": {"question": question, "scope": "project", "lookup_queries": []},
        "service_requests": calls,
        "preparation": {key: prepared[key] for key in (
            "expected_paths", "indexed_paths", "excluded_or_failed_paths", "unexpected_paths",
        )},
        "state_before": before, "state_after": after,
        "public_payload": payload, "bindings": bindings,
        "pipeline_diagnostics": {
            key: deepcopy(diagnostics.get(key)) for key in (
                "stage_status", "planned_query_ids", "observer_counts",
                "qualification_outcomes", "delivery_decision",
            ) if key in diagnostics
        },
        "error": None,
    }


def source_errors(observation: dict, documents: dict[str, str]) -> list[str]:
    """Validate final visible rows against authored bytes and same-call bindings."""
    errors = []
    payload = observation.get("public_payload") or {}
    sources = payload.get("sources")
    if not isinstance(sources, list):
        return ["sources_not_list"]
    seen = set()
    bindings = observation.get("bindings") or {}
    for source in sources:
        if not isinstance(source, dict):
            errors.append("source_not_object")
            continue
        evidence_id = source.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id or evidence_id in seen:
            errors.append("missing_or_duplicate_evidence_id")
            continue
        seen.add(evidence_id)
        path, snippet = source.get("path_or_url"), source.get("snippet")
        if not isinstance(path, str) or path not in documents:
            errors.append("source_outside_authored_members")
            continue
        raw = documents[path]
        start, end = source.get("line_start"), source.get("line_end")
        if type(start) is not int or type(end) is not int or not (1 <= start <= end <= len(raw.splitlines())):
            errors.append("invalid_source_coordinates")
        elif not isinstance(snippet, str) or not snippet or snippet not in "\n".join(raw.splitlines()[start - 1:end]):
            errors.append("visible_text_not_in_authored_range")
        if source.get("project_identity") != observation.get("project_identity"):
            errors.append("different_project_identity")
        if source.get("scope") != "project" or source.get("authority") != "source_of_truth":
            errors.append("different_authored_scope_or_authority")
        binding = bindings.get(evidence_id) or {}
        if binding.get("projected_source") != source:
            errors.append("different_same_call_source_binding")
        material = binding.get("candidate_hash_material")
        if not isinstance(material, dict) or set(material) != {"path", "section", "content", "snippet", "version"}:
            errors.append("missing_candidate_hash_material")
            continue
        if material["path"] != path or material["section"] != source.get("section"):
            errors.append("different_candidate_identity")
        for key in ("content", "snippet"):
            value = material[key]
            if value is not None and (not isinstance(value, str) or value not in raw):
                errors.append("candidate_text_not_from_authored_document")
        if not material["content"] and not material["snippet"]:
            errors.append("empty_candidate_text")
        if source.get("content_sha256") != sha256_json(material):
            errors.append("different_candidate_content_hash")
        if source.get("version_binding") != (material["version"] or "unversioned"):
            errors.append("different_candidate_version")
    if set(bindings) != seen:
        errors.append("binding_roster_mismatch")
    return sorted(set(errors))


def authority_errors(payload: dict) -> list[str]:
    errors = []
    for key in ("answer_supported", "answer_available", "edit_ready"):
        if payload.get(key) is not False:
            errors.append(key)
    for key in ("answer", "answer_text", "final_answer", "authorized_actions", "mutation_actions"):
        if payload.get(key):
            errors.append(key)
    for key in ("mutation_ready", "mutation_authorized", "edit_authorized", "authorized",
                "authorization_granted", "can_edit", "auto_execute"):
        if key in payload and payload[key] is not False:
            errors.append(key)
    return errors


RUNTIME_REQUIRED_PATHS = {
    "docmancer/mcp/_docs_server_part01.py",
    "docmancer/docs/interfaces/mcp/context_tools.py",
    "docmancer/docs/domain/documentation_query_plan.py",
    "docmancer/docs/application/project_docs_member_transaction.py",
    "docmancer/docs/application/model_visible_projection.py",
    "eval/evidence_quality_v2/runtime.py",
    "scripts/run_project_docs_self_host_gate.py",
    "eval/agent_developer_v1/current_retrieval_runtime.py",
    "eval/agent_developer_v1/paraphrase_robustness.py",
}


def build_runtime_manifest(repo_root: Path) -> dict:
    """Hash repository sources actually imported in this fixture process."""
    repo_root = repo_root.resolve()
    loaded = {}
    prefixes = ("docmancer", "eval.agent_developer_v1", "eval.evidence_quality_v2",
                "scripts.run_project_docs_self_host_gate")
    for name, module in tuple(sys.modules.items()):
        if not name.startswith(prefixes) or not getattr(module, "__file__", None):
            continue
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(repo_root) or path.suffix != ".py":
            raise ValueError(f"unreviewed downstream module import: {name}")
        loaded.setdefault(path.relative_to(repo_root).as_posix(), []).append(name)
    if not RUNTIME_REQUIRED_PATHS <= set(loaded):
        raise ValueError("downstream runtime import inventory is incomplete")
    rows = [{"path": path, "sha256": bytes_sha256(repo_root / path), "imported_as": sorted(names)}
            for path, names in sorted(loaded.items())]
    return {"algorithm": "same-process-source-sha256-v1", "files": rows, "sha256": sha256_json(rows)}


def verify_runtime_manifest(manifest: dict, repo_root: Path) -> None:
    if not isinstance(manifest, dict) or set(manifest) != {"algorithm", "files", "sha256"}:
        raise ValueError("P1.4 runtime manifest shape is invalid")
    if manifest["algorithm"] != "same-process-source-sha256-v1":
        raise ValueError("P1.4 runtime manifest algorithm is invalid")
    rows = manifest["files"]
    if not isinstance(rows, list) or not rows or manifest["sha256"] != sha256_json(rows):
        raise ValueError("P1.4 runtime manifest digest mismatch")
    paths = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "imported_as"}:
            raise ValueError("P1.4 runtime manifest row is malformed")
        path = row["path"]
        if (not isinstance(path, str) or path.startswith(("/", "\\")) or ".." in Path(path).parts
                or not isinstance(row["imported_as"], list) or not row["imported_as"]
                or any(not isinstance(name, str) or not name for name in row["imported_as"])):
            raise ValueError("P1.4 runtime manifest import identity is invalid")
        if not (repo_root / path).is_file() or bytes_sha256(repo_root / path) != row["sha256"]:
            raise ValueError("P1.4 runtime manifest differs from current checkout")
        paths.append(path)
    if paths != sorted(set(paths)) or not RUNTIME_REQUIRED_PATHS <= set(paths):
        raise ValueError("P1.4 runtime manifest inventory is incomplete")

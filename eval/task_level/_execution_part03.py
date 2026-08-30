"""Implementation shard 3 for execution."""
from __future__ import annotations

from ._execution_shared import *  # noqa: F401,F403

from ._execution_part01 import _activated_run_environment, _bounded_direct_projection_errors, _directory_sha256, _estimate_tokens, _write_json_atomic, fresh_run_environment
from ._execution_part02 import _host_evidence_categories, _replace_path_in_json

def _prepare_shared_task33_evidence(
    task: TaskSpec,
    runtime_root: Path,
    repeat: int,
) -> tuple[HostEvidenceSnapshot, dict[str, Any]]:
    seed_root = runtime_root / task.task_id / f"repeat_{repeat}" / "bounded-evidence-seed"
    workspace = seed_root / "workspace"
    output_dir = seed_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    materialized = materialize_fixture(task, workspace)
    contract = TASK33_EVALUATION_CONTRACTS.get(task.task_id)
    if task.task_id in TASK23_PROTOCOL_TASKS and (
        contract is None
        or materialized.get("fixture_hash") != contract.fixture_sha256
        or materialized.get("protocol_fixture_hash") != contract.protocol_fixture_sha256
    ):
        raise IsolatedDeliveryError("task33_shared_fixture_identity_mismatch")
    env = fresh_run_environment(output_dir)
    preparation = prepare_docatlas(task, workspace, output_dir, env)
    if preparation.get("status") == "condition_setup_failed":
        raise IsolatedDeliveryError("task33_shared_docatlas_preparation_failed")
    index_revision = _directory_sha256(Path(env["DOCATLAS_HOME"]))
    evidence = capture_task33_host_evidence(
        task,
        workspace,
        output_dir,
        env,
        project_revision=str(materialized["fixture_hash"]),
        index_revision=index_revision,
    )
    missing = sorted(set(TASK33C_REQUIRED_EVIDENCE_CATEGORIES) - set(evidence.evidence_categories))
    if missing:
        raise IsolatedDeliveryError("task33_shared_evidence_categories_missing:" + ",".join(missing))
    sanitized_preparation = _replace_path_in_json(preparation, seed_root, "<task33-shared-capture>")
    sanitized_preparation["shared_frozen_capture"] = True
    sanitized_preparation["evidence_fingerprint"] = evidence.fingerprint
    sanitized_preparation["index_revision"] = evidence.index_revision
    return evidence, sanitized_preparation


def prepare_docatlas(task: TaskSpec, workspace: Path, output_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    started = time.monotonic()
    sync_status = "not_run"
    sync_error = None
    sync_counts = {
        "current": 0,
        "new": 0,
        "changed": 0,
        "orphaned_removed": 0,
        "stale_removed": 0,
        "sections_indexed": 0,
    }
    try:
        from docmancer.docs.service import LibraryDocsService

        with _activated_run_environment(env):
            sync_result = LibraryDocsService().sync_project_docs(str(workspace), with_vectors=False)
            sync_status = getattr(sync_result, "status", "success")
            sync_counts = {
                "current": int(getattr(sync_result, "current_count", 0) or 0),
                "new": int(getattr(sync_result, "new_count", 0) or 0),
                "changed": int(getattr(sync_result, "changed_count", 0) or 0),
                "orphaned_removed": int(
                    getattr(sync_result, "orphaned_removed", 0) or 0
                ),
                "stale_removed": int(getattr(sync_result, "stale_removed", 0) or 0),
                "sections_indexed": int(
                    getattr(sync_result, "sections_indexed", 0) or 0
                ),
            }
    except Exception as exc:
        sync_status = "failed"
        sync_error = repr(exc)

    index_changed = any(
        sync_counts[key]
        for key in (
            "new",
            "changed",
            "orphaned_removed",
            "stale_removed",
            "sections_indexed",
        )
    )
    if sync_status == "failed":
        index_state = "condition_setup_failed"
    elif sync_counts["current"] > 0 and not index_changed:
        index_state = "already_current"
    else:
        index_state = "updated_local"
    diagnostics = {
        "task_id": task.task_id,
        "status": "prepared_with_local_project_docs_only" if sync_status != "failed" else "condition_setup_failed",
        "allow_network": False,
        "docmancer_home": env["DOCATLAS_HOME"],
        "project_docs_sync_status": sync_status,
        "project_docs_sync_error": sync_error,
        "index_state": index_state,
        "with_vectors": False,
        "provider_input_tokens": 0,
        "provider_output_tokens": 0,
        "sync_counts": sync_counts,
        "sources": ["fixture README/docs", "FastAPI docs preindex not fetched during unit validation"],
        "pages": 1 if sync_status != "failed" else 0,
        "chunks": 1 if sync_status != "failed" else 0,
        "expected_domains_present": [],
        "contamination": 0,
        "wall_time_seconds": round(time.monotonic() - started, 4),
        "limitation": "Offline pilot preparation syncs project-owned docs only. Exact dependency docs must already be locally cached; no network fetch is performed.",
    }
    (output_dir / "docatlas_preparation.json").write_text(json.dumps(diagnostics, indent=2, sort_keys=True), encoding="utf-8")
    return diagnostics


def capture_task33_host_evidence(
    task: TaskSpec,
    workspace: Path,
    output_dir: Path,
    env: dict[str, str],
    *,
    project_revision: str,
    index_revision: str,
) -> HostEvidenceSnapshot:
    """Run the frozen host retrieval once for both bounded delivery lanes."""

    from docmancer.docs.service import LibraryDocsService

    started = time.monotonic()
    retrieval_query = derive_task33_retrieval_query(task.issue_text)
    objective_sha256 = hashlib.sha256(task.issue_text.encode("utf-8")).hexdigest()
    old_handler = signal.getsignal(signal.SIGALRM)

    def _timeout_handler(_signum: int, _frame: Any) -> None:
        raise TimeoutError("Task 33 host retrieval exceeded 45 seconds")

    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(45)
    try:
        with _activated_run_environment(env):
            result = LibraryDocsService().get_docs_context(
                retrieval_query,
                project_path=str(workspace),
                library=None,
                ecosystem=task.ecosystem,
                version=None,
                mode="project",
                response_style="snippet-first",
                allow_network=False,
                allow_latest_fallback=False,
                tokens=4_000,
                limit=12,
            )
        response = _replace_path_in_json(_jsonable(result), workspace, "<repo>")
        retrieved_context_pack = tuple(
            dict(item) for item in response.get("context_pack", []) if isinstance(item, dict)
        )
        context_pack = _augment_task33_host_context(
            workspace,
            retrieval_query,
            retrieved_context_pack,
        )
    except Exception as exc:
        raise IsolatedDeliveryError(f"host_retrieval_failed:{exc.__class__.__name__}") from exc
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    status = str(response.get("status") or "unknown")
    trust_contract = response.get("trust_contract") if isinstance(response.get("trust_contract"), dict) else {}
    retrieval_issues = list(bounded_patch_retrieval_issues(response))
    available_paths = {
        str(item.get("path") or "").strip().replace("\\", "/") for item in context_pack
    }
    for required_path in TASK33C_REQUIRED_EVIDENCE_PATHS:
        if required_path not in available_paths:
            retrieval_issues.append("missing_required_evidence_path:" + required_path)
    issues = tuple(dict.fromkeys(retrieval_issues))
    categories = _host_evidence_categories(context_pack)
    accounted_response = dict(response)
    accounted_response["context_pack"] = list(context_pack)
    wall = round(time.monotonic() - started, 6)
    snapshot = HostEvidenceSnapshot(
        query=retrieval_query,
        objective_sha256=objective_sha256,
        query_derivation=TASK33_QUERY_DERIVATION,
        evidence_items=context_pack,
        trust_contract=trust_contract,
        retrieval_issues=issues,
        evidence_categories=categories,
        project_revision=project_revision,
        index_revision=index_revision,
        response_status=status,
        raw_retrieval_tokens=_estimate_tokens(json.dumps(
            accounted_response,
            ensure_ascii=False,
            sort_keys=True,
        )),
        retrieval_wall_time_seconds=wall,
    )
    snapshot.validate()
    persist_host_evidence(snapshot, output_dir)
    _write_json_atomic(output_dir / "host_retrieval_metrics.json", {
        "schema_version": 1,
        "status": status,
        "retrieval_calls": 1,
        "query": retrieval_query,
        "query_sha256": hashlib.sha256(retrieval_query.encode("utf-8")).hexdigest(),
        "objective_sha256": objective_sha256,
        "query_derivation": snapshot.query_derivation,
        "evidence_fingerprint": snapshot.fingerprint,
        "evidence_count": len(context_pack),
        "evidence_categories": list(categories),
        "project_revision": project_revision,
        "index_revision": index_revision,
        "raw_retrieval_tokens": snapshot.raw_retrieval_tokens,
        "retrieval_wall_time_seconds": wall,
        "retrieval_issues": list(issues),
    })
    return snapshot


def _augment_task33_host_context(
    workspace: Path,
    query: str,
    retrieved_items: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    """Add bounded deterministic local evidence without another retrieval call."""

    from docmancer.docs.domain.project_doc_ranking import project_source_taxonomy
    from docmancer.docs.domain.content_trust import annotate_context_pack
    from docmancer.docs.domain.source_map import (
        build_project_repo_map,
        build_project_source_evidence,
    )
    from docmancer.docs.project import ProjectMetadataReader

    root = workspace.resolve()
    query_terms = {
        term.lower()
        for term in re.findall(r"[A-Za-z0-9_]+", query)
        if len(term) >= 3
    }
    ranked_docs: list[tuple[int, str, dict[str, Any]]] = []
    metadata = ProjectMetadataReader().read(root, docs_candidate_limit=64)
    for candidate in metadata.docs_candidates:
        relative = str(candidate.path or "").strip().replace("\\", "/")
        path = (root / relative).resolve()
        if not relative or not path.is_relative_to(root) or not path.is_file():
            continue
        content = path.read_text(encoding="utf-8", errors="replace")[:4_000]
        searchable = " ".join((relative, str(candidate.description or ""), content)).lower()
        score = sum(term in searchable for term in query_terms)
        if not score:
            continue
        taxonomy = project_source_taxonomy(
            relative,
            doc_scope=candidate.doc_scope,
            module_path=candidate.module_path,
        )
        item = {
            "stable_chunk_id": "local-doc-" + hashlib.sha256(
                f"{relative}\0{content}".encode("utf-8")
            ).hexdigest()[:40],
            "parent_logical_id": "local-parent-" + hashlib.sha256(
                relative.encode("utf-8")
            ).hexdigest()[:40],
            "display_content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "display_text": content,
            "source_class": "project_doc",
            "source_type": taxonomy["source_type"],
            "source_kind": taxonomy["source_kind"],
            "authority": candidate.authority or taxonomy["authority"],
            "risk_flags": taxonomy["risk_flags"],
            "doc_scope": candidate.doc_scope,
            "module_path": candidate.module_path,
            "description": candidate.description,
            "lifecycle_status": candidate.lifecycle_status,
            "impact_policy": candidate.impact_policy,
            "path": relative,
            "title": relative,
            "heading_path": relative,
            "freshness": "current",
            "why_selected": "derived retrieval query matched discovered project documentation",
            "content": content,
            "token_estimate": max(1, len(content) // 4),
        }
        ranked_docs.append((score, relative, item))

    local_items = [
        item for _, _, item in sorted(ranked_docs, key=lambda row: (-row[0], row[1]))[:6]
    ]
    local_items.extend(
        item
        for item in build_project_source_evidence(
            root,
            question=query,
            max_items=8,
            token_budget=1_500,
        )
        if item.get("evidence_class") == "source_snippet"
    )
    local_items.extend(build_project_repo_map(
        root,
        question=query,
        max_files=8,
        token_budget=2_000,
    ))
    for item in local_items:
        item.setdefault("origin_lane", "project")
    local_items, _ = annotate_context_pack(local_items, repository_root=root)

    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in (*retrieved_items, *local_items):
        key = (
            str(item.get("source_class") or ""),
            str(item.get("path") or ""),
            str(item.get("line_start") or ""),
            str(item.get("heading_path") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(item))
    return tuple(merged)


def inject_docatlas_context(task: TaskSpec, workspace: Path, output_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    started = time.monotonic()
    fallback_reason: str | None = None
    try:
        from docmancer.docs.service import LibraryDocsService

        old_handler = signal.getsignal(signal.SIGALRM)

        def _timeout_handler(_signum: int, _frame: Any) -> None:
            raise TimeoutError("DocAtlas context injection exceeded 45 seconds")

        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(45)
        try:
            with _activated_run_environment(env):
                dependency = task.dependencies[0] if task.dependencies else None
                result = LibraryDocsService().get_docs_context(
                    task.issue_text,
                    project_path=str(workspace),
                    library=None if task.task_id.startswith("real_project_") else dependency.name if dependency else None,
                    ecosystem=task.ecosystem,
                    version=None if task.task_id.startswith("real_project_") else dependency.version if dependency else None,
                    mode="project" if task.task_id.startswith("real_project_") else "auto",
                    response_style="snippet-first",
                    allow_network=False,
                    allow_latest_fallback=False,
                    tokens=2500,
                    limit=6,
                )
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    except Exception as exc:
        fallback_reason = repr(exc)
        result = _fallback_project_context(task, workspace, fallback_reason)

    response = _jsonable(result)
    (output_dir / "docatlas_response.json").write_text(json.dumps(response, indent=2, sort_keys=True), encoding="utf-8")
    sources = _extract_context_sources(response)[:6]
    (output_dir / "context_sources.json").write_text(json.dumps(sources, indent=2, sort_keys=True), encoding="utf-8")
    markdown = format_injected_context(response, sources)
    if len(markdown) > CONTEXT_INJECTION_LIMIT_CHARS:
        markdown = markdown[:CONTEXT_INJECTION_LIMIT_CHARS] + "\n\n[truncated by benchmark harness]\n"
    (output_dir / "injected_context.md").write_text(markdown, encoding="utf-8")
    raw_json = json.dumps(response, sort_keys=True)
    payload = {
        "status": "success" if fallback_reason is None else "fallback_local_project_context",
        "docatlas_retrieval_status": "success" if fallback_reason is None else "fallback_local_project_context",
        "vector_indexing_timed_out": bool(fallback_reason and "exceeded 45 seconds" in fallback_reason),
        "fallback_used": fallback_reason is not None,
        "fallback_source": "visible_fixture_project_docs" if fallback_reason is not None else None,
        "docatlas_tool_success": fallback_reason is None,
        "docatlas_fallback_success": fallback_reason is not None,
        "harness_docatlas_calls": 1 if fallback_reason is None else 0,
        "sources": len(sources),
        "injected_context_tokens": _estimate_tokens(markdown),
        "retrieved_context_tokens": _estimate_tokens(raw_json),
        "raw_doc_context_tokens": _estimate_tokens(raw_json),
        "fallback_reason": fallback_reason,
        "wall_time_seconds": round(time.monotonic() - started, 4),
    }
    (output_dir / "docatlas_context_injection.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def build_bounded_direct_packet(
    task: TaskSpec,
    workspace: Path,
    output_dir: Path,
    evidence: HostEvidenceSnapshot,
) -> dict[str, Any]:
    """Format the same frozen host evidence supplied to the isolated worker."""

    from docmancer.docs.application.action_packet import build_action_packet, validate_action_packet
    from docmancer.docs.application.model_visible_projection import (
        project_patch_context,
        validate_model_visible_projection,
    )

    evidence.validate()
    packet_evidence = [
        *evidence.evidence_items,
        build_task33c_validation_evidence(task.test_command),
    ]
    packet = build_action_packet(
        question=task.issue_text,
        context_pack=packet_evidence,
        trust_contract=evidence.trust_contract,
        # Leave headroom, then enforce the authoritative serialized limit below.
        max_tokens=1_960,
        project_path=str(workspace),
        retrieval_issues=evidence.retrieval_issues,
        required_evidence_paths=(
            *TASK33C_REQUIRED_EVIDENCE_PATHS,
            "host-policy://task33c/validation",
        ),
        required_target_paths=TASK33C_REQUIRED_TARGET_PATHS,
        behavioral_contract_required=True,
    )
    errors = validate_action_packet(
        packet,
        evidence_items=packet_evidence,
        max_tokens=2_000,
        project_path=str(workspace),
    )
    if errors:
        raise IsolatedDeliveryError("invalid_bounded_direct_packet:" + ";".join(errors))
    missing_categories = missing_packet_evidence_categories(
        packet,
        evidence.evidence_items,
        TASK33C_REQUIRED_EVIDENCE_CATEGORIES,
    )
    if packet.get("status") != "insufficient_evidence" and missing_categories:
        raise IsolatedDeliveryError(
            "bounded_direct_missing_required_evidence_categories:" + ",".join(missing_categories)
        )
    missing_paths = missing_packet_evidence_paths(
        packet, evidence.evidence_items, TASK33C_REQUIRED_EVIDENCE_PATHS
    )
    if packet.get("status") != "insufficient_evidence" and missing_paths:
        raise IsolatedDeliveryError(
            "bounded_direct_missing_required_evidence_paths:" + ",".join(missing_paths)
        )
    contract = TASK33_EVALUATION_CONTRACTS.get(task.task_id)
    target_surface = packet.get("target_surface") if isinstance(packet.get("target_surface"), dict) else {}
    packet_targets = {
        str(row.get("path") or "").strip().replace("\\", "/")
        for row in target_surface.get("likely_files", [])
        if isinstance(row, dict)
    }
    missing_targets = sorted(set(contract.allowed_paths if contract else ()) - packet_targets)
    if packet.get("status") != "insufficient_evidence" and missing_targets:
        raise IsolatedDeliveryError(
            "bounded_direct_missing_required_target_modules:" + ",".join(missing_targets)
        )
    projection, projection_snapshot = project_patch_context(
        packet=packet,
        evidence_items=packet_evidence,
        max_tokens=2_000,
    )
    projection_errors = _bounded_direct_projection_errors(
        projection,
        validate_model_visible_projection(
            projection,
            snapshot=projection_snapshot,
            max_tokens=2_000,
        ),
    )
    if projection_errors:
        raise IsolatedDeliveryError(
            "invalid_bounded_direct_projection:" + ";".join(projection_errors)
        )
    persist_host_evidence(evidence, output_dir)
    _write_json_atomic(output_dir / "action_packet.json", packet)
    _write_json_atomic(output_dir / "model_visible_patch_context.json", projection)
    _write_json_atomic(output_dir / "model_visible_evidence_snapshot.json", projection_snapshot)
    _write_json_atomic(output_dir / "bounded_direct_metrics.json", {
        "schema_version": 2,
        "strategy": "bounded_direct",
        "status": packet["status"],
        "attempts": 1,
        "retrieval_calls": evidence.retrieval_calls,
        "parent_visible_raw_retrieval": False,
        "parent_packet_tokens": packet["estimated_tokens"],
        "model_visible_projection_tokens": projection["estimated_tokens"],
        "raw_retrieval_tokens": evidence.raw_retrieval_tokens,
        "retrieval_wall_time_seconds": evidence.retrieval_wall_time_seconds,
        "evidence_fingerprint": evidence.fingerprint,
        "project_revision": evidence.project_revision,
        "index_revision": evidence.index_revision,
    })
    return packet


def _fallback_project_context(task: TaskSpec, workspace: Path, reason: str) -> dict[str, Any]:
    items = []
    selected = []
    for relative in task.expected_project_docs[:6]:
        path = workspace / relative
        if path.exists() and path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")[:1600]
            items.append({"content": text, "source": {"kind": "project_doc", "path": relative}})
            selected.append({"source": {"kind": "project_doc", "path": relative}, "reason": "fallback expected project doc"})
    return {
        "mode": "project_fallback",
        "reason_code": "docatlas_context_timeout_fallback",
        "warnings": [f"DocAtlas context retrieval failed; benchmark used visible project-doc fallback: {reason}"],
        "context_pack": items,
        "trust_contract": {"selected": selected, "risky": [], "rejected": []},
    }


def format_injected_context(response: dict[str, Any], sources: list[dict[str, Any]]) -> str:
    trust = response.get("trust_contract", {}) if isinstance(response.get("trust_contract"), dict) else {}
    routing = response.get("routing", {}) if isinstance(response.get("routing"), dict) else {}
    items = response.get("context_pack") or response.get("items") or response.get("context") or []
    snippets: list[str] = []
    if isinstance(items, list):
        for item in items[:2]:
            if isinstance(item, dict):
                snippet = item.get("snippet") or item.get("content") or item.get("text") or item.get("summary")
                if snippet:
                    snippets.append(str(snippet)[:1600])
    lines = [
        "## Verified DocAtlas context",
        "",
        "Routing:",
        f"- mode_selected: {response.get('mode') or routing.get('mode_selected') or 'auto'}",
        f"- reason: {routing.get('reason') or response.get('reason_code') or 'DocAtlas offline context route'}",
        "",
    ]
    for index, snippet in enumerate(snippets, start=1):
        lines.extend([f"Primary snippet {index}:", "```text", snippet, "```", ""])
    lines.extend(["Project constraints:"])
    for source in sources:
        if str(source.get("kind", "")).startswith("project"):
            lines.append(f"- Follow project source {source.get('path') or source.get('title')}")
    if not any(str(source.get("kind", "")).startswith("project") for source in sources):
        lines.append("- No project-specific constraint source selected by DocAtlas.")
    lines.extend(["", "Sources:"])
    for index, source in enumerate(sources, start=1):
        label = source.get("kind") or "source"
        path = source.get("path") or source.get("url") or source.get("title") or "unknown"
        why = source.get("why") or source.get("freshness") or "selected by DocAtlas"
        lines.append(f"{index}. [{label}] {path} - {why}")
    raw_sources = trust.get("sources")
    trust_sources: dict[str, Any] = raw_sources if isinstance(raw_sources, dict) else {}
    selected = trust_sources.get("selected") or trust.get("selected") or trust.get("selected_sources") or []
    risky = trust_sources.get("risky") or trust.get("risky") or []
    rejected = trust_sources.get("rejected") or trust.get("rejected") or []
    lines.extend([
        "",
        "Trust Contract:",
        f"- selected: {len(selected) if isinstance(selected, list) else 0}",
        f"- risky: {len(risky) if isinstance(risky, list) else 0}",
        f"- rejected: {len(rejected) if isinstance(rejected, list) else 0}",
        "",
        "Warnings:",
    ])
    warnings = response.get("warnings") if isinstance(response.get("warnings"), list) else []
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings[:4])
    else:
        lines.append("- No DocAtlas warnings reported.")
    return "\n".join(lines)


def _extract_context_sources(response: dict[str, Any]) -> list[dict[str, Any]]:
    trust = response.get("trust_contract", {}) if isinstance(response.get("trust_contract"), dict) else {}
    raw_sources = trust.get("sources")
    trust_sources: dict[str, Any] = raw_sources if isinstance(raw_sources, dict) else {}
    candidates = trust_sources.get("selected") or trust.get("selected") or trust.get("selected_sources") or response.get("sources") or []
    sources: list[dict[str, Any]] = []
    if isinstance(candidates, list):
        for item in candidates:
            if isinstance(item, dict):
                source = item.get("source") if isinstance(item.get("source"), dict) else item
                sources.append({
                    "kind": source.get("kind") or source.get("type") or source.get("source_type") or "project",
                    "path": source.get("path") or source.get("url") or source.get("title"),
                    "title": source.get("title"),
                    "why": item.get("why") or item.get("reason"),
                    "freshness": source.get("freshness"),
                })
    return sources


def _jsonable(value: Any) -> Any:
    if hasattr(value, "__dict__"):
        return _jsonable(value.__dict__)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def runner_unavailable_result(task: TaskSpec, condition_id: str, run_output_dir: Path, exc: Exception, *, runner_id: str, model: str) -> dict[str, Any]:
    (run_output_dir / "patch.diff").write_text("", encoding="utf-8")
    (run_output_dir / "changed_files.json").write_text("[]\n", encoding="utf-8")
    validation = {"constraint_validation": {"total_constraints": 0, "satisfied": 0, "violated": 0, "unknown": 0, "violations": []}}
    (run_output_dir / "validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    error_payload = {
        "type": exc.__class__.__name__,
        "message": str(exc),
        "traceback_tail": traceback.format_exc().splitlines()[-8:],
    }
    (run_output_dir / "runner_error.json").write_text(json.dumps(error_payload, indent=2, sort_keys=True), encoding="utf-8")
    result = {
        "run_id": run_output_dir.parents[2].name,
        "task_id": task.task_id,
        "condition_id": condition_id,
        "repeat": int(run_output_dir.name.removeprefix("repeat_")),
        "runner_id": runner_id,
        "runner_version": "unavailable",
        "model": model,
        "status": "runner_unavailable",
        "resolved": False,
        "public_tests_passed": False,
        "hidden_tests_passed": False,
        "tests_passed": False,
        "compile_success": False,
        "policy_clean": True,
        "policy": {"clean": True, "violations": [], "network_attempts": 0, "runner_unavailable": True},
        "docatlas": {"available": condition_id in DOCATLAS_CONDITIONS, "harness_calls": 0, "agent_calls": 0, "context_retrieved": False, "context_injected": False, "context_used": False, "fallback_used": False},
        "contract": {},
        "actionability": {"checklist_items": [], "action_checklist_used": False},
        "patch_constraints": {"constraint_count": 0, "constraint_used": False, "constraint_packet_tokens": None},
        "constraint_validation": validation["constraint_validation"],
        "constraint_packet_tokens": None,
        "constraint_count": 0,
        "constraint_used": False,
        "constraint_violations_after_patch": 0,
        "unknown_count": 0,
        "patch_path": str(run_output_dir / "patch.diff"),
        "trajectory_path": None,
        "changed_files": [],
        "forbidden_changes": [],
        "metrics": {"wall_time_seconds": 0.0, "input_tokens": None, "output_tokens": None, "fallback_used": False},
        "notes": [f"Runner unavailable before patch generation: {exc.__class__.__name__}: {exc}"],
    }
    (run_output_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result

__all__=['_prepare_shared_task33_evidence', 'prepare_docatlas', 'capture_task33_host_evidence', '_augment_task33_host_context', 'inject_docatlas_context', 'build_bounded_direct_packet', '_fallback_project_context', 'format_injected_context', '_extract_context_sources', '_jsonable', 'runner_unavailable_result']

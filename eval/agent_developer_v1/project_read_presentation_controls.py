"""Native current-window presentation controls inside the existing member test.

One real public read owns its acquisition receipt. Subsequent explicitly labelled
operand replays exercise the same production boundaries without another search.
"""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from dataclasses import asdict, replace
from functools import wraps
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.docs.interfaces.mcp import context_tools
from docmancer.docs.models import DeliveryDecision, DocsChunk, DocsResult
from docmancer.mcp._docs_server_part01 import call_docs_tool_payload
from docmancer.retrieval.dispatch import RetrievalDispatcher
from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project


def run_project_read_presentation_controls(workspace: Path, storage_state):
    question = "How is the host receipt assembled?"
    lookups = ("AlphaWindowRecord", "BetaWindowRecord")
    documents = {
        f"manual/{lane}-{index:02d}.md":
            f"λ entry {index:02d}. {symbol} retains revision {index:02d} for six cycles."
        for lane, symbol in (("alpha", lookups[0]), ("beta", lookups[1]))
        for index in range(12)
    }
    project = (workspace / "project").resolve()
    write_project(project, documents)
    request = {"question": question, "project_path": str(project),
               "scope": "project", "lookup_queries": list(lookups)}
    labels = []

    def require(condition, guard, detail=None):
        if not condition:
            if detail is not None:
                print("PROJECT_READ_PRESENTATION_FAILURE " + json.dumps(
                    {"guard": guard, "detail": detail}, sort_keys=True, ensure_ascii=False, default=str))
            raise AssertionError(guard)

    def digest(value):
        return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()

    def no_authority(payload):
        require(all(payload.get(key) is False for key in (
            "answer_supported", "answer_available", "edit_ready",
        )), "critical_project_read_no_answer_or_edit")
        require("query-original" not in payload.get("covered_query_ids", ())
                and not payload.get("answer_evidence_ids") and not payload.get("answer"),
                "critical_project_read_no_original_credit")

    with isolated_service(workspace / "state") as (service, config):
        prepared = index_project(service, config, project)
        require(prepared["expected_paths"] == prepared["indexed_paths"] == sorted(documents)
                and not prepared["excluded_or_failed_paths"] and not prepared["unexpected_paths"],
                "critical_project_read_finite_preparation", prepared)
        policy = service.member_storage_policy
        generation = prepared["generation_id"]
        identity = "local:" + digest(str(project))
        with closing(policy.connect()) as connection:
            children = [dict(row) for row in connection.execute(
                "SELECT c.*, p.source_content_hash AS committed_source_content_hash "
                "FROM retrieval_children c JOIN retrieval_parents p "
                "ON p.generation_id = c.generation_id AND p.logical_id = c.parent_logical_id "
                "WHERE c.generation_id = ?", (generation,))]
        by_path = {row["source_path"]: row for row in children}
        require(len(children) == len(by_path) == 24 and set(by_path) == set(documents),
                "critical_project_read_unique_children")
        for path, child in by_path.items():
            body = documents[path]
            require(child["display_text"] == body
                    and child["committed_source_content_hash"] == child["display_content_hash"] == digest(body)
                    and child["project_identity"] == identity and child["source_class"] == "project_file"
                    and child["doc_scope"] == "project" and child["generation_id"] == generation
                    and child["char_start"] == child["byte_start"] == 0
                    and child["char_end"] == len(body) and child["byte_end"] == len(body.encode("utf-8")),
                    "critical_project_read_prepared_bytes", {"path": path})

        def state():
            return {"storage": storage_state(policy), "generation": policy.generation(),
                    "catalog": digest((project / "docatlas.project-docs.yaml").read_bytes()),
                    "documents": {path: digest((project / path).read_bytes()) for path in documents}}

        before = state()
        actual = service.materialize(read_only_startup=True)
        get_member, get_project = actual.get_project_docs, actual.get_project_context
        app = actual.unified_context
        get_unified, dispatch = app.get_docs_context, RetrievalDispatcher.run
        validate = context_tools.validate_model_visible_projection
        projector = context_tools.project_docs_context
        projector_inputs = []
        member_returns, project_returns, unified_returns, snapshots = [], [], [], []
        project_calls, dispatch_calls = [], []

        @wraps(get_member)
        def observe_member(*args, **kwargs):
            result = get_member(*args, **kwargs)
            member_returns.append(deepcopy(result))
            return result

        @wraps(get_project)
        def observe_project(*args, **kwargs):
            result = get_project(*args, **kwargs)
            project_calls.append((deepcopy(args), deepcopy(kwargs)))
            project_returns.append(deepcopy(result))
            return result

        @wraps(get_unified)
        def observe_unified(*args, **kwargs):
            result = get_unified(*args, **kwargs)
            unified_returns.append(deepcopy(result))
            return result

        @wraps(dispatch)
        def observe_dispatch(owner, query, *args, **kwargs):
            result = dispatch(owner, query, *args, **kwargs)
            dispatch_calls.append({"query": query, "args": args, "kwargs": deepcopy(kwargs),
                                   "returned": len(result.chunks)})
            return result

        @wraps(projector)
        def observe_projector(*args, **kwargs):
            before_projection = deepcopy(kwargs["retrieval"])
            result = projector(*args, **kwargs)
            projector_inputs.append(before_projection)
            return result

        @wraps(validate)
        def observe_validation(payload, *, snapshot, **kwargs):
            errors = validate(payload, snapshot=snapshot, **kwargs)
            snapshots.append(deepcopy(snapshot))
            return errors

        with (patch.object(actual, "get_project_docs", observe_member),
              patch.object(actual, "get_project_context", observe_project),
              patch.object(app, "get_docs_context", observe_unified),
              patch.object(RetrievalDispatcher, "run", observe_dispatch),
              patch.object(context_tools, "project_docs_context", observe_projector),
              patch.object(context_tools, "validate_model_visible_projection", observe_validation)):
            payload = call_docs_tool_payload("get_docs_context", request, actual)
        require(state() == before, "critical_project_read_state")
        require(len(member_returns) == len(project_returns) == len(unified_returns) == len(snapshots) == len(projector_inputs) == 1,
                "critical_project_read_single_native_call",
                {"member": len(member_returns), "project": len(project_returns),
                 "unified": len(unified_returns), "snapshots": len(snapshots), "projectors": len(projector_inputs),
                 "status": payload.get("status"), "error": payload.get("error")})
        require([row["query"] for row in dispatch_calls] == [question, question, *lookups]
                and all(not row["args"] and row["kwargs"].get("limit") == 20
                        and row["kwargs"].get("mode") == "lexical"
                        and row["kwargs"].get("expand") == "none"
                        and type(row["kwargs"].get("budget")) is int
                        and 0 < row["kwargs"]["budget"] <= 20_000 for row in dispatch_calls)
                and len({row["kwargs"]["budget"] for row in dispatch_calls}) == 1,
                "critical_project_read_acquisition_bound",
                [{key: row["kwargs"].get(key) for key in ("mode", "limit", "budget", "expand")}
                 for row in dispatch_calls])
        for index, row in enumerate(dispatch_calls):
            filters = row["kwargs"]["filters"]
            require(filters["project_path"] == str(project) and filters["project_identity"] == identity
                    and filters["source_class"] == "project_file" and filters["doc_scope"] == "project"
                    and ("authority" not in filters if index != 1 else filters["authority"] == "source_of_truth"),
                    "critical_project_read_acquisition_scope")
        member, context, unified = member_returns[0], project_returns[0], unified_returns[0]
        require(member.status == "success" and not member.requires_confirmation
                and len(member.results) == 24
                and {row.stable_chunk_id for row in member.results} == {row["stable_chunk_id"] for row in children},
                "critical_project_read_acquired_qualified",
                {"status": member.status, "count": len(member.results)})
        for row in member.results:
            expected_id = "query-lookup-1" if "/alpha-" in row.path else "query-lookup-2"
            traces = row.metadata["retrieval_query_matches"]
            require(row.path in documents and row.content == documents[row.path]
                    and row.content_hash == "sha256:" + digest(documents[row.path])
                    and {key for key, trace in traces.items() if trace.get("qualified") is True} == {expected_id}
                    and traces[expected_id]["query_text"] == lookups[int(expected_id[-1]) - 1]
                    and traces["query-original"]["query_text"] == question
                    and traces["query-original"]["qualified"] is False,
                    "critical_project_read_acquired_qualified", {"path": row.path})

        stage = context.diagnostics["retrieval_routing"]["stages"]["project_docs"]
        require(stage["budget_exceeded"] is True and stage["observed_item_count"] == 24
                and stage["item_count"] == 20 and stage["status"] == "insufficient"
                and stage["observed_budget_projection_bytes"] < 65536
                and len(context.project_docs.results) == 20
                and "retrieval_stage_budget_exceeded" in context.warnings,
                "critical_project_read_bounded_control", stage)
        expected_ids = {row["stable_chunk_id"] for row in children}
        for result in (context, unified):
            pack = result.context_pack
            require(len(pack) == 24 and {row["stable_chunk_id"] for row in pack} == expected_ids
                    and result.delivery_decision is not None and result.delivery_decision.deliverable is True,
                    "critical_project_read_preserves_acquired_windows",
                    {"type": type(result).__name__, "count": len(pack),
                     "delivery": asdict(result.delivery_decision) if result.delivery_decision else None})
            require(result.answer_available is False and not result.requires_confirmation,
                    "critical_project_read_no_answer_or_edit")
            for row in pack:
                child = by_path[row["path"]]
                expected_id = "query-lookup-1" if "/alpha-" in row["path"] else "query-lookup-2"
                require(row["content"] == row["display_text"] == documents[row["path"]]
                        and row["project_identity"] == identity and row["doc_scope"] == "project"
                        and row["source_class"] == "project_doc" and row["generation_id"] == generation
                        and row["_source_snapshot_sha256"] == "sha256:" + child["committed_source_content_hash"]
                        and all(row.get(field) == child[field] for field in (
                            "stable_chunk_id", "parent_logical_id", "source_identity", "display_content_hash",
                            "char_start", "char_end", "byte_start", "byte_end", "line_start", "line_end"))
                        and row["instruction_trust"] == "untrusted_data"
                        and row["retrieval_query_matches"][expected_id]["qualified"] is True
                        and row["retrieval_query_matches"]["query-original"]["qualified"] is False,
                        "critical_project_read_current_window", {"path": row["path"]})

        require(payload.get("status") == "ok" and payload.get("kind") == "docs_context"
                and payload.get("context_available") is True and payload.get("sources")
                and set(payload.get("covered_query_ids", ())) == {"query-lookup-1", "query-lookup-2"},
                "critical_project_read_public_context",
                {"status": payload.get("status"), "covered": payload.get("covered_query_ids"),
                 "count": len(payload.get("sources") or ())})
        no_authority(payload)
        require(not validate_model_visible_projection(payload, snapshot=snapshots[0]),
                "critical_project_read_public_snapshot")
        for visible in payload["sources"]:
            path = visible["path_or_url"]
            require(path in documents, "critical_project_read_public_finite_source")
            child, body = by_path[path], documents[path]
            bound = snapshots[0][visible["evidence_id"]]
            source = bound["source"]
            require(bound["projected_source"] == visible and visible["snippet"] == body
                    and source["display_text"] == child["display_text"] == body
                    and source["project_identity"] == identity and source["source_class"] == "project_doc"
                    and source["generation_id"] == generation
                    and source["source_content_hash"] == child["committed_source_content_hash"] == digest(body)
                    and all(source.get(field) == child[field] for field in (
                        "stable_chunk_id", "parent_logical_id", "source_identity", "display_content_hash",
                        "char_start", "char_end", "byte_start", "byte_end", "line_start", "line_end"))
                    and body[source["char_start"]:source["char_end"]] == visible["snippet"]
                    and body.encode("utf-8")[source["byte_start"]:source["byte_end"]] == visible["snippet"].encode("utf-8"),
                    "critical_project_read_public_bound_bytes", {"path": path})
        # Each finite document has a different authored revision fact. The same
        # lookup is not a reason to drop any of these qualified current units.
        expected_units = {
            (path, child["stable_chunk_id"], child["parent_logical_id"], child["source_identity"],
             generation, identity, "project_doc", "project",
             child["char_start"], child["char_end"], child["byte_start"], child["byte_end"],
             child["line_start"], child["line_end"], digest(documents[path]))
            for path, child in by_path.items()
        }

        def require_complete_units(projected, bound_sources, *, label, guard):
            visible = projected.get("sources") or []
            actual_units = []
            for row in visible:
                bound = bound_sources.get(row.get("evidence_id"), {})
                original = bound.get("source", {})
                actual_units.append((
                    row.get("path_or_url"), original.get("stable_chunk_id"),
                    original.get("parent_logical_id"), original.get("source_identity"),
                    original.get("generation_id"), original.get("project_identity"),
                    original.get("source_class"), original.get("doc_scope"),
                    original.get("char_start"), original.get("char_end"),
                    original.get("byte_start"), original.get("byte_end"),
                    row.get("line_start"), row.get("line_end"),
                    digest(row.get("snippet") or ""),
                ))
            require(len(actual_units) == len(expected_units) and set(actual_units) == expected_units,
                    guard, {"label": label, "expected_count": len(expected_units),
                            "actual_count": len(actual_units),
                            "paths": [row.get("path_or_url") for row in visible]})
            require(set(projected.get("covered_query_ids") or ()) == {"query-lookup-1", "query-lookup-2"},
                    "critical_project_read_public_context", {"label": label})
            no_authority(projected)

        require_complete_units(payload, snapshots[0], label="native",
                               guard="critical_project_read_distinct_lookup_units")

        def deny_acquisition(*_args, **_kwargs):
            raise AssertionError("critical_project_read_replay_cannot_search")

        # Reorder or repeat the actual prepared operands; never retrieve again.
        # Public provenance/bytes stay bound to the original 24 committed rows.
        projection_replays = []
        saved_input = deepcopy(projector_inputs[0])
        pack = saved_input["context_pack"]
        require(len(pack) == 24, "critical_project_read_projection_input_units")
        for label, replay_pack in (
            ("repeated_current_units", [deepcopy(row) for row in pack for _ in range(2)]),
            ("reversed_current_units", list(reversed(deepcopy(pack)))),
        ):
            replay = deepcopy(saved_input)
            replay["context_pack"] = replay_pack
            with (patch.object(actual, "get_project_docs", deny_acquisition),
                  patch.object(actual, "get_project_context", deny_acquisition),
                  patch.object(app, "get_docs_context", deny_acquisition),
                  patch.object(RetrievalDispatcher, "run", deny_acquisition)):
                projected, bound_sources = projector(retrieval=replay)
            require(not validate_model_visible_projection(projected, snapshot=bound_sources),
                    "critical_project_read_public_snapshot", {"label": label})
            require_complete_units(projected, bound_sources, label=label,
                                   guard="critical_project_read_projection_unit_identity")
            projection_replays.append({"label": label, "input_windows": len(replay_pack),
                                       "public_sources": len(projected["sources"])})
        require(projector_inputs[0] == saved_input and state() == before,
                "critical_project_read_projection_replay_state")

        def replay_member(label, operand, *, overrides=None, dependency=None):
            incoming = deepcopy(operand)
            preserved = asdict(incoming)
            calls = []
            def observed_member(*args, **kwargs):
                calls.append((args, kwargs))
                return incoming
            def observed_dependency(*args, **kwargs):
                if dependency is None:
                    raise AssertionError("critical_project_read_replay_cannot_fetch")
                return deepcopy(dependency)
            args, kwargs = deepcopy(project_calls[0])
            kwargs.update(overrides or {})
            with (patch.object(actual, "get_project_docs", observed_member),
                  patch.object(actual, "get_docs", observed_dependency),
                  patch.object(RetrievalDispatcher, "run", deny_acquisition)):
                result = get_project(*args, **kwargs)
            require(len(calls) == 1 and asdict(incoming) == preserved and state() == before,
                    "critical_project_read_operand_replay", {"label": label})
            require(result.delivery_decision is not None and result.delivery_decision.deliverable is False
                    and result.answer_available is False,
                    "critical_project_read_operational_veto",
                    {"label": label, "status": result.status, "count": len(result.context_pack),
                     "delivery": asdict(result.delivery_decision) if result.delivery_decision else None})
            labels.append(label)
            return result

        for label, changes in (
            ("project_consent", {"requires_confirmation": True, "confirmation_reason": "fixture_read_consent"}),
            ("project_stale", {"status": "stale"}),
            ("project_catalog_invalid", {"status": "invalid_project_docs_catalog"}),
            ("project_acquisition_error", {"status": "error", "reason_code": "fixture_acquisition_error"}),
        ):
            replay_member(label, replace(member, **changes))
        for label, changes in (
            ("stale_windows", {"stale": True}),
            ("foreign_paths", {"path": "outside/not-a-member.md"}),
            ("changed_body_hash", {"content_hash": "0" * 64}),
        ):
            replay_member(label, replace(member, results=[replace(row, **changes) for row in member.results]))
        replay_member("changed_catalog_hash", replace(member, results=[
            replace(row, metadata={**row.metadata, "project_doc_catalog_entry_hash": "0" * 64})
            for row in member.results
        ]))
        dependency = DocsResult(
            library_id="fixture:external-budget", library="external-budget", version=None, topic=question,
            refreshed=False, stale_before_refresh=False, warning=None, last_refreshed_at=None,
            results=[DocsChunk(title=f"External {index}", content=f"ExternalBudgetRecord retains revision {index}.",
                               source=f"fixture://external/{index}", url=None) for index in range(21)],
        )
        extra = {"mode": "auto", "library": "external-budget", "allow_network": True}
        blocked = replay_member("dependency_stage_overflow", member, overrides=extra, dependency=dependency)
        dependency_stage = blocked.diagnostics["retrieval_routing"]["stages"]["dependency_docs"]
        require(dependency_stage["budget_exceeded"] is True
                and dependency_stage["observed_item_count"] == 21 and dependency_stage["item_count"] == 20,
                "critical_project_read_other_stage_budget", dependency_stage)
        replay_member("dependency_consent_with_success", member, overrides=extra,
                      dependency=replace(dependency, results=dependency.results[:1], requires_confirmation=True))
        replay_member("dependency_stale_with_success", member, overrides=extra,
                      dependency=replace(dependency, results=dependency.results[:1], stale_before_refresh=True))

        # An explicit producer veto is separate from post-acquisition packing.
        blocked_context = replace(context, delivery_decision=DeliveryDecision(False, "fixture_explicit_veto"))
        with (patch.object(actual, "get_project_context", lambda *_args, **_kwargs: deepcopy(blocked_context)),
              patch.object(RetrievalDispatcher, "run", deny_acquisition)):
            blocked_payload = call_docs_tool_payload("get_docs_context", request, actual)
        require(not blocked_payload.get("sources") and blocked_payload.get("context_available") is False
                and blocked_payload.get("delivery_decision", {}).get("deliverable") is False,
                "critical_project_read_explicit_delivery_veto")
        labels.append("explicit_project_delivery_veto")

        attempted = []
        def stop_before_acquisition(*_args, **_kwargs):
            attempted.append(True)
            raise AssertionError("invalid request reached acquisition")
        label = "too_many_host_lookups"
        changes = {"lookup_queries": [f"Probe{index}" for index in range(6)]}
        with patch.object(app, "get_docs_context", stop_before_acquisition):
            failure = call_docs_tool_payload("get_docs_context", {**request, **changes}, actual)
        require(not attempted and not failure.get("sources") and failure.get("status") != "ok",
                "critical_project_read_request_work_bound", {"label": label})
        labels.append(label)

        # The public schema has no 4000-character question ceiling. The legacy
        # compiler's internal work bound must not truncate the host's original.
        long_original = "x" * 4001
        forwarded = []
        def capture_original(source_question, **_kwargs):
            forwarded.append(source_question)
            raise TimeoutError("fixture original identity capture")
        with (patch.object(app, "get_docs_context", capture_original),
              patch.object(RetrievalDispatcher, "run", deny_acquisition)):
            failure = call_docs_tool_payload("get_docs_context",
                {**request, "question": long_original}, actual)
        require(forwarded == [long_original] and not failure.get("sources")
                and failure.get("status") == "failed",
                "critical_project_read_original_input_fidelity")
        labels.append("long_original_identity")

        interrupted = []
        def interrupted_dispatch(*_args, **_kwargs):
            interrupted.append(True)
            raise TimeoutError("fixture acquisition interrupted")
        with patch.object(RetrievalDispatcher, "run", interrupted_dispatch):
            failure = call_docs_tool_payload("get_docs_context", request, actual)
        error = failure.get("error")
        require(len(interrupted) == 1 and not failure.get("sources") and failure.get("status") == "failed"
                and isinstance(error, dict) and error.get("reason_code") == "network_required"
                and error.get("exception_type") == "TimeoutError"
                and error.get("where") == {"tool": "get_docs_context", "handler": None, "phase": "execution"},
                "critical_project_read_interrupted_acquisition")
        labels.append("acquisition_timeout_no_retry")

        # Ordinary reads do not advertise a retention completion for a fake.
        with (patch.object(actual, "get_project_context", lambda *_args, **_kwargs: deepcopy(context)),
              patch.object(RetrievalDispatcher, "run", deny_acquisition)):
            failure = call_docs_tool_payload("get_docs_context", {**request, "context_format": "patch_context"}, actual)
        require(not failure.get("sources") and "unsupported_found_window_retention" in json.dumps(failure),
                "critical_project_read_existing_retention_completion")
        labels.append("missing_patch_retention_completion")
        require(state() == before, "critical_project_read_state")
        print("PROJECT_READ_PRESENTATION_RECEIPT " + json.dumps({
            "native_public_reads": 1, "native_dispatch_calls": len(dispatch_calls),
            "prepared_children": len(children), "acquired_qualified": len(member.results),
            "bounded_control_items": len(context.project_docs.results),
            "project_windows": len(context.context_pack), "unified_windows": len(unified.context_pack),
            "public_source_count": len(payload["sources"]), "operand_replays": labels,
            "projection_replays": projection_replays,
            "distinct_full_source_units": len(expected_units),
            "generation": generation, "catalog_sha256": prepared["catalog_sha256"],
            "state_equal": True, "public_full_bodies_checked": len(payload["sources"]),
        }, ensure_ascii=False, sort_keys=True))

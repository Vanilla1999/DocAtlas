"""Native metamorphic checks for one current raw literal source window.

The four original closed-context bodies remain unchanged in the owning gate.
These two additional reads vary only outer whitespace; the same literal fact,
public question and immutable member path remain the independent oracle.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
from typing import Any

from docmancer.docs.application._docs_context_projection_core import project_docs_context
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.query_reference_binding import CatalogSource, ScopeKey, resolve_references


def run_literal_window_controls(require, indexed_body, read, bodies, source_path: str) -> dict[str, Any]:
    records = []
    lf_capture = None
    for label, literal, leading, trailing in (
        ("lf_tail", "OrdersDraftStore", "", "\n"),
        ("leading_crlf", "RelayBufferCell", " \t", "\r\n"),
    ):
        fact = bodies[literal]
        body = leading + fact + trailing
        question = f"What does {literal} do?"
        indexed_body(body)
        capture = read(question)
        payload = capture["public_payload"]
        sources = payload.get("sources") or []
        require(payload.get("kind") == "docs_context" and payload.get("status") == "ok"
                and payload.get("context_available") is True and len(sources) == 1
                and sources[0].get("path_or_url") == source_path
                and sources[0].get("snippet") == body,
                "recovery_literal_raw_window_fact", {"layout": label, "capture": capture})
        require(all(payload.get(key) is False for key in (
                    "answer_supported", "answer_available", "edit_ready"))
                and payload.get("covered_query_ids") == []
                and payload.get("missing_query_ids") == ["query-original"]
                and payload.get("query_coverage") == "partial",
                "recovery_literal_raw_window_no_credit", payload)
        require(len(capture["projection_attempts"]) == 1,
                "recovery_literal_raw_window_single_call", capture)
        attempt = capture["projection_attempts"][0]
        require(not validate_model_visible_projection(
                    attempt["projected_payload"], snapshot=attempt["snapshot"]),
                "recovery_literal_raw_window_snapshot", attempt)
        source = sources[0]
        bound = attempt["snapshot"][source["evidence_id"]]
        original = bound["source"]
        evidence = original["_reference_evidence"]
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        owner = "local:" + hashlib.sha256(capture["request"]["project_path"].encode("utf-8")).hexdigest()
        expected_window = {
            "char_start": 0, "char_end": len(body),
            "byte_start": 0, "byte_end": len(body.encode("utf-8")),
            "line_start": 1, "line_end": body[:-1].count("\n") + 1,
        }
        require(evidence["raw_document"] == body and evidence["text"] == body
                and evidence["source"]["content_sha256"] == digest
                and str(original["_source_snapshot_sha256"]).removeprefix("sha256:") == digest
                and original["project_identity"] == owner
                and evidence["source"]["scope"]["project_id"] == owner
                and evidence["source"]["canonical_path"] == source_path
                and original["doc_scope"] == evidence["member_binding"]["doc_scope"] == "project"
                and original["_source_catalog_hash"] == evidence["member_binding"]["catalog_entry_hash"]
                and all(original.get(key) == value for key, value in expected_window.items())
                and evidence["char_start"] == 0 and evidence["char_end"] == len(body),
                "recovery_literal_raw_window_source_binding", {
                    "layout": label, "expected_window": expected_window, "original": original})
        require(source["line_start"] == expected_window["line_start"]
                and source["line_end"] == expected_window["line_end"]
                and {key: value for key, value in source.items() if key != "source_uri"}
                    == {key: value for key, value in bound["projected_source"].items() if key != "source_uri"}
                and ("source_uri" not in source
                     or source["source_uri"] == bound["projected_source"].get("source_uri")),
                "recovery_literal_raw_window_delivery_binding", bound)
        trace = original["retrieval_query_matches"]["query-original"]
        require(trace.get("query_text") == question and trace.get("qualified") is False
                and trace.get("qualification_reason") == "insufficient_visible_match"
                and trace.get("reference_visible_span") == [len(leading), len(leading) + len(fact)],
                "recovery_literal_raw_window_canonical_span", trace)
        admissions = (attempt["after_projection"].get("retrieval_diagnostics") or {}).get(
            "docs_context_projection", {}).get("literal_context_admissions") or []
        require(admissions and all(admission.get("body_window") == expected_window for admission in admissions),
                "recovery_literal_raw_window_coordinates", {
                    "layout": label, "expected_window": expected_window, "admissions": admissions})
        expected_witness = {
            "text": literal, "char_start": body.index(literal),
            "char_end": body.index(literal) + len(literal),
        }
        witnesses = [witness for admission in admissions
                     for witness in admission.get("body_witnesses", [])]
        require(len(witnesses) == 1 and all(
                    witnesses[0].get(key) == value for key, value in expected_witness.items())
                and body[witnesses[0]["char_start"]:witnesses[0]["char_end"]] == literal
                and all(admission.get("coverage_credit") is False for admission in admissions),
                "recovery_literal_raw_window_witness", {"layout": label, "admissions": admissions})
        refs = [row for row in original["_reference_root_plan"]["references"]
                if row["mention"]["text"] == literal]
        require(len(refs) == 1 and refs[0]["role"] == "unresolved" and refs[0]["state"] == "unresolved"
                and refs[0]["mention"]["explicit"] is False,
                "recovery_literal_raw_window_no_role", refs)
        records.append({
            "layout": label, "question_sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
            "fact_sha256": hashlib.sha256(fact.encode("utf-8")).hexdigest(),
            "source_sha256": digest, "source_path": source_path,
            "source_window": expected_window, "literal_witness": expected_witness,
        })
        if label == "lf_tail":
            lf_capture = capture

    # Use the successful native operand. Only the candidate's outer LF is
    # removed from its claimed span; full content and current source/hash stay.
    require(lf_capture is not None, "recovery_literal_raw_window_native_operand")
    altered = deepcopy(lf_capture["projection_attempts"][0]["before_projection"])
    require(bool(altered.get("context_pack")), "recovery_literal_raw_window_native_operand")
    for candidate in altered["context_pack"]:
        candidate["char_end"] -= 1
    result, snapshot = project_docs_context(retrieval=altered)
    require(not result.get("context_available") and not result.get("sources") and not snapshot,
            "recovery_literal_raw_window_span_replay", {"payload": result, "snapshot": snapshot})
    require(not validate_model_visible_projection(result, snapshot=snapshot),
            "recovery_literal_raw_window_negative_valid", result)

    # A separately authored quoted query reuses the same acquired source. Build
    # its reference DTO with the real current resolver; this is projection-only
    # counterfactual input, not a claim of another native acquisition.
    quoted_question = "What does `OrdersDraftStore` do?"
    quoted = deepcopy(lf_capture["projection_attempts"][0]["before_projection"])
    quoted["question"] = quoted_question
    quoted["documentation_query_plan"] = build_documentation_query_plan(quoted_question).as_payload()
    for candidate in quoted["context_pack"]:
        identity = candidate["_reference_evidence"]["source"]
        scope = ScopeKey(**identity["scope"])
        current = CatalogSource(identity["document_id"], scope,
                                identity["canonical_path"], identity["content_sha256"])
        plan = asdict(resolve_references(quoted_question, catalog=(current,), scope=scope,
                                        catalog_complete=True))
        candidate["_reference_root_plan"] = plan
        candidate["_reference_plans"] = {quoted_question: deepcopy(plan)}
    healthy, healthy_snapshot = project_docs_context(retrieval=deepcopy(quoted))
    require(healthy.get("context_available") is True and len(healthy.get("sources") or []) == 1
            and healthy["sources"][0].get("snippet") == bodies["OrdersDraftStore"] + "\n"
            and healthy.get("covered_query_ids") == []
            and healthy.get("missing_query_ids") == ["query-original"]
            and all(healthy.get(key) is False for key in ("answer_supported", "answer_available", "edit_ready"))
            and not validate_model_visible_projection(healthy, snapshot=healthy_snapshot),
            "recovery_literal_explicit_raw_window_positive", healthy)
    live = healthy_snapshot[healthy["sources"][0]["evidence_id"]]["source"]
    trace = live["retrieval_query_matches"]["query-original"]
    require(trace.get("qualified") is False
            and trace.get("qualification_reason") == "insufficient_visible_match"
            and any(binding.get("role") == "symbol_identity" and binding.get("field") == "body"
                    and binding.get("char_start") == 0 and binding.get("char_end") == len("OrdersDraftStore")
                    for binding in trace.get("reference_bindings") or []),
            "recovery_literal_explicit_raw_window_reference", trace)
    for candidate in quoted["context_pack"]:
        candidate["char_end"] -= 1
    rejected, rejected_snapshot = project_docs_context(retrieval=quoted)
    require(not rejected.get("context_available") and not rejected.get("sources") and not rejected_snapshot,
            "recovery_literal_explicit_raw_window_span_replay", rejected)
    require(not validate_model_visible_projection(rejected, snapshot=rejected_snapshot),
            "recovery_literal_raw_window_negative_valid", rejected)
    pair_context = _run_literal_pair_controls(require)
    return {"native_reads": 2, "member_preparations": 2, "projection_replays": 3, "records": records,
            "explicit_replay_question_sha256": hashlib.sha256(quoted_question.encode("utf-8")).hexdigest(),
            "pair_context": pair_context}

def _run_literal_pair_controls(require) -> dict[str, Any]:
    """One frozen native read, then explicitly counted detached counterexamples."""
    from pathlib import Path
    import tempfile
    from unittest.mock import patch

    from docmancer.docs.application import _docs_context_projection_core as core_module
    from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project
    from eval.project_context_quality.capture_public_context import capture_public_call

    question = "How does OrdersDraftStore differ from PaymentOutbox?"
    fact = ("OrdersDraftStore writes order drafts before upload, whereas PaymentOutbox "
            "writes pending payment events until confirmation.")
    source_path = "ARCHITECTURE.md"
    body = (Path(__file__).parent / "projects" / "explicit_manifest_monorepo" / source_path).read_bytes().decode("utf-8")
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    require(body_hash == "ccad600f6c90895fa820d0516c37382a7ed7b2cbed5f99137bdefa2e40d05ba7"
            and len(body.encode("utf-8")) == 485 and body[361:484] == fact and body.endswith("\n"),
            "recovery_pair_frozen_source")
    names = ("OrdersDraftStore", "PaymentOutbox")
    records, replays = [], []
    with tempfile.TemporaryDirectory(prefix="docatlas-pair-context-") as temporary:
        root = Path(temporary)
        project = root / "project"
        write_project(project, {source_path: body})
        with isolated_service(root / "state") as (service, config):
            prepared = index_project(service, config, project)
            require(prepared["indexed_paths"] == [source_path]
                    and not prepared["excluded_or_failed_paths"] and not prepared["unexpected_paths"],
                    "recovery_pair_exact_fixture_member", prepared)
            policy = service.member_storage_policy
            owner = "local:" + hashlib.sha256(str(project).encode("utf-8")).hexdigest()

            def state():
                return (
                    policy.generation(), hashlib.sha256(policy.db_path.read_bytes()).hexdigest(),
                    hashlib.sha256((project / source_path).read_bytes()).hexdigest(),
                    hashlib.sha256((project / "docatlas.project-docs.yaml").read_bytes()).hexdigest(),
                )

            core_calls = []
            real_core = core_module.project_docs_context

            def observe_core(*args, **kwargs):
                retrieval = kwargs["retrieval"]
                before_core = deepcopy(retrieval)
                result = real_core(*args, **kwargs)
                payload, snapshot = result
                core_calls.append(deepcopy({
                    "before_projection": before_core, "after_projection": retrieval,
                    "projected_payload": payload, "snapshot": snapshot,
                }))
                return result

            before = state()
            with patch.object(core_module, "project_docs_context", observe_core):
                capture = capture_public_call(service, {
                    "question": question, "project_path": str(project), "scope": "all",
                })
            require(state() == before, "recovery_pair_read_only", capture)
            require(len(capture["projection_attempts"]) == 1 and len(core_calls) == 1,
                    "recovery_pair_single_public_projection", capture)
            attempt = capture["projection_attempts"][0]
            core_call = core_calls[0]
            queries = core_call["before_projection"]["documentation_query_plan"]["queries"]
            require([(row.get("query_id"), row.get("text"), row.get("origin"), row.get("relation"),
                      row.get("public_parent_query_id")) for row in queries]
                    == [("query-original", question, "original", "direct", None)],
                    "recovery_pair_original_only_request", queries)

            def check_context(payload, snapshot, projected, *, core_payload=None, core_snapshot=None, core_projected=None):
                sources = payload.get("sources") or []
                require(payload.get("kind") == "docs_context" and payload.get("status") == "ok"
                        and payload.get("context_available") is True
                        and sources and all(row.get("path_or_url") == source_path for row in sources)
                        and any(fact in row.get("snippet", "") for row in sources),
                        "recovery_pair_frozen_fact", {"capture": capture, "payload": payload})
                require(all(payload.get(key) is False for key in (
                            "answer_supported", "answer_available", "edit_ready"))
                        and payload.get("covered_query_ids") == []
                        and payload.get("missing_query_ids") == ["query-original"]
                        and payload.get("query_coverage") == "partial"
                        and not validate_model_visible_projection(payload, snapshot=snapshot),
                        "recovery_pair_no_authority_or_credit", payload)
                core_payload = payload if core_payload is None else core_payload
                core_snapshot = snapshot if core_snapshot is None else core_snapshot
                core_projected = projected if core_projected is None else core_projected
                require(not validate_model_visible_projection(core_payload, snapshot=core_snapshot),
                        "recovery_pair_core_snapshot", core_payload)
                admissions = (core_projected.get("retrieval_diagnostics") or {}).get(
                    "docs_context_projection", {}).get("literal_context_admissions") or []
                require(admissions and all(
                            row.get("reason") == "literal_symbol_body_context"
                            and row.get("coverage_credit") is False
                            and row.get("qualification_reason") == "insufficient_visible_match"
                            and len(row.get("body_witnesses") or []) == 2 for row in admissions),
                        "recovery_pair_body_admission", admissions)
                final_rows = []
                for source in sources:
                    bound = snapshot[source["evidence_id"]]
                    current = bound["source"]
                    evidence = current["_reference_evidence"]
                    identity, scope = evidence["source"], evidence["source"]["scope"]
                    start, end = current.get("char_start"), current.get("char_end")
                    require(type(start) is int and type(end) is int and 0 <= start < end <= len(body)
                            and source["snippet"] == body[start:end]
                            and evidence["raw_document"] == body
                            and identity["canonical_path"] == source_path
                            and identity["content_sha256"] == body_hash
                            and str(current["_source_snapshot_sha256"]).removeprefix("sha256:") == body_hash
                            and current["project_identity"] == scope["project_id"] == owner
                            and current["generation_id"] == scope["snapshot_id"] == prepared["generation_id"]
                            and current["doc_scope"] == evidence["member_binding"]["doc_scope"] == "project"
                            and current["_source_catalog_hash"] == evidence["member_binding"]["catalog_entry_hash"],
                            "recovery_pair_current_raw_source", bound)
                    expected = {
                        "char_start": start, "char_end": end,
                        "byte_start": len(body[:start].encode("utf-8")),
                        "byte_end": len(body[:end].encode("utf-8")),
                        "line_start": body[:start].count("\n") + 1,
                        "line_end": body[:end - 1].count("\n") + 1,
                    }
                    require(all(current.get(key) == value for key, value in expected.items())
                            and source["line_start"] == expected["line_start"]
                            and source["line_end"] == expected["line_end"]
                            and {key: value for key, value in source.items() if key != "source_uri"}
                                == {key: value for key, value in bound["projected_source"].items()
                                    if key != "source_uri"}
                            and ("source_uri" not in source
                                 or source["source_uri"] == bound["projected_source"].get("source_uri")),
                            "recovery_pair_raw_window_delivery", bound)
                    trace = current["retrieval_query_matches"]["query-original"]
                    plan = current["_reference_root_plan"]
                    refs = plan["references"]
                    require(plan["question"] == question and plan["catalog_complete"] is True
                            and [(row["mention"]["text"], row["role"], row["state"],
                                  row["mention"]["explicit"], row["source_ids"]) for row in refs]
                                == [(name, "unresolved", "unresolved", False, []) for name in names]
                            and all(row["mention"]["start"] == question.index(row["mention"]["text"])
                                    and row["mention"]["end"] == question.index(row["mention"]["text"])
                                        + len(row["mention"]["text"]) for row in refs)
                            and trace.get("query_text") == question and trace.get("qualified") is False
                            and trace.get("qualification_reason") == "insufficient_visible_match",
                            "recovery_pair_original_unresolved", trace)
                    final_rows.append((source, current, identity, start, end))
                retained = {}
                for seed in core_payload.get("sources") or []:
                    original = core_snapshot[seed["evidence_id"]]["source"]
                    evidence = original["_reference_evidence"]
                    start, end = original.get("char_start"), original.get("char_end")
                    require(type(start) is int and type(end) is int and 0 <= start < end <= len(body)
                            and seed["snippet"] == body[start:end] and evidence["raw_document"] == body
                            and evidence["source"]["content_sha256"] == body_hash
                            and original["project_identity"] == evidence["source"]["scope"]["project_id"] == owner,
                            "recovery_pair_core_raw_binding", original)
                    expected = {
                        "char_start": start, "char_end": end,
                        "byte_start": len(body[:start].encode("utf-8")), "byte_end": len(body[:end].encode("utf-8")),
                        "line_start": body[:start].count("\n") + 1, "line_end": body[:end - 1].count("\n") + 1,
                    }
                    require(all(original.get(key) == value for key, value in expected.items()),
                            "recovery_pair_core_raw_binding", original)
                    matched = [row for row in admissions if row.get("source_id") == evidence["source"]["document_id"]
                               and row.get("body_window") == expected]
                    require(matched and all(
                        [(witness["text"], witness["char_start"], witness["char_end"],
                          witness["query_char_start"], witness["query_char_end"]) for witness in row["body_witnesses"]]
                            == [(name, body.index(name), body.index(name) + len(name),
                                 question.index(name), question.index(name) + len(name)) for name in names]
                        and all(witness.get("kind") == "literal_pair_context"
                                and witness["paragraph_char_start"] == 361
                                and witness["paragraph_char_end"] == end
                                for witness in row["body_witnesses"]) for row in matched),
                        "recovery_pair_two_current_body_witnesses", admissions)
                    # Final structural context may be a canonical superset. Bind
                    # independently to its actual source, policy fields and raw
                    # interval; never require the two carriers to have equal spans.
                    containing = [row for row, current, identity, a, b in final_rows
                        if identity == evidence["source"] and a <= start < end <= b
                        and all(current.get(key) == original.get(key) for key in (
                            "project_identity", "_source_snapshot_sha256", "_source_catalog_hash",
                            "resolved_version", "generation_id", "doc_scope", "module_path"))
                        and all(row.get(key) == seed.get(key) for key in (
                            "project_identity", "path_or_url", "version_binding", "authority", "scope"))]
                    require(containing, "recovery_pair_final_retains_core_lineage", {
                        "seed_id": seed["evidence_id"], "core_span": [start, end]})
                    retained[seed["evidence_id"]] = containing[0]["evidence_id"]
                require(retained, "recovery_pair_final_retains_core_lineage", admissions)
                return [{"path": row["path_or_url"], "snippet_sha256": hashlib.sha256(
                    row["snippet"].encode("utf-8")).hexdigest(), "evidence_id": row["evidence_id"]} for row in sources]

            records.extend(check_context(capture["public_payload"], attempt["snapshot"], attempt["after_projection"],
                core_payload=core_call["projected_payload"], core_snapshot=core_call["snapshot"],
                core_projected=core_call["after_projection"]))
            operand = deepcopy(core_call["before_projection"])
            healthy_input = deepcopy(operand)
            healthy, healthy_snapshot = project_docs_context(retrieval=healthy_input)
            check_context(healthy, healthy_snapshot, healthy_input)
            replays.append("healthy_current_operand")
            direct_probes = _pair_predicate_controls(require, question)

            def reject(value, label, guard):
                payload, snapshot = project_docs_context(retrieval=value)
                require(not payload.get("context_available") and not payload.get("sources") and not snapshot,
                        guard, {"label": label, "payload": payload})
                require(not validate_model_visible_projection(payload, snapshot=snapshot),
                        "recovery_pair_negative_projection_valid", payload)
                replays.append(label)

            def with_query(text):
                value = deepcopy(operand)
                value["question"] = text
                value["documentation_query_plan"] = build_documentation_query_plan(text).as_payload()
                for candidate in value["context_pack"]:
                    identity = candidate["_reference_evidence"]["source"]
                    scope = ScopeKey(**identity["scope"])
                    source = CatalogSource(identity["document_id"], scope,
                                           identity["canonical_path"], identity["content_sha256"])
                    plan = asdict(resolve_references(text, catalog=(source,), scope=scope, catalog_complete=True))
                    candidate["_reference_root_plan"] = plan
                    candidate["_reference_plans"] = {text: deepcopy(plan)}
                return value

            reject(with_query("How does OrdersDraftStore differ from PaymentOutbox under lunar phase?"),
                   "unknown_suffix", "recovery_pair_frame_requires_full_query")
            for text, label in (
                ("How does ordersDraftStore differ from PaymentOutbox?", "case_changed"),
                ("How does OrdersDraftStoreExtra differ from PaymentOutbox?", "prefix_only"),
                ("How does OrdersDraftStore differ from OrdersDraftStore?", "same_name"),
            ):
                reject(with_query(text), label, "recovery_pair_exact_query_identity")
            changed = deepcopy(operand)
            changed["question"] = "How does PaymentOutbox differ from OrdersDraftStore?"
            changed["documentation_query_plan"] = build_documentation_query_plan(changed["question"]).as_payload()
            reject(changed, "replayed_original_plan", "recovery_pair_query_plan_binding")
            for label in ("foreign_owner", "wrong_snapshot_hash", "clipped_raw_span", "foreign_member_scope"):
                changed = deepcopy(operand)
                for candidate in changed["context_pack"]:
                    if label == "foreign_owner":
                        candidate["project_identity"] = "local:" + "0" * 64
                    elif label == "wrong_snapshot_hash":
                        candidate["_source_snapshot_sha256"] = "sha256:" + "0" * 64
                    elif label == "clipped_raw_span":
                        candidate["char_end"] -= 1
                    else:
                        candidate["doc_scope"] = "module"
                reject(changed, label, "recovery_pair_current_source_binding")
    return {
        "native_reads": 1, "member_preparations": 1, "observed_core_calls": len(core_calls),
        "projection_replays": len(replays),
        "projection_replay_labels": replays, **direct_probes,
        "question_sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
        "source_sha256": body_hash, "source_bytes": 485,
        "fact_sha256": hashlib.sha256(fact.encode("utf-8")).hexdigest(),
        "source_path": source_path, "scope": "all", "sources": records,
    }


def _pair_predicate_controls(require, question: str) -> dict[str, Any]:
    """Small direct grammar/body probes; no native-source or retrieval credit."""
    from docmancer.docs.domain.literal_context_admission import (
        _closed_pair_context, _pair_context_witnesses,
    )

    names = ("OrdersDraftStore", "PaymentOutbox")
    mentions = _closed_pair_context(question)
    require(tuple(mention.text for mention in mentions) == names,
            "recovery_pair_original_frame", mentions)
    body_negatives = (
        ("single_body_name", "OrdersDraftStore retains drafts.",
         "recovery_pair_requires_both_body_literals"),
        ("separate_paragraphs", "OrdersDraftStore retains drafts.\n\nPaymentOutbox retains events.",
         "recovery_pair_keeps_paragraph_boundary"),
        ("heading", "# OrdersDraftStore PaymentOutbox\nUnrelated substantive prose.",
         "recovery_pair_plain_body_only"),
        ("link", "[OrdersDraftStore PaymentOutbox](guide.md)\nUnrelated substantive prose.",
         "recovery_pair_plain_body_only"),
        ("labels", "OrdersDraftStore PaymentOutbox.", "recovery_pair_plain_body_only"),
        ("body_case", "ordersdraftstore retains drafts, whereas PaymentOutbox retains events.",
         "recovery_pair_whole_body_identifiers"),
        ("qualified_segments", "OrdersDraftStore.member retains drafts, whereas PaymentOutbox.member retains events.",
         "recovery_pair_whole_body_identifiers"),
        ("path_prefix", "lib/OrdersDraftStore retains records, whereas PaymentOutbox keeps events.",
         "recovery_pair_whole_body_identifiers"),
        ("path_suffix", "OrdersDraftStore retains records, whereas PaymentOutbox\\events stay queued.",
         "recovery_pair_whole_body_identifiers"),
        ("fenced_code", "\x60\x60\x60text\nOrdersDraftStore retains drafts, whereas PaymentOutbox retains events.\n\x60\x60\x60",
         "recovery_pair_plain_body_only"),
        ("blockquote", "> OrdersDraftStore retains drafts, whereas PaymentOutbox retains events.",
         "recovery_pair_plain_body_only"),
        ("indented_code", "    OrdersDraftStore retains drafts, whereas PaymentOutbox retains events.",
         "recovery_pair_plain_body_only"),
    )
    for label, text, guard in body_negatives:
        require(not _pair_context_witnesses(text, 0, mentions), guard, {"label": label})
    repeated = "OrdersDraftStore retains drafts. OrdersDraftStore and PaymentOutbox preserve pending records."
    witness = _pair_context_witnesses(repeated, 0, mentions)
    require([(row["text"], row["char_start"], row["char_end"]) for row in witness]
            == [(name, repeated.index(name), repeated.index(name) + len(name)) for name in names],
            "recovery_pair_repeated_names_stay_context", witness)
    neutral_question = "How does CopperLedger differ from QuartzMailbox?"
    neutral_mentions = _closed_pair_context(neutral_question)
    neutral_body = "CopperLedger retains records, whereas QuartzMailbox retains envelopes."
    witness = _pair_context_witnesses(neutral_body, 0, neutral_mentions)
    require([(row["text"], row["char_start"], row["char_end"]) for row in witness]
            == [(name, neutral_body.index(name), neutral_body.index(name) + len(name))
                for name in ("CopperLedger", "QuartzMailbox")],
            "recovery_pair_generic_names", witness)
    syntax_negatives = (
        "How does \x60OrdersDraftStore\x60 differ from \x60PaymentOutbox\x60?",
        "How does OrdersDraftStore.md differ from PaymentOutbox.md?",
        "How does OrdersDraftStore differ from PaymentOutbox and RelayBufferCell?",
    )
    for text in syntax_negatives:
        require(not _closed_pair_context(text), "recovery_pair_no_role_promotion", text)
    return {
        "direct_frame_probes": 5, "direct_body_probes": 14,
        "direct_body_negative_labels": [label for label, _, _ in body_negatives],
        "direct_body_inputs_sha256": hashlib.sha256(
            "\n".join(text for _, text, _ in body_negatives).encode("utf-8")).hexdigest(),
        "neutral_question_sha256": hashlib.sha256(neutral_question.encode("utf-8")).hexdigest(),
        "neutral_body_sha256": hashlib.sha256(neutral_body.encode("utf-8")).hexdigest(),
    }

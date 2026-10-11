from __future__ import annotations


def _native_source(tmp_path, text: str, question: str):
    from tests.docs._reference_binding_fixtures import capture_reference_case

    cap = capture_reference_case(tmp_path, {"Guide.md": text}, question)
    source = dict(cap["projection_attempts"][0]["before_projection"]["context_pack"][0])
    plan = cap["projection_attempts"][0]["before_projection"]["documentation_query_plan"]
    source["_independent_query_plan"] = plan
    source["_qualification_candidate"] = dict(source)
    source["_expected_project_identity"] = source["project_identity"]
    source["_lifecycle_intent"] = "current"
    source["path_or_url"] = source["path"]
    query_text = {
        str(item.get("query_id") or ""): str(item.get("text") or "")
        for item in plan.get("queries") or ()
        if isinstance(item, dict)
    }
    return source, query_text


def test_delivery_unit_inventory_requalifies_each_structural_leaf(tmp_path) -> None:
    from docmancer.docs.application._docs_context_projection_core import _requalify_visible_source
    from docmancer.docs.application.qualified_support_units import build_delivery_units

    source, query_text = _native_source(
        tmp_path,
        "# Retry\n\nA transport retry uses `--relay-retry`.\n\nWater the basil every evening.\n",
        "What command handles a transport retry?",
    )
    evidence = source["_reference_evidence"]
    units = build_delivery_units(
        source=source,
        raw_text=evidence["text"],
        raw_start=evidence["char_start"],
        query_text=query_text,
        eligible_query_ids=frozenset({"query-original"}),
        requalify=_requalify_visible_source,
    )
    bodies = {
        evidence["text"][unit.start - evidence["char_start"] : unit.end - evidence["char_start"]]
        for unit in units
    }
    assert "A transport retry uses `--relay-retry`." in bodies
    assert "Water the basil every evening." not in bodies


def test_delivery_unit_inventory_keeps_leaf_items_not_parent_union(tmp_path) -> None:
    from docmancer.docs.application._docs_context_projection_core import _requalify_visible_source
    from docmancer.docs.application.qualified_support_units import build_delivery_units

    source, query_text = _native_source(
        tmp_path,
        "# Retry\n\nRetry options:\n\n- A transport retry uses `--relay-retry`.\n- A transport retry uses `--backup-relay`.\n",
        "What command handles a transport retry?",
    )
    evidence = source["_reference_evidence"]
    units = build_delivery_units(
        source=source,
        raw_text=evidence["text"],
        raw_start=evidence["char_start"],
        query_text=query_text,
        eligible_query_ids=frozenset({"query-original"}),
        requalify=_requalify_visible_source,
    )
    bodies = [
        evidence["text"][unit.start - evidence["char_start"] : unit.end - evidence["char_start"]]
        for unit in units
    ]
    assert len(units) == 2
    assert any("--relay-retry" in body for body in bodies)
    assert any("--backup-relay" in body for body in bodies)
    assert not any("--relay-retry" in body and "--backup-relay" in body for body in bodies)


def test_native_inventory_keeps_composite_when_children_do_not_cover_all_query_directions(tmp_path) -> None:
    from tests.docs._reference_binding_fixtures import capture_reference_case
    from docmancer.docs.application._docs_context_projection_core import _requalify_visible_source
    from docmancer.docs.application.qualified_support_units import build_delivery_units

    text = (
        "# Options\n\n"
        "- Alpha transport uses red channel.\n"
        "- Beta transport uses blue relay.\n"
    )
    cap = capture_reference_case(
        tmp_path,
        {"Guide.md": text},
        "What channel does Alpha transport use?",
        lookups=("alpha beta red blue gamma delta",),
    )
    before = cap["projection_attempts"][0]["before_projection"]
    source = dict(before["context_pack"][0])
    plan = before["documentation_query_plan"]
    source.update({
        "_independent_query_plan": plan,
        "_qualification_candidate": dict(source),
        "_expected_project_identity": source["project_identity"],
        "_lifecycle_intent": "current",
        "path_or_url": source["path"],
    })
    query_text = {
        str(item.get("query_id") or ""): str(item.get("text") or "")
        for item in plan.get("queries") or ()
        if isinstance(item, dict)
    }
    evidence = source["_reference_evidence"]
    units = build_delivery_units(
        source=source,
        raw_text=evidence["text"],
        raw_start=evidence["char_start"],
        query_text=query_text,
        eligible_query_ids=frozenset({"query-original", "query-lookup-1"}),
        requalify=_requalify_visible_source,
    )
    bodies = [
        evidence["text"][unit.start - evidence["char_start"] : unit.end - evidence["char_start"]]
        for unit in units
    ]

    assert any(body == "- Alpha transport uses red channel." for body in bodies)
    assert any(
        "- Alpha transport uses red channel." in body
        and "- Beta transport uses blue relay." in body
        for body in bodies
    ), "composite-only lookup support must not be discarded as a redundant parent union"
    composite = next(
        unit for unit, body in zip(units, bodies)
        if "Alpha transport" in body and "Beta transport" in body
    )
    assert "query-lookup-1" in composite.qualified_query_ids

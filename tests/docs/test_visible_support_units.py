from __future__ import annotations

from dataclasses import replace
import hashlib

import pytest

from docmancer.docs.domain.query_reference_binding import ScopeKey
from docmancer.docs.application.qualified_support_units import (
    DeliveryUnit,
    OriginKey,
    VariantFootprint,
    make_footprint,
    visible_units,
)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def origin_for(text: str, *, start: int = 100) -> OriginKey:
    return OriginKey(
        ScopeKey("p", "", "g1"),
        "d",
        digest(text),
        start,
        start + len(text),
        "owner",
        digest("root question"),
    )


def test_same_query_ids_do_not_mean_same_visible_units() -> None:
    text = "A retry uses direct delivery.\n\nB retry uses a backup relay."
    split = text.index("\n\n")
    origin = origin_for(text)
    units = (
        DeliveryUnit(origin, 100, 100 + split, digest(text[:split]), frozenset({"q"})),
        DeliveryUnit(
            origin,
            100 + split + 2,
            100 + len(text),
            digest(text[split + 2 :]),
            frozenset({"q"}),
        ),
    )

    short = make_footprint(
        origin=origin,
        raw_text=text,
        raw_start=100,
        start=100,
        end=100 + split,
        units=units,
        query_ids=frozenset({"q"}),
    )
    full = make_footprint(
        origin=origin,
        raw_text=text,
        raw_start=100,
        start=100,
        end=100 + len(text),
        units=units,
        query_ids=frozenset({"q"}),
    )

    assert short.query_ids == full.query_ids
    assert len(short.unit_keys) == 1
    assert len(full.unit_keys) == 2
    assert short.unit_keys < full.unit_keys
    assert short.redundancy_keys < full.redundancy_keys


def test_same_body_under_different_verified_conditions_is_not_a_duplicate() -> None:
    text = "On socket timeout:\nRetry the request.\n\nOn DNS timeout:\nRetry the request."
    first_condition = (100, 118)
    first_body_start = 119
    first_body_end = first_body_start + len("Retry the request.")
    second_condition_start = text.index("On DNS timeout:") + 100
    second_condition = (second_condition_start, second_condition_start + len("On DNS timeout:"))
    second_body_start = text.rindex("Retry the request.") + 100
    second_body_end = second_body_start + len("Retry the request.")
    origin = origin_for(text)
    body_hash = digest("Retry the request.")
    units = (
        DeliveryUnit(origin, first_body_start, first_body_end, body_hash, frozenset({"q"}), (first_condition,)),
        DeliveryUnit(origin, second_body_start, second_body_end, body_hash, frozenset({"q"}), (second_condition,)),
    )

    full = make_footprint(
        origin=origin,
        raw_text=text,
        raw_start=100,
        start=100,
        end=100 + len(text),
        units=units,
        query_ids=frozenset({"q"}),
    )

    assert len(full.unit_keys) == 2
    assert len(full.redundancy_keys) == 2


def test_same_body_and_same_dependency_context_remains_duplicate() -> None:
    text = "On timeout:\nRetry the request."
    origin = origin_for(text)
    body_start = 100 + text.index("Retry")
    body_end = 100 + len(text)
    condition = (100, 100 + len("On timeout:"))
    unit = DeliveryUnit(
        origin, body_start, body_end, digest("Retry the request."), frozenset({"q"}), (condition,)
    )
    duplicate = replace(unit)

    footprint = make_footprint(
        origin=origin,
        raw_text=text,
        raw_start=100,
        start=100,
        end=100 + len(text),
        units=(unit, duplicate),
        query_ids=frozenset({"q"}),
    )

    assert len(footprint.unit_keys) == 1
    assert len(footprint.redundancy_keys) == 1


def test_visible_units_require_complete_current_bytes_and_dependencies() -> None:
    text = "π condition\nBody alpha.\n\nBody beta."
    origin = origin_for(text, start=7)
    first_start = 7 + text.index("Body alpha.")
    first_end = first_start + len("Body alpha.")
    dependency = (7, 7 + len("π condition"))
    unit = DeliveryUnit(origin, first_start, first_end, digest("Body alpha."), frozenset({"q"}), (dependency,))

    assert visible_units(
        origin=origin,
        raw_text=text,
        raw_start=7,
        start=7,
        end=first_end,
        units=(unit,),
    ) == (unit,)
    # Crop away the verified condition: the body cannot retain this unit.
    assert visible_units(
        origin=origin,
        raw_text=text,
        raw_start=7,
        start=first_start,
        end=first_end,
        units=(unit,),
    ) == ()
    # Stale hash never authorizes changed bytes.
    changed = text.replace("Body alpha.", "Body omega.")
    assert visible_units(
        origin=origin,
        raw_text=changed,
        raw_start=7,
        start=7,
        end=7 + len(changed),
        units=(unit,),
    ) == ()


def test_visible_units_reject_other_origin_and_invalid_requested_span() -> None:
    text = "Body alpha."
    origin = origin_for(text)
    unit = DeliveryUnit(origin, 100, 100 + len(text), digest(text), frozenset({"q"}))
    other = replace(origin, document_id="other")
    other_unit = replace(unit, origin=other)

    assert visible_units(
        origin=origin,
        raw_text=text,
        raw_start=100,
        start=100,
        end=100 + len(text),
        units=(other_unit,),
    ) == ()
    with pytest.raises(ValueError):
        visible_units(
            origin=origin,
            raw_text=text,
            raw_start=100,
            start=99,
            end=100 + len(text),
            units=(unit,),
        )


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


def test_crop_recomputes_footprint_and_drops_removed_unit() -> None:
    text = "Alpha retry path.\n\nBeta retry path."
    split = text.index("\n\n")
    origin = origin_for(text)
    units = (
        DeliveryUnit(origin, 100, 100 + split, digest(text[:split]), frozenset({"q"})),
        DeliveryUnit(origin, 100 + split + 2, 100 + len(text), digest(text[split + 2 :]), frozenset({"q"})),
    )
    full = make_footprint(
        origin=origin, raw_text=text, raw_start=100,
        start=100, end=100 + len(text), units=units, query_ids=frozenset({"q"}),
    )
    cropped = make_footprint(
        origin=origin, raw_text=text, raw_start=100,
        start=100, end=100 + split, units=units, query_ids=frozenset({"q"}),
    )
    assert len(full.unit_keys) == 2
    assert len(cropped.unit_keys) == 1
    assert cropped.unit_keys < full.unit_keys


def test_snapshot_change_breaks_same_origin_identity_even_for_identical_bytes() -> None:
    from docmancer.docs.application.context_variant_retention import is_same_origin_gain

    text = "Alpha retry path.\n\nBeta retry path."
    split = text.index("\n\n")
    old_origin = origin_for(text)
    new_origin = replace(old_origin, scope=ScopeKey("p", "", "g2"))
    old = VariantFootprint(
        old_origin, 100, 100 + split,
        frozenset({(100, 100 + split, digest(text[:split]))}),
        frozenset({"a"}), frozenset({"q"}),
    )
    new = VariantFootprint(
        new_origin, 100, 100 + len(text),
        old.unit_keys | {(100 + split + 2, 100 + len(text), digest(text[split + 2 :]))},
        frozenset({"a", "b"}), frozenset({"q"}),
    )
    assert not is_same_origin_gain(old, new)


def test_copied_body_at_different_offsets_is_redundant_within_one_origin() -> None:
    text = "Retry the request.\n\nRetry the request."
    origin = origin_for(text)
    body_hash = digest("Retry the request.")
    second = text.rindex("Retry the request.")
    units = (
        DeliveryUnit(origin, 100, 100 + len("Retry the request."), body_hash, frozenset({"q"})),
        DeliveryUnit(origin, 100 + second, 100 + len(text), body_hash, frozenset({"q"})),
    )
    footprint = make_footprint(
        origin=origin, raw_text=text, raw_start=100,
        start=100, end=100 + len(text), units=units, query_ids=frozenset({"q"}),
    )
    assert len(footprint.unit_keys) == 2
    assert len(footprint.redundancy_keys) == 1


def test_native_inventory_keeps_repeated_body_with_distinct_conditions_as_composites(tmp_path) -> None:
    from docmancer.docs.application._docs_context_projection_core import _requalify_visible_source
    from docmancer.docs.application.qualified_support_units import build_delivery_units

    source, query_text = _native_source(
        tmp_path,
        "# Retry\n\nOn socket timeout:\nRetry the request.\n\nOn DNS timeout:\nRetry the request.\n",
        "When a timeout happens, should I retry the request?",
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
    assert any(body == "On socket timeout:\nRetry the request." for body in bodies)
    assert any(body == "On DNS timeout:\nRetry the request." for body in bodies)
    assert all(unit.required_spans == () for unit in units)


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

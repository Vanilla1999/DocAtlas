from __future__ import annotations

from dataclasses import replace

from docmancer.docs.application.context_variant_retention import is_same_origin_gain
from docmancer.docs.application.qualified_support_units import OriginKey, VariantFootprint
from docmancer.docs.domain.query_reference_binding import ScopeKey


def test_fuller_same_origin_is_novel_with_identical_query_ids() -> None:
    origin = OriginKey(ScopeKey("p", "", "g1"), "d", "a" * 64, 0, 100, "o", "b" * 64)
    old = VariantFootprint(
        origin,
        0,
        40,
        frozenset({(0, 40, "c" * 64)}),
        frozenset({"body-a"}),
        frozenset({"q"}),
    )
    new = replace(
        old,
        end=100,
        unit_keys=old.unit_keys | {(42, 100, "d" * 64)},
        redundancy_keys=old.redundancy_keys | {"body-b"},
    )

    assert old.query_ids == new.query_ids
    assert is_same_origin_gain(old, new)
    assert not is_same_origin_gain(new, old)
    assert not is_same_origin_gain(old, replace(new, origin=replace(origin, document_id="other")))


def test_same_origin_gain_must_preserve_old_span_units_and_query_lineage() -> None:
    origin = OriginKey(ScopeKey("p", "", "g1"), "d", "a" * 64, 0, 120, "o", "b" * 64)
    old = VariantFootprint(
        origin, 10, 50,
        frozenset({(10, 50, "u1")}), frozenset({"r1"}), frozenset({"q1"}),
    )
    good = VariantFootprint(
        origin, 0, 90,
        frozenset({(10, 50, "u1"), (52, 90, "u2")}),
        frozenset({"r1", "r2"}), frozenset({"q1"}),
    )
    assert is_same_origin_gain(old, good)
    assert not is_same_origin_gain(old, replace(good, start=20))
    assert not is_same_origin_gain(old, replace(good, unit_keys=frozenset({(52, 90, "u2")})))
    assert not is_same_origin_gain(old, replace(good, query_ids=frozenset()))
    assert not is_same_origin_gain(old, replace(good, redundancy_keys=old.redundancy_keys))


def test_same_origin_gain_is_promoted_only_after_mandatory_coverage() -> None:
    from docmancer.docs.application.context_variant_retention import (
        prefer_same_origin_gain_candidate,
    )

    origin = OriginKey(ScopeKey("p", "", "g1"), "d", "a" * 64, 0, 100, "o", "b" * 64)
    old = VariantFootprint(
        origin, 0, 40,
        frozenset({(0, 40, "u1")}), frozenset({"r1"}), frozenset({"q"}),
    )
    full = VariantFootprint(
        origin, 0, 100,
        frozenset({(0, 40, "u1"), (42, 100, "u2")}),
        frozenset({"r1", "r2"}), frozenset({"q"}),
    )
    optional = {"evidence_id": "other"}
    upgrade = {"evidence_id": "same"}
    prepared = [optional, upgrade]
    footprints = {id(upgrade): full}

    prefer_same_origin_gain_candidate(
        prepared,
        selected={"same": old},
        footprints=footprints,
        missing_mandatory_ids=set(),
        missing_component_ids=set(),
    )
    assert prepared[0] is upgrade

    blocked = [optional, upgrade]
    prefer_same_origin_gain_candidate(
        blocked,
        selected={"same": old},
        footprints=footprints,
        missing_mandatory_ids={"required-q"},
        missing_component_ids=set(),
    )
    assert blocked[0] is optional


def test_replacement_with_unknown_new_footprint_cannot_discard_verified_content() -> None:
    from docmancer.docs.application.context_variant_retention import (
        replacement_preserves_or_advances_mandatory,
    )

    origin = OriginKey(ScopeKey("p", "", "g1"), "d", "a" * 64, 0, 100, "o", "b" * 64)
    old = VariantFootprint(
        origin, 0, 80,
        frozenset({(0, 40, "u1"), (42, 80, "u2")}),
        frozenset({"r1", "r2"}),
        frozenset({"q"}),
    )

    assert replacement_preserves_or_advances_mandatory(
        old, None,
        candidate_query_ids={"required-q"},
        missing_mandatory_ids={"required-q"},
        candidate_component_ids=set(),
        selected_component_ids=set(),
    ) is False

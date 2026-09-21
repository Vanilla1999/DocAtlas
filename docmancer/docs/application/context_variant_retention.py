"""Pure and bounded helpers for same-origin content-retention decisions."""
from __future__ import annotations

from typing import Any, Callable

from .qualified_support_units import (
    DeliveryUnit,
    VariantFootprint,
    build_delivery_units,
    make_footprint,
)
from .context_selection import bind_visible_assignments, component_witnesses, qualified_query_ids
from docmancer.docs.domain.context_blocks import source_block_alternatives
from docmancer.docs.domain.context_windows import (
    _focused_line_range, _focused_snippet, _is_complete_source_span, _projection_limits,
)


def is_same_origin_gain(old: VariantFootprint, new: VariantFootprint) -> bool:
    """Return whether *new* strictly adds verified content without losing *old*."""
    return bool(
        old.origin == new.origin
        and new.start <= old.start <= old.end <= new.end
        and old.unit_keys <= new.unit_keys
        and old.query_ids <= new.query_ids
        and old.redundancy_keys < new.redundancy_keys
    )


def prepare_delivery_inventory(
    *, source: dict[str, Any], raw_text: str, query_plan: dict[str, Any],
    query_text: dict[str, str], eligible_query_ids: frozenset[str],
    requalify: Callable[..., dict[str, Any]],
) -> tuple[tuple[DeliveryUnit, ...], int | None]:
    """Build one verified unit inventory from the prepared current source window."""
    reference = source.get("_reference_evidence") or {}
    if not (
        isinstance(reference, dict)
        and reference.get("text") == raw_text
        and type(reference.get("char_start")) is int
    ):
        return (), None
    raw_start = int(reference["char_start"])
    prepared = {
        **source,
        "path_or_url": source.get("path") or source.get("source") or "",
        "_qualification_candidate": source.get("_qualification_candidate", source),
        "_independent_query_plan": query_plan,
        "_expected_project_identity": source.get("_expected_project_identity"),
        "_lifecycle_intent": source.get("_lifecycle_intent", "current"),
    }
    return (
        build_delivery_units(
            source=prepared,
            raw_text=raw_text,
            raw_start=raw_start,
            query_text=query_text,
            eligible_query_ids=eligible_query_ids,
            requalify=requalify,
        ),
        raw_start,
    )


def store_variant_footprint(
    *, sink: dict[int, VariantFootprint] | None, candidate: dict[str, Any],
    raw_text: str, raw_start: int | None, units: tuple[DeliveryUnit, ...],
    start: int, end: int, query_ids: frozenset[str],
) -> None:
    """Record a freshly recomputed footprint for one exact current variant."""
    if sink is None or raw_start is None or not units:
        return
    sink[id(candidate)] = make_footprint(
        origin=units[0].origin,
        raw_text=raw_text,
        raw_start=raw_start,
        start=raw_start + start,
        end=raw_start + end,
        units=units,
        query_ids=query_ids,
    )


def prefer_same_origin_gain_candidate(
    prepared: list[dict[str, Any]], *,
    selected: dict[str, VariantFootprint],
    footprints: dict[int, VariantFootprint],
    missing_mandatory_ids: set[str],
    missing_component_ids: set[str],
) -> None:
    """Promote a content upgrade only after mandatory directions are satisfied."""
    if missing_mandatory_ids or missing_component_ids:
        return
    for index, candidate in enumerate(prepared):
        old = selected.get(str(candidate.get("evidence_id") or ""))
        new = footprints.get(id(candidate))
        if old is not None and new is not None and is_same_origin_gain(old, new):
            prepared.insert(0, prepared.pop(index))
            return


def replacement_preserves_or_advances_mandatory(
    old: VariantFootprint | None,
    new: VariantFootprint | None,
    *, candidate_query_ids: set[str], missing_mandatory_ids: set[str],
    candidate_component_ids: set[str], selected_component_ids: set[str],
) -> bool:
    """Reject optional footprint downgrade; allow one only for missing mandatory evidence."""
    if old is None:
        return True
    if new is None:
        return False
    same_footprint = (
        old.origin == new.origin
        and old.unit_keys == new.unit_keys
        and old.redundancy_keys == new.redundancy_keys
        and old.query_ids <= new.query_ids
    )
    if same_footprint or is_same_origin_gain(old, new):
        return True
    return bool(
        candidate_query_ids & missing_mandatory_ids
        or candidate_component_ids - selected_component_ids
    )


def qualified_fragments(
    source: dict[str, Any], *, raw_snippet: str, query_ids: set[str],
    query_text: dict[str, str], source_line_start: Any, requalify,
    obligations: tuple[Any, ...] = (),
    assignments: Any = (),
    delivery_units: tuple[DeliveryUnit, ...] = (),
    delivery_raw_start: int | None = None,
    footprint_sink: dict[int, VariantFootprint] | None = None,
) -> list[dict[str, Any]]:
    """Retain small qualified alternatives until the actual payload is measured."""
    variants = []
    variant_spans: dict[int, tuple[int, int]] = {}
    seen_spans = set()

    focuses = (*tuple(query_text.get(query_id, "") for query_id in sorted(query_ids)),
               *component_witnesses({**source, "snippet": raw_snippet}, obligations).values())
    for limit in _projection_limits(raw_snippet):
        for focus in (focuses, *((value,) for value in focuses if value)):
            snippet, snippet_start, snippet_end = _focused_snippet(
                raw_snippet, focus, limit=limit,
            )
            if (snippet_start, snippet_end) in seen_spans:
                continue
            seen_spans.add((snippet_start, snippet_end))
            candidate = dict(source)
            candidate["snippet"] = snippet
            candidate["line_start"], candidate["line_end"] = _focused_line_range(
                raw_snippet, snippet_start, snippet_end, source_line_start,
            )
            candidate = requalify(candidate, query_text=query_text)
            candidate = bind_visible_assignments(
                source.get("_qualification_candidate", source), candidate, assignments,
            )
            if snippet and (qualified_query_ids((candidate,)) & query_ids or component_witnesses(candidate, obligations)):
                variants.append(candidate)
                variant_spans[id(candidate)] = (snippet_start, snippet_end)
                store_variant_footprint(
                    sink=footprint_sink, candidate=candidate, raw_text=raw_snippet,
                    raw_start=delivery_raw_start, units=delivery_units,
                    start=snippet_start, end=snippet_end,
                    query_ids=frozenset(qualified_query_ids((candidate,)) & query_ids),
                )
    # Exact small atoms can remove a heading or irrelevant adjacent paragraph
    # without widening any rolling window. Larger prose is offered only for an
    # unstructured mandatory direction, not optional aliases or hidden metadata.
    required_ids = set((source.get("_independent_query_plan") or {}).get("required_query_ids") or ())
    preserve_required_blocks = bool(required_ids & query_ids and not obligations and not assignments)
    required_blocks: list[tuple[int, int]] = []
    for snippet_start, snippet_end in source_block_alternatives(raw_snippet).spans:
        if ((snippet_start, snippet_end) in seen_spans
                or (snippet_end - snippet_start > 640 and not preserve_required_blocks)):
            continue
        snippet = raw_snippet[snippet_start:snippet_end]
        candidate = dict(source)
        candidate["snippet"] = snippet
        candidate["line_start"], candidate["line_end"] = _focused_line_range(
            raw_snippet, snippet_start, snippet_end, source_line_start,
        )
        candidate = requalify(candidate, query_text=query_text)
        candidate = bind_visible_assignments(
            source.get("_qualification_candidate", source), candidate, assignments,
        )
        candidate_ids = qualified_query_ids((candidate,)) & query_ids
        if candidate_ids or component_witnesses(candidate, obligations):
            seen_spans.add((snippet_start, snippet_end))
            variants.append(candidate)
            variant_spans[id(candidate)] = (snippet_start, snippet_end)
            store_variant_footprint(
                    sink=footprint_sink, candidate=candidate, raw_text=raw_snippet,
                    raw_start=delivery_raw_start, units=delivery_units,
                    start=snippet_start, end=snippet_end,
                    query_ids=frozenset(qualified_query_ids((candidate,)) & query_ids),
                )
            if preserve_required_blocks and candidate_ids & required_ids:
                required_blocks.append((snippet_start, snippet_end))
    if required_blocks:
        # For an unstructured mandatory request, a clipped interior is not a
        # substitute for its qualified whole block. Typed component/assignment
        # requests above retain their finer-grained witness policy. Admission
        # can reject the whole atom, but cannot silently pass its prefix instead.
        def inside_required_block(candidate: dict[str, Any]) -> bool:
            span = variant_spans.get(id(candidate))
            if span is None:
                return False
            offset, candidate_end = span
            return any(
                block_start <= offset
                and candidate_end <= block_end
                and span != (block_start, block_end)
                for block_start, block_end in required_blocks
            )

        variants = [
            candidate for candidate in variants
            if not inside_required_block(candidate)
        ]
    # Offer one bounded verbatim union span when it preserves both directions.
    seed_variants = tuple(variants)
    for left_index, left in enumerate(seed_variants):
        left_span = variant_spans.get(id(left))
        if left_span is None:
            continue
        left_start, left_end = left_span
        left_ids = qualified_query_ids((left,)) & query_ids
        if not left_ids:
            continue
        for right in seed_variants[left_index + 1:]:
            right_span = variant_spans.get(id(right))
            if right_span is None:
                continue
            right_start, right_end = right_span
            right_ids = qualified_query_ids((right,)) & query_ids
            if not right_ids or left_ids == right_ids:
                continue
            union_ids = left_ids | right_ids
            union_start = min(left_start, right_start)
            union_end = max(left_end, right_end)
            if union_end - union_start > 640 or (union_start, union_end) in seen_spans:
                continue
            union_snippet = raw_snippet[union_start:union_end].strip()
            union_visible_start = raw_snippet.find(
                union_snippet, union_start, union_end + 1,
            )
            if union_visible_start < 0:
                continue
            union_visible_end = union_visible_start + len(union_snippet)
            union_candidate = dict(source)
            union_candidate["snippet"] = union_snippet
            union_candidate["line_start"], union_candidate["line_end"] = _focused_line_range(
                raw_snippet, union_visible_start, union_visible_end, source_line_start)
            union_candidate = requalify(union_candidate, query_text=query_text)
            if not union_ids <= (qualified_query_ids((union_candidate,)) & query_ids):
                continue
            union_candidate = bind_visible_assignments(
                source.get("_qualification_candidate", source), union_candidate, assignments,
            )
            seen_spans.add((union_start, union_end))
            variants.append(union_candidate)
            variant_spans[id(union_candidate)] = (
                union_visible_start, union_visible_end,
            )
            store_variant_footprint(
                sink=footprint_sink, candidate=union_candidate, raw_text=raw_snippet,
                raw_start=delivery_raw_start, units=delivery_units,
                start=union_visible_start, end=union_visible_end,
                query_ids=frozenset(qualified_query_ids((union_candidate,)) & query_ids),
            )

    def structurally_complete(candidate: dict[str, Any]) -> bool:
        span = variant_spans.get(id(candidate))
        return _is_complete_source_span(
            raw_snippet,
            str(candidate.get("snippet") or ""),
            span_start=span[0] if span is not None else None,
        )

    # Prefer structurally complete variants when coverage is otherwise equal.
    variants.sort(
        key=lambda candidate: (
            len(qualified_query_ids((candidate,)) & query_ids),
            len(component_witnesses(candidate, obligations)),
            len(candidate.get("_visible_assignment_hashes") or ()),
            int(structurally_complete(candidate)),
            -len(str(candidate.get("snippet") or "")),
        ),
        reverse=True,
    )
    return variants

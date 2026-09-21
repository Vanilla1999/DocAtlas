"""Private source-local delivery units for bounded docs projection.

These values describe already-qualified visible evidence.  They never grant
source access or answer support and are rebuilt from the current source window.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

from docmancer.docs.domain.query_reference_binding import ScopeKey


@dataclass(frozen=True, slots=True)
class OriginKey:
    scope: ScopeKey
    document_id: str
    source_sha256: str
    source_start: int
    source_end: int
    owner_id: str
    query_plan_sha256: str


@dataclass(frozen=True, slots=True)
class DeliveryUnit:
    origin: OriginKey
    start: int
    end: int
    body_sha256: str
    qualified_query_ids: frozenset[str]
    required_spans: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class VariantFootprint:
    origin: OriginKey
    start: int
    end: int
    unit_keys: frozenset[tuple[int, int, str]]
    redundancy_keys: frozenset[str]
    query_ids: frozenset[str]


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _slice(raw_text: str, raw_start: int, start: int, end: int) -> str | None:
    left, right = start - raw_start, end - raw_start
    if left < 0 or right < left or right > len(raw_text):
        return None
    return raw_text[left:right]


def _validate_requested_span(
    *, origin: OriginKey, raw_text: str, raw_start: int, start: int, end: int,
) -> None:
    if any(type(value) is not int for value in (raw_start, start, end)):
        raise ValueError("delivery span coordinates must be integers")
    raw_end = raw_start + len(raw_text)
    if (
        raw_start != origin.source_start
        or raw_end != origin.source_end
        or start < raw_start
        or end < start
        or end > raw_end
    ):
        raise ValueError("delivery span is outside the exact origin window")


def visible_units(
    *, origin: OriginKey, raw_text: str, raw_start: int,
    start: int, end: int, units: tuple[DeliveryUnit, ...],
) -> tuple[DeliveryUnit, ...]:
    """Return complete, byte-matching units visible in the exact current span."""
    _validate_requested_span(
        origin=origin, raw_text=raw_text, raw_start=raw_start, start=start, end=end,
    )
    if _digest(raw_text) != origin.source_sha256:
        return ()

    result: list[DeliveryUnit] = []
    seen: set[tuple[int, int, str, tuple[tuple[int, int], ...]]] = set()
    for unit in units:
        if unit.origin != origin or not (start <= unit.start < unit.end <= end):
            continue
        body = _slice(raw_text, raw_start, unit.start, unit.end)
        if body is None or _digest(body) != unit.body_sha256:
            continue
        dependencies: list[tuple[int, int]] = []
        valid = True
        for dependency in unit.required_spans:
            if (
                len(dependency) != 2
                or any(type(value) is not int for value in dependency)
                or not start <= dependency[0] < dependency[1] <= end
                or _slice(raw_text, raw_start, dependency[0], dependency[1]) is None
            ):
                valid = False
                break
            dependencies.append(dependency)
        if not valid:
            continue
        key = (unit.start, unit.end, unit.body_sha256, tuple(dependencies))
        if key not in seen:
            seen.add(key)
            result.append(unit)
    return tuple(result)


def _redundancy_key(
    unit: DeliveryUnit, *, raw_text: str, raw_start: int,
) -> str:
    """Fingerprint body plus verified applicability context inside one origin."""
    dependency_parts = []
    for start, end in unit.required_spans:
        value = _slice(raw_text, raw_start, start, end)
        if value is None:  # visible_units already rejects this; fail closed if reused.
            return ""
        dependency_parts.append(f"{start}:{end}:{_digest(value)}")
    context = "|".join(dependency_parts)
    return f"{unit.body_sha256}:{_digest(context)}"


def make_footprint(
    *, origin: OriginKey, raw_text: str, raw_start: int,
    start: int, end: int, units: tuple[DeliveryUnit, ...],
    query_ids: frozenset[str],
) -> VariantFootprint:
    """Collect complete current units separately from retrieval attribution."""
    visible = visible_units(
        origin=origin,
        raw_text=raw_text,
        raw_start=raw_start,
        start=start,
        end=end,
        units=units,
    )
    return VariantFootprint(
        origin=origin,
        start=start,
        end=end,
        unit_keys=frozenset((unit.start, unit.end, unit.body_sha256) for unit in visible),
        redundancy_keys=frozenset(
            key for unit in visible
            if (key := _redundancy_key(unit, raw_text=raw_text, raw_start=raw_start))
        ),
        query_ids=frozenset(query_ids),
    )


def _origin_from_source(*, source: dict, raw_text: str, raw_start: int) -> OriginKey | None:
    import json

    evidence = source.get("_reference_evidence") or {}
    identity = evidence.get("source") or {}
    scope = identity.get("scope") or {}
    if not all(scope.get(key) is not None for key in ("project_id", "version", "snapshot_id")):
        return None
    if evidence.get("char_start") != raw_start or evidence.get("char_end") != raw_start + len(raw_text):
        return None
    owner = evidence.get("owner") or {}
    plan = source.get("_independent_query_plan") or {}
    plan_bytes = json.dumps(plan, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return OriginKey(
        ScopeKey(str(scope["project_id"]), str(scope["version"]), str(scope["snapshot_id"])),
        str(identity.get("document_id") or ""),
        _digest(raw_text),
        raw_start,
        raw_start + len(raw_text),
        str(owner.get("logical_id") or ""),
        hashlib.sha256(plan_bytes).hexdigest(),
    )


def build_delivery_units(*, source: dict, raw_text: str, raw_start: int,
                         query_text: dict[str, str], eligible_query_ids: frozenset[str],
                         requalify) -> tuple[DeliveryUnit, ...]:
    """Enumerate exact blocks, requalify them, and keep minimal supported units."""
    from docmancer.docs.domain.context_blocks import source_block_alternatives

    origin = _origin_from_source(source=source, raw_text=raw_text, raw_start=raw_start)
    if origin is None or _digest(raw_text) != origin.source_sha256:
        return ()
    alternatives = source_block_alternatives(raw_text)
    if "block_work_limited" in alternatives.limitations:
        return ()

    qualified: list[tuple[int, int, frozenset[str]]] = []
    for local_start, local_end in alternatives.spans:
        snippet = raw_text[local_start:local_end]
        if not snippet:
            continue
        candidate = dict(source)
        candidate["snippet"] = snippet
        candidate["char_start"] = raw_start + local_start
        candidate["char_end"] = raw_start + local_end
        result = requalify(candidate, query_text=query_text)
        ids = frozenset(
            str(query_id)
            for query_id, trace in (result.get("retrieval_query_matches") or {}).items()
            if isinstance(trace, dict) and trace.get("qualified") is True
            and str(query_id) in eligible_query_ids
        )
        if ids:
            qualified.append((local_start, local_end, ids))

    # Unions package their independently supported leaves; they are not extra
    # semantic value.  If no smaller qualified block exists, the larger block
    # remains one indivisible conservative unit.
    minimal: list[tuple[int, int, frozenset[str]]] = []
    for item in qualified:
        children = [
            other for other in qualified
            if other != item
            and item[0] <= other[0] < other[1] <= item[1]
            and (other[0], other[1]) != (item[0], item[1])
        ]
        covered_by_children = frozenset(
            query_id for child in children for query_id in child[2]
        )
        novel_ids = item[2] - covered_by_children
        if children and not novel_ids:
            continue
        minimal.append((item[0], item[1], novel_ids or item[2]))
    return tuple(
        DeliveryUnit(
            origin,
            raw_start + start,
            raw_start + end,
            _digest(raw_text[start:end]),
            ids,
        )
        for start, end, ids in sorted(minimal, key=lambda item: (item[0], item[1]))
    )

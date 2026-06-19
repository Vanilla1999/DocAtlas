"""Streaming XML parser for USPTO trademark case-file records.

Uses ``xml.etree.ElementTree.iterparse`` so memory stays flat regardless
of input file size. Calls ``element.clear()`` after each record and
prunes preceding siblings so the document tree never accumulates.
``lxml`` is optional and faster on multi-GB files; we fall back to the
stdlib when it's not installed.

The parser is intentionally tolerant: a single malformed record
increments ``ParseStats.failed`` and is skipped. Callers can inspect
the stats object after the iterator drains.
"""
from __future__ import annotations

import gzip
import io
import logging
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import IO, Iterator

from .schema import CaseFile, CaseFileOwner, GoodsAndServices

logger = logging.getLogger(__name__)

# USPTO's "case-file" tag. Bulk files may wrap many in a single root element.
_CASE_FILE_TAG = "case-file"

# Goods-and-services statements live under <case-file-statements> with type
# codes that start with these prefixes (GS = goods/services, D = description).
_GS_TYPE_PREFIXES = ("GS", "D")


@dataclass
class ParseStats:
    parsed: int = 0
    emitted: int = 0
    skipped_dead: int = 0
    failed: int = 0
    failures_by_reason: dict[str, int] = field(default_factory=dict)

    def record_failure(self, reason: str) -> None:
        self.failed += 1
        self.failures_by_reason[reason] = self.failures_by_reason.get(reason, 0) + 1


def _parse_uspto_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    # USPTO formats dates as YYYYMMDD without separators.
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _text(elem, path: str) -> str | None:
    child = elem.find(path)
    if child is None:
        return None
    return (child.text or "").strip() or None


def _all_text(elem, path: str) -> list[str]:
    return [(c.text or "").strip() for c in elem.findall(path) if (c.text or "").strip()]


def _to_case_file(elem) -> CaseFile | None:
    """Convert a parsed `<case-file>` element to a `CaseFile` model."""
    serial = _text(elem, "serial-number")
    if not serial:
        return None

    header = elem.find("case-file-header")
    mark = _text(header, "mark-identification") if header is not None else None
    if not mark:
        # USPTO sometimes leaves the mark element empty for stylised marks
        # whose only representation is the drawing. Use a placeholder so the
        # record still flows; downstream callers can filter on this if they
        # only want word marks.
        mark = ""

    goods_services: list[GoodsAndServices] = []
    for cls in elem.findall("classifications/classification"):
        intl = _text(cls, "international-code") or ""
        us_codes = _all_text(cls, "us-code-list/us-code")
        goods_services.append(
            GoodsAndServices(
                international_class_code=intl,
                us_class_codes=us_codes,
                description="",
                first_use_anywhere_date=_parse_uspto_date(_text(cls, "first-use-anywhere-date")),
                first_use_in_commerce_date=_parse_uspto_date(_text(cls, "first-use-in-commerce-date")),
            )
        )

    # Goods-and-services *descriptions* live in <case-file-statements>; the
    # type code disambiguates which class they belong to. We collect all
    # GS-type statements and attach them to the first matching class when
    # there's no other binding, or as a generic class="" entry otherwise.
    for stmt in elem.findall("case-file-statements/case-file-statement"):
        type_code = (_text(stmt, "type-code") or "").strip()
        text = _text(stmt, "text") or ""
        if not text:
            continue
        if not type_code or not type_code.startswith(_GS_TYPE_PREFIXES):
            continue
        # USPTO statement codes embed the class as the trailing 3 zero-padded
        # digits (e.g. ``GS030`` → class 030). Keep the zero-padding so it
        # matches the value emitted by ``<international-code>030</international-code>``.
        trailing = type_code[2:]
        intl_class = trailing if (len(trailing) == 3 and trailing.isdigit()) else ""
        target = next(
            (g for g in goods_services if g.international_class_code == intl_class),
            None,
        )
        if target is None:
            target = GoodsAndServices(international_class_code=intl_class, description=text)
            goods_services.append(target)
        elif not target.description:
            target.description = text
        else:
            target.description = f"{target.description}\n{text}"

    owners: list[CaseFileOwner] = []
    for owner_elem in elem.findall("case-file-owners/case-file-owner"):
        party_name = _text(owner_elem, "party-name") or ""
        if not party_name:
            continue
        owners.append(
            CaseFileOwner(
                party_name=party_name,
                party_type=_text(owner_elem, "party-type") or "",
                address=_text(owner_elem, "address-1"),
                nationality=_text(owner_elem, "nationality/country"),
            )
        )

    design_codes = _all_text(elem, "design-searches/design-search/design-search-code")
    pseudo_marks = _all_text(elem, "pseudo-marks/pseudo-mark/pseudo-mark-identification")
    prior_regs = _all_text(elem, "prior-registration-applications/prior-registration-application/other-related-registration-number")

    return CaseFile(
        serial_number=serial,
        registration_number=_text(header, "registration-number") if header is not None else None,
        filing_date=_parse_uspto_date(_text(header, "filing-date") if header is not None else None),
        registration_date=_parse_uspto_date(_text(header, "registration-date") if header is not None else None),
        status_code=_text(header, "status-code") if header is not None else None,
        status_date=_parse_uspto_date(_text(header, "status-date") if header is not None else None),
        mark_identification=mark,
        mark_drawing_code=_text(header, "mark-drawing-code") if header is not None else None,
        goods_and_services=goods_services,
        owners=owners,
        design_search_codes=design_codes,
        pseudo_marks=pseudo_marks,
        prior_registrations=prior_regs,
    )


def _iterparse(source: IO[bytes] | str | Path) -> Iterator:
    """Return an iterparse iterator backed by lxml when available, else stdlib."""
    try:
        from lxml import etree  # type: ignore

        return etree.iterparse(source, events=("end",), tag=_CASE_FILE_TAG, recover=True)
    except ImportError:
        from xml.etree import ElementTree as ET

        return ET.iterparse(source, events=("end",))


def _open_stream(path: Path) -> tuple[IO[bytes], bool]:
    """Open the input, transparently handling .gz and .zip wrappers.

    Returns ``(stream, owns_handle)``. ``.zip`` files yield the first XML
    member; callers wanting all members should iterate them externally.
    """
    suffix = path.suffix.lower()
    if suffix == ".gz":
        return gzip.open(path, "rb"), True
    if suffix == ".zip":
        zf = zipfile.ZipFile(path)
        xml_members = [n for n in zf.namelist() if n.lower().endswith(".xml")]
        if not xml_members:
            raise ValueError(f"no .xml member found inside {path}")
        return zf.open(xml_members[0]), True
    return open(path, "rb"), True


def iter_case_files(
    path: str | Path,
    *,
    live_only: bool = True,
    stats: ParseStats | None = None,
) -> Iterator[CaseFile]:
    """Yield `CaseFile` records from a USPTO XML / XML.gz / ZIP file.

    Memory stays bounded: each element is cleared after parsing and
    earlier siblings are pruned. A single malformed record increments
    ``stats.failed`` and is skipped.
    """
    path = Path(path).expanduser()
    if not path.exists():
        raise FileNotFoundError(path)

    stats = stats if stats is not None else ParseStats()
    stream, _ = _open_stream(path)
    try:
        for event, elem in _iterparse(stream):
            # Stdlib iterparse fires for every tag; filter to <case-file>.
            tag = elem.tag.rsplit("}", 1)[-1] if "}" in elem.tag else elem.tag
            if tag != _CASE_FILE_TAG:
                continue
            stats.parsed += 1
            try:
                case_file = _to_case_file(elem)
            except Exception as exc:  # pragma: no cover - parser is tolerant
                logger.debug("case-file parse failed: %s", exc)
                stats.record_failure(type(exc).__name__)
                case_file = None

            if case_file is None:
                stats.record_failure("invalid-record")
            else:
                if live_only and not case_file.is_live():
                    stats.skipped_dead += 1
                else:
                    stats.emitted += 1
                    yield case_file

            # Free the element and its predecessors so the tree never grows.
            elem.clear()
            parent = elem.getparent() if hasattr(elem, "getparent") else None
            if parent is not None:
                # lxml: drop previous siblings
                while parent[0] is not elem:
                    del parent[0]
    finally:
        try:
            stream.close()
        except Exception:
            pass

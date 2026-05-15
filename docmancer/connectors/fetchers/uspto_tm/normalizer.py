"""Turn a ``CaseFile`` into a docmancer ``Document``.

Each case file becomes exactly one section in the index (``chunking_strategy:
"single"``), so the section ``id`` lines up 1:1 with a USPTO serial number.
Body text is written so FTS5 hits land on mark identification, owner names,
goods/services descriptions, pseudo marks, and design codes.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterator

from docmancer.core.models import Document

from .parser import ParseStats, iter_case_files
from .schema import CaseFile


def case_file_to_document(cf: CaseFile) -> Document:
    """Render a CaseFile as a docmancer ``Document`` with single-section chunking."""
    title = f"{cf.mark_identification or '(no mark)'} (Serial {cf.serial_number})"
    body_parts: list[str] = [
        f"# {cf.mark_identification or '(no mark)'}",
        "",
        f"**Serial Number:** {cf.serial_number}",
    ]
    if cf.registration_number:
        body_parts.append(f"**Registration Number:** {cf.registration_number}")
    if cf.status_code:
        body_parts.append(
            f"**Status:** {cf.status_code}"
            + (f" as of {cf.status_date.isoformat()}" if cf.status_date else "")
        )
    if cf.filing_date:
        body_parts.append(f"**Filing Date:** {cf.filing_date.isoformat()}")
    if cf.registration_date:
        body_parts.append(f"**Registration Date:** {cf.registration_date.isoformat()}")
    if cf.owners:
        owner_names = ", ".join(o.party_name for o in cf.owners if o.party_name)
        if owner_names:
            body_parts.append(f"**Owner(s):** {owner_names}")
    if cf.mark_drawing_code:
        body_parts.append(f"**Mark Drawing Code:** {cf.mark_drawing_code}")

    if cf.goods_and_services:
        body_parts.extend(["", "**Goods and Services:**"])
        for gs in cf.goods_and_services:
            label = f"Class {gs.international_class_code}" if gs.international_class_code else "Class (unspecified)"
            desc = gs.description.strip() if gs.description else "(no description)"
            body_parts.append(f"- {label}: {desc}")

    if cf.pseudo_marks:
        body_parts.extend([
            "",
            f"**Pseudo Marks (USPTO phonetic):** {', '.join(cf.pseudo_marks)}",
        ])

    if cf.design_search_codes:
        body_parts.extend([
            "",
            f"**Design Codes:** {', '.join(cf.design_search_codes)}",
        ])

    if cf.prior_registrations:
        body_parts.extend([
            "",
            f"**Prior Registrations:** {', '.join(cf.prior_registrations)}",
        ])

    content = "\n".join(body_parts).rstrip() + "\n"

    international_classes = sorted(
        {gs.international_class_code for gs in cf.goods_and_services if gs.international_class_code}
    )
    owner_names = [o.party_name for o in cf.owners if o.party_name]
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    metadata = {
        "format": "uspto-tm",
        "chunking_strategy": "single",
        "source_path": f"uspto-tm/{cf.serial_number}.xml",
        "title": title,
        "anchor": title,
        "content_hash": content_hash,
        "serial_number": cf.serial_number,
        "registration_number": cf.registration_number,
        "status_code": cf.status_code,
        "filing_date": cf.filing_date.isoformat() if cf.filing_date else None,
        "registration_date": cf.registration_date.isoformat() if cf.registration_date else None,
        "international_classes": international_classes,
        "mark_drawing_code": cf.mark_drawing_code,
        "owner_names": owner_names,
        "design_codes": cf.design_search_codes,
        "pseudo_marks": cf.pseudo_marks,
    }

    return Document(
        source=f"uspto-tm://{cf.serial_number}",
        content=content,
        metadata=metadata,
    )


def iter_uspto_documents(
    path: str | Path,
    *,
    live_only: bool = True,
    stats: ParseStats | None = None,
) -> Iterator[Document]:
    """Stream-parse a USPTO XML file and yield docmancer ``Document`` objects."""
    for cf in iter_case_files(path, live_only=live_only, stats=stats):
        yield case_file_to_document(cf)

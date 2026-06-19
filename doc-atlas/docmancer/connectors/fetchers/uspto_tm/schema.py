"""Pydantic models for USPTO trademark case-file records.

Mirrors the subset of `tm_caseFile.xsd` we actually use for retrieval.
Optional fields stay ``None`` when missing from the XML rather than
raising — bulk USPTO data is uneven and one bad record should never
abort an ingest of millions.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class GoodsAndServices(BaseModel):
    """One goods-and-services description for an international class."""

    international_class_code: str = ""
    us_class_codes: list[str] = Field(default_factory=list)
    description: str = ""
    first_use_anywhere_date: Optional[date] = None
    first_use_in_commerce_date: Optional[date] = None


class CaseFileOwner(BaseModel):
    """One owner / applicant record."""

    party_name: str = ""
    party_type: str = ""
    address: Optional[str] = None
    nationality: Optional[str] = None


class CaseFile(BaseModel):
    """A single USPTO trademark case file.

    The schema is intentionally permissive: every field except
    ``serial_number`` and ``mark_identification`` is optional, so daily
    XML files with partial records still flow through the pipeline.
    """

    serial_number: str
    registration_number: Optional[str] = None
    filing_date: Optional[date] = None
    registration_date: Optional[date] = None
    status_code: Optional[str] = None
    status_date: Optional[date] = None
    mark_identification: str = ""
    mark_drawing_code: Optional[str] = None
    goods_and_services: list[GoodsAndServices] = Field(default_factory=list)
    owners: list[CaseFileOwner] = Field(default_factory=list)
    design_search_codes: list[str] = Field(default_factory=list)
    pseudo_marks: list[str] = Field(default_factory=list)
    prior_registrations: list[str] = Field(default_factory=list)
    correspondent: Optional[str] = None

    def is_live(self) -> bool:
        """Best-effort "is this mark active" check.

        USPTO encodes statuses with numeric codes. The "live registration /
        pending application" range covers most cases worth indexing; the
        full mapping lives in the USPTO status-code reference. Callers
        that want stricter filtering should consult their own allowlist.
        """
        if not self.status_code:
            return False
        # Status codes 600–899 are typically post-registration "live"; 60x–69x
        # are pending. Anything 700+ that isn't dead. This is a coarse filter
        # and is intentionally over-permissive — refine per project.
        try:
            code = int(self.status_code)
        except ValueError:
            return False
        return 600 <= code < 900

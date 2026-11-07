"""Host-only model-text revision; source admission and machine packets stay intact."""
from __future__ import annotations

import os


ENVIRONMENT_KEY = "DOCATLAS_CONTEXT_PRESENTATION"
LITERAL_V2 = "literal-v2"
LITERAL_FORMAT = "docatlas.standalone-text.v2"


def literal_presentation_enabled() -> bool:
    value = os.environ.get(ENVIRONMENT_KEY, "off")
    if value not in ("", "off", LITERAL_V2):
        raise ValueError("invalid_DOCATLAS_CONTEXT_PRESENTATION")
    return value == LITERAL_V2


def presentation_settings() -> dict[str, str]:
    """Do not add even an empty setting to historical continuation fingerprints."""
    return {ENVIRONMENT_KEY: LITERAL_V2} if literal_presentation_enabled() else {}


def validate_context_presentation(*, minimal: bool) -> None:
    """A literal model view requires the existing single, public text lane."""
    if literal_presentation_enabled() and not minimal and (
        os.environ.get("DOCATLAS_MCP_TEXT_FALLBACK") != "1"
        or os.environ.get("DOCATLAS_MCP_COMPACT_TEXT") != "1"
        or os.environ.get("DOCATLAS_MCP_MODEL_VIEW") == "1"
    ):
        raise ValueError("literal-v2 requires compact text fallback and excludes private model view")

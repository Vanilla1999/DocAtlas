"""Self-contained, citation-preserving MCP text for ordinary OpenCode clients.

OpenCode v2.1.2 drops MCP _meta, so the private-ledger model view is not
appropriate there. This is a distinct, fully text-carried projection: the
original selected source text, exact public evidence ID, source-read URI and
source scope/version/authority remain in the model-facing tool result.

No new retrieval, model, authority, summaries or permission is introduced.
The MCP boundary decides whether a canonical fallback can be delivered safely.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math

from .model_context_view import ModelViewError, canonical, encode_model_result
from .projection_tokenizer import projection_token_count
from .section_compression import expand_sections

FORMAT = "docatlas.standalone-text.v1"
COMPACT_TEXT_MAX_TOKENS = 12000
# Never discard a future source field silently. All recognized omitted fields
# are either redundant with the display, or the hash verified by the server.
_KNOWN_SOURCE_FIELDS = frozenset({
    "path_or_url", "snippet", "evidence_id", "source_uri", "section",
    "line_start", "line_end", "scope", "version_binding", "authority",
    "instruction_trust", "freshness", "source_type", "project_identity",
    "content_sha256",
})


@dataclass(frozen=True)
class StandaloneTextResult:
    text: str | None
    reason_code: str | None = None


class StandaloneTextError(ValueError):
    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


def compact_text_fits(text: str) -> bool:
    """Apply the existing text budget without shortening a source or packet."""
    body = text.encode("utf-8")
    return (math.ceil(len(body) / 4) <= COMPACT_TEXT_MAX_TOKENS
            and projection_token_count(body) <= COMPACT_TEXT_MAX_TOKENS)


def render_standalone_text(packet: dict) -> StandaloneTextResult:
    """Report a stable refusal reason without publishing source text in errors."""
    try:
        text = _encode_standalone_text(packet)
        return StandaloneTextResult(text, None if text is not None else "unsupported_context_packet")
    except (ModelViewError, StandaloneTextError) as exc:
        return StandaloneTextResult(None, exc.reason_code)
    except (ValueError, TypeError, KeyError) as exc:
        reason = {
            "invalid_model_view_sources": "invalid_source_binding",
            "model_view_field_collision": "model_view_field_collision",
            "invalid_DOCATLAS_CONTEXT_ASSEMBLY": "invalid_context_assembly_policy",
        }.get(str(exc), "invalid_compact_context")
        return StandaloneTextResult(None, reason)


def encode_standalone_text(packet: dict) -> str | None:
    """Compatibility entry point for replay consumers that only need the text."""
    return render_standalone_text(packet).text


def _encode_standalone_text(packet: dict) -> str | None:
    """Render original evidence with resolvable public references, or refuse.

    All validity checks/source authorization were already performed by the
    standard projection. Unsupported source shapes never lose unknown fields
    merely to make the compact representation fit.
    """
    rendered = encode_model_result(packet)
    if rendered is None:
        return None
    view, _private = rendered  # Do NOT attach a ledger OpenCode cannot retain.
    expanded = expand_sections(packet)
    rows = expanded["sources"]
    if len(rows) != len(view["sources"]):
        raise StandaloneTextError("source_row_count_mismatch")
    if any(set(row) - _KNOWN_SOURCE_FIELDS for row in rows):
        raise StandaloneTextError("unsupported_source_fields")
    if any(not isinstance(row.get("evidence_id"), str)
           or not row["evidence_id"] or not isinstance(row.get("path_or_url"), str)
           or not isinstance(row.get("snippet"), str) for row in rows):
        raise StandaloneTextError("invalid_source_binding")
    if len({row["evidence_id"] for row in rows}) != len(rows):
        raise StandaloneTextError("duplicate_source_reference")

    # A one-project response pays for that provenance once, not once per line.
    identities = [row.get("project_identity") for row in rows]
    shared_identity = bool(identities) and identities[0] is not None and all(
        identity == identities[0] for identity in identities)
    if shared_identity:
        view.setdefault("source_context", {})["project_identity"] = deepcopy(identities[0])

    for visible, original in zip(view["sources"], rows, strict=True):
        if (visible.get("text") != original["snippet"]
                or visible.get("path") != original["path_or_url"]):
            raise StandaloneTextError("source_text_mismatch")
        # Unlike an opaque response-local short ref, this is the original
        # evidence_id already advertised by DocAtlas to ordinary clients.
        visible["ref"] = original["evidence_id"]
        if "source_uri" in original:
            visible["source_uri"] = deepcopy(original["source_uri"])
        if not shared_identity and "project_identity" in original:
            visible["project_identity"] = deepcopy(original["project_identity"])
    view["context_format"] = FORMAT
    text = canonical(view)
    if not compact_text_fits(text):
        raise StandaloneTextError("standalone_context_output_limit")
    # Separate, reversible Context Assembly stage. It never chooses evidence.
    from .context_assembly import assemble_context
    return assemble_context(text)

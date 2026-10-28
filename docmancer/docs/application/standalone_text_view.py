"""Self-contained, citation-preserving MCP text for ordinary OpenCode clients.

OpenCode v2.1.2 drops MCP _meta, so the private-ledger model view is not
appropriate there. This is a distinct, fully text-carried projection: the
original selected source text, exact public evidence ID, source-read URI and
source scope/version/authority remain in the model-facing tool result.

No new retrieval, model, authority, summaries or permission is introduced.
Unsupported shapes revert to the existing canonical text delivery.
"""
from __future__ import annotations

from copy import deepcopy
import math

from .model_context_view import canonical, encode_model_result
from .projection_tokenizer import projection_token_count
from .section_compression import expand_sections

FORMAT = "docatlas.standalone-text.v1"
# Never discard a future source field silently. All recognized omitted fields
# are either redundant with the display, or the hash verified by the server.
_KNOWN_SOURCE_FIELDS = frozenset({
    "path_or_url", "snippet", "evidence_id", "source_uri", "section",
    "line_start", "line_end", "scope", "version_binding", "authority",
    "instruction_trust", "freshness", "source_type", "project_identity",
    "content_sha256",
})


def encode_standalone_text(packet: dict) -> str | None:
    """Render original evidence with resolvable public references, or None.

    All validity checks/source authorization were already performed by the
    standard projection. A missing metadata field or unsupported future source
    shape falls back to the *complete* original text payload at the MCP edge.
    """
    rendered = encode_model_result(packet)
    if rendered is None:
        return None
    view, _private = rendered  # Do NOT attach a ledger OpenCode cannot retain.
    expanded = expand_sections(packet)
    rows = expanded["sources"]
    if len(rows) != len(view["sources"]):
        return None
    if any(set(row) - _KNOWN_SOURCE_FIELDS for row in rows):
        return None
    if any(not isinstance(row.get("evidence_id"), str)
           or not row["evidence_id"] or not isinstance(row.get("path_or_url"), str)
           or not isinstance(row.get("snippet"), str) for row in rows):
        return None
    if len({row["evidence_id"] for row in rows}) != len(rows):
        return None

    # A one-project response pays for that provenance once, not once per line.
    identities = [row.get("project_identity") for row in rows]
    shared_identity = bool(identities) and identities[0] is not None and all(
        identity == identities[0] for identity in identities)
    if shared_identity:
        view.setdefault("source_context", {})["project_identity"] = deepcopy(identities[0])

    for visible, original in zip(view["sources"], rows, strict=True):
        if (visible.get("text") != original["snippet"]
                or visible.get("path") != original["path_or_url"]):
            return None
        # Unlike an opaque response-local short ref, this is the original
        # evidence_id already advertised by DocAtlas to ordinary clients.
        visible["ref"] = original["evidence_id"]
        if "source_uri" in original:
            visible["source_uri"] = deepcopy(original["source_uri"])
        if not shared_identity and "project_identity" in original:
            visible["project_identity"] = deepcopy(original["project_identity"])
    view["context_format"] = FORMAT
    text = canonical(view)
    body = text.encode("utf-8")
    if max(projection_token_count(body), math.ceil(len(body) / 4)) > 12000:
        return None
    # Separate, reversible Context Assembly stage. It never chooses evidence.
    from .context_assembly import assemble_context
    return assemble_context(text)

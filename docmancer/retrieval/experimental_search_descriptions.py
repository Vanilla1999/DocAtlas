"""Source-bound, opt-in retrieval annotations; never authoritative evidence."""
from __future__ import annotations

import hashlib

from docmancer.core.structured_chunking import estimate_utf8_tokens

ARTIFACT_KEY = "experimental_search_descriptions_v1"
CHILD_KEY = "experimental_search_description_v1"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_artifact(artifact, *, source_path: str, content: str, spans) -> dict:
    """Validate the entire artifact, including entries not selected for append."""
    header = {"source_path", "source_sha256", "context_sha256", "recipe", "version",
              "model", "model_revision", "records"}
    if type(artifact) is not dict or set(artifact) != header:
        raise ValueError("invalid search-description artifact fields")
    for key in header - {"records", "model_revision"}:
        if type(artifact[key]) is not str or not artifact[key].strip():
            raise ValueError(f"invalid search-description {key}")
    if artifact["model_revision"] is not None and (
        type(artifact["model_revision"]) is not str or not artifact["model_revision"].strip()
    ):
        raise ValueError("invalid search-description model_revision")
    if (artifact["source_path"] != source_path
            or artifact["source_sha256"] != sha256(content)
            or artifact["context_sha256"] != sha256(content)):
        raise ValueError("search-description source/context binding mismatch")
    if type(artifact["records"]) is not list:
        raise ValueError("search-description records must be a list")
    allowed = set(spans)
    records = {}
    for record in artifact["records"]:
        if type(record) is not dict or set(record) != {
            "char_start", "char_end", "display_sha256", "description", "description_sha256"
        }:
            raise ValueError("invalid search-description record fields")
        start, end = record["char_start"], record["char_end"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(content):
            raise ValueError("invalid search-description span")
        for key in ("display_sha256", "description", "description_sha256"):
            if type(record[key]) is not str or not record[key].strip():
                raise ValueError(f"invalid search-description {key}")
        span = (start, end)
        if span not in allowed or span in records:
            raise ValueError("unmatched or duplicate search-description span")
        if (record["display_sha256"] != sha256(content[start:end])
                or record["description_sha256"] != sha256(record["description"])):
            raise ValueError("search-description content hash mismatch")
        records[span] = record
    return records


def append_description(baseline: str, record: dict, hard_max: int) -> tuple[str, str]:
    description = record["description"]
    if len(description.encode("utf-8")) > 512:
        return baseline, "skipped_description_bytes"
    combined = f"{baseline}\n{description}"
    if estimate_utf8_tokens(combined) > hard_max:
        return baseline, "skipped_retrieval_budget"
    return combined, "appended"


def child_binding(artifact: dict, record: dict, status: str) -> dict:
    return {**{key: value for key, value in artifact.items() if key != "records"},
            "record": record, "status": status}

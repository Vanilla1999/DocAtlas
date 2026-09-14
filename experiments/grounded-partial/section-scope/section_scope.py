"""Source-bound heading context, experiment only; no retrieval or gold access."""
from __future__ import annotations
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import re
from unittest.mock import patch

PREFIX = "source-section: "
STAMP_KEYS = ("_source_snapshot_sha256", "_source_catalog_hash", "version")


@dataclass(frozen=True)
class Heading:
    level: int
    line: int
    start: int
    end: int
    text: str


def headings(document: str) -> tuple[Heading, ...]:
    """Conservative ATX/Setext outline. Fenced and HTML block bodies are ignored.

    Not a general Markdown parser. Blockquote/indented headings are deliberately
    not inferred; unsupported structures fail to supply context, not evidence.
    """
    lines = document.splitlines(keepends=True)
    offsets, total = [], 0
    for line in lines:
        offsets.append(total)
        total += len(line)
    found, fence, html, skip = [], "", False, -1
    for i, line in enumerate(lines):
        if i == skip:
            continue
        fm = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        if fence:
            if fm and fm[1][0] == fence[0] and len(fm[1]) >= len(fence) and not fm[2].strip():
                fence = ""
            continue
        if fm:
            fence = fm[1]
            continue
        if re.match(r"^ {0,3}<(?:!--|/?[A-Za-z])", line):
            html = True
        if html:
            if not line.strip():
                html = False
            continue
        match = re.match(r"^(#{1,6})[ \t]+(.+?)[ \t]*\r?\n?$", line)
        if match:
            found.append((len(match[1]), i + 1, offsets[i], line.rstrip("\r\n")))
        elif (line.strip() and not line.startswith((" ", "\t", ">"))
              and i + 1 < len(lines) and re.fullmatch(r"(?:={3,}|-{3,})\s*", lines[i + 1])):
            level = 1 if lines[i + 1].startswith("=") else 2
            found.append((level, i + 1, offsets[i], line.rstrip("\r\n")))
            skip = i + 1
    result = []
    for i, (level, line, start, text) in enumerate(found):
        end = next((h[2] for h in found[i + 1:] if h[0] <= level), len(document))
        result.append(Heading(level, line, start, end, text))
    return tuple(result)


def present(term: str, text: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(term.casefold()) + r"(?!\w)", text.casefold()) is not None


def explicit_owners(text: str) -> tuple[str, ...]:
    # Narrow obstruction, not semantic entity recognition: code-spelled names
    # or multi-capital API names in an intervening heading cannot be ignored.
    quoted = re.findall(r"`([A-Za-z_][\w.]*)`", text)
    camel = [v for v in re.findall(r"\b[A-Za-z_]\w*\b", text) if re.search(r"[a-z][A-Z]", v)]
    return tuple(dict.fromkeys((*quoted, *camel)))


class ScopeBinder:
    def __init__(self, documents: dict[str, str], identity: str, stamps: dict[str, tuple]):
        self.documents = dict(documents)
        self.identity = identity
        self.stamps = dict(stamps)
        self.outlines = {p: headings(t) for p, t in documents.items()}
        self.digests = {p: hashlib.sha256(t.encode()).hexdigest() for p, t in documents.items()}

    def bind(self, source: dict) -> dict | None:
        origin = source.get("_qualification_candidate", source)
        path = str(source.get("path_or_url") or origin.get("path") or "")
        if (origin.get("source_class") != "project_doc" or origin.get("project_identity") != self.identity
            or source.get("_expected_project_identity", self.identity) != self.identity
            or origin.get("stale") or origin.get("freshness", "current") != "current"
            or origin.get("index_freshness", "synchronized") != "synchronized"
            or origin.get("risk_flags") or origin.get("instruction_risk_flags")
            or path not in self.documents or path != origin.get("path")
            or tuple(origin.get(k) for k in STAMP_KEYS) != self.stamps.get(path)):
            return None
        text = source.get("snippet")
        raw = origin.get("content")
        start, end = origin.get("char_start"), origin.get("char_end")
        if (not isinstance(text, str) or not text.strip() or not isinstance(raw, str)
            or type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(self.documents[path])
            or self.documents[path][start:end] != raw):
            return None
        offset = raw.find(text)
        if offset < 0 or raw.find(text, offset + 1) >= 0:
            return None
        absolute = start + offset
        first = absolute + len(text) - len(text.lstrip())
        last = absolute + len(text.rstrip())
        chain = [h for h in self.outlines[path] if h.start <= first and last <= h.end]
        if not chain:
            return None
        return {"path": path, "document_sha256": self.digests[path],
                "start": absolute, "end": absolute + len(text),
                "headings": [{"line": h.line, "text": h.text} for h in chain]}

    def qualify(self, original, probe, source, **kwargs):
        before = original(probe, **kwargs)
        proof = self.bind(source)
        missing = tuple(before.trace.get("missing_exact_terms") or ())
        if (before.qualified or before.reason != "insufficient_visible_match" or not missing
            or len(before.trace.get("body_matched_terms") or ()) < 2 or proof is None):
            return before, None
        chain = proof["headings"]
        for term in missing:
            owners = [i for i, h in enumerate(chain) if present(term, h["text"])]
            if not owners or any(explicit_owners(h["text"]) and not present(term, h["text"])
                                 for h in chain[max(owners) + 1:]):
                return before, None
        context = "\n".join("# " + h["text"].lstrip("# ") for h in chain)
        body = kwargs.get("evidence_text")
        if body != source.get("snippet"):
            return before, None
        after = original(probe, **{**kwargs, "evidence_text": context + "\n" + body,
                                   "visible_text": kwargs["visible_text"] + "\n" + context})
        return (after, proof) if after.qualified else (before, None)


def label(proof: dict) -> str:
    return PREFIX + " > ".join(f"L{h['line']}: {h['text']}" for h in proof["headings"])


@contextmanager
def installed(binder: ScopeBinder, mode: str, events: list):
    from docmancer.docs.application import docs_context_projection as projection
    original_requalify = projection._requalify_visible_source
    original_qualify = projection.qualify_evidence

    def requalify(source, **parameters):
        source = dict(source)
        origin = source.get("_qualification_candidate", source)
        if str(source.get("section", "")).startswith(PREFIX):
            source["section"] = str(origin.get("heading_path") or origin.get("title") or "document")
        stage = "visible_window" if "_independent_query_plan" in source else "initial_candidate"
        proofs = []

        def qualifier(probe, **kwargs):
            before = original_qualify(probe, **kwargs)
            after, proof = (before, None)
            if mode == "scope_requalify" or stage == "initial_candidate":
                after, proof = binder.qualify(original_qualify, probe, source, **kwargs)
            if proof:
                proofs.append(proof)
            if kwargs["query_id"] == "query-original" or proof:
                events.append({"stage": stage, "query_id": kwargs["query_id"],
                               "path": source.get("path_or_url", origin.get("path")),
                               "snippet": source.get("snippet"), "before": dict(before.trace),
                               "after": dict(after.trace), "scope_proof": proof})
            return after

        with patch.object(projection, "qualify_evidence", qualifier):
            result = original_requalify(source, **parameters)
        if proofs:
            assert all(p == proofs[0] for p in proofs)
            result["section"] = label(proofs[0])
        return result

    with patch.object(projection, "_requalify_visible_source", requalify):
        yield

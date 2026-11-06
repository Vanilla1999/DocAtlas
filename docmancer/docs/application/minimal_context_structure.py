"""Checked own-body scoring and source-exact structural dependency closure.

The native parser's parents are *own* sections, ending at the next heading.
Subtrees are a delivery operation, never an ancestor's scoring body. Hydration
requires both live native provenance and the ordinary source qualification;
neither a serialized snapshot nor raw_document alone is a grant.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
import hashlib
from html import unescape
import json
import posixpath
import re
from urllib.parse import unquote, urlsplit

from docmancer.core.structured_chunking import _atom_spans, parse_markdown_parents
from docmancer.docs.domain.literal_context_admission import (
    _checked_original_candidate, recheck_source_valid_candidate,
)
from docmancer.docs.domain.original_body_discovery import original_body_derivation_binding
from docmancer.docs.domain.query_reference_binding import prepare_reference_probe
from .complete_context_scoring import ScoringUnit
from .model_visible_projection import _docs_source, _snapshot_entry


STRUCTURAL_RECIPE = "minimal-structure-v1"
EVIDENCE_STRUCTURAL_RECIPE = "own_body_ancestors_definitions_no_automatic_anchor_or_seed_subtrees_v2"
REFERENCE_STRUCTURAL_RECIPE = "explicit_addressed_section_closure_v3"


class StructuralContextError(ValueError):
    reason_code = "scan_incomplete"

    def __init__(self, message, **details):
        super().__init__(message)
        self.receipt = {"structural_recipe": STRUCTURAL_RECIPE,
                        "status": self.reason_code, "error": message, **details}


@dataclass
class _Document:
    identity: str
    path: str
    raw: str
    seeds: list
    parents: list
    ancestors: list = field(default_factory=list)
    subtrees: list = field(default_factory=list)
    anchors: dict = field(default_factory=dict)
    definitions: dict = field(default_factory=dict)
    syntax: list = field(default_factory=list)


@dataclass
class StructuralUnits:
    units: tuple[ScoringUnit, ...]
    metadata: dict
    documents: dict
    question: str
    expected_project_identity: str | None
    receipt: dict
    recipe: str = STRUCTURAL_RECIPE

    @property
    def scoring_units(self):
        return self.units


def _identity(candidate):
    ref = candidate["_reference_evidence"]
    return json.dumps({
        "source": ref["source"], "member": ref.get("member_binding"),
        "file_hash": ref.get("project_doc_content_hash"),
        "candidate": {key: candidate.get(key) for key in (
            "project_identity", "_source_snapshot_sha256", "_source_catalog_hash",
            "resolved_version", "generation_id", "doc_scope", "module_path",
            "authority", "instruction_trust",
        )},
    }, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _check_seed(source, question, expected):
    ref = source.get("_reference_evidence") or {}
    text = ref.get("text")
    receipt = recheck_source_valid_candidate(
        question=question, evidence_text=text if isinstance(text, str) else "",
        candidate=source, expected_project_identity=expected,
        lifecycle_intent=source.get("_lifecycle_intent", "current"),
    )
    if receipt is None:
        raise StructuralContextError("Native structural source failed live recheck")
    return receipt


def _syntax(raw, parent):
    """Mask literal code, retaining coordinates for syntax-only dependency edges."""
    text = list(raw[parent.char_start:parent.char_end])
    for atom in _atom_spans(raw, parent.char_start, parent.char_end):
        if atom.atom_type == "code":
            for i in range(atom.start - parent.char_start, atom.end - parent.char_start):
                if text[i] not in "\r\n":
                    text[i] = " "
    value = "".join(text)
    # Equal-length backtick runs delimit inline literals; no topical inference.
    value = re.sub(r"(`+)(?!`)(.*?)(?<!`)\1(?!`)",
                   lambda m: " " * len(m[0]), value, flags=re.S)
    value = re.sub(r"<!--.*?-->", lambda m: " " * len(m[0]), value, flags=re.S)
    return re.sub(r"\\[\[\]()]", "  ", value)


def _label(value):
    return " ".join(value.split()).casefold()


def _prepare_structure(doc):
    stack = []
    slug_counts = defaultdict(int)
    for index, parent in enumerate(doc.parents):
        while stack and doc.parents[stack[-1]].level >= parent.level:
            stack.pop()
        doc.ancestors.append(tuple(stack))
        if parent.level:
            stack.append(index)
        doc.subtrees.append(index + 1)
        if parent.level:
            slug = re.sub(r"[^\w\- ]", "", parent.title.casefold()).replace(" ", "-")
            count = slug_counts[slug]
            slug_counts[slug] += 1
            doc.anchors.setdefault(slug + (f"-{count}" if count else ""), []).append(index)
        syntax = _syntax(doc.raw, parent)
        doc.syntax.append(syntax)
        for match in re.finditer(r"<(?:[A-Za-z][\w:-]*)\b[^>]*?\b(?:id|name)\s*=\s*(['\"])(.*?)\1[^>]*>", syntax):
            doc.anchors.setdefault(match[2], []).append(index)
        for match in re.finditer(r"(?m)^ {0,3}\[([^\]\n]+)\]:[ \t]*(.*)$", syntax):
            destination = match[2].strip()
            # A reference destination may start on the next nonblank line.
            # Keep footnote continuation as body, not a URL destination.
            if not destination and not match[1].startswith("^"):
                following = re.match(r"\r?\n[ \t]*([^\s].*)", syntax[match.end():])
                if following is not None:
                    destination = following[1].strip()
            doc.definitions.setdefault(_label(match[1]), []).append((index, destination))
    # Stack-based ends avoid a quadratic walk for deeply nested sections.
    stack = []
    for index, parent in enumerate(doc.parents):
        while stack and doc.parents[stack[-1]].level >= parent.level:
            doc.subtrees[stack.pop()] = index
        if parent.level:
            stack.append(index)
    for index in stack:
        doc.subtrees[index] = len(doc.parents)


def _hydrate(doc, index, structure):
    """Bind one complete parser-owned span through live source lineage.

    This deliberately does not use legacy containing_span's 4096-parent gate.
    The exact parser parent coordinates are the structural proof, and canonical
    qualification plus the same-call derivation binding independently check the
    hydrated bytes. This creates no discovery receipts or query coverage.
    """
    parent = doc.parents[index]
    a, b = parent.char_start, parent.char_end
    seed = next((s for s in doc.seeds if
                 a <= s["_reference_evidence"]["char_start"] < b), doc.seeds[0])
    _check_seed(seed, structure.question, structure.expected_project_identity)
    raw, text = doc.raw, doc.raw[a:b]
    source = {**seed, "_reference_evidence": dict(seed["_reference_evidence"])}
    header_end = a + len(text.splitlines(keepends=True)[0]) if parent.level else a
    source.update(content=text, display_text=text, snippet=text,
                  char_start=a, char_end=b, byte_start=parent.byte_start,
                  byte_end=parent.byte_end, line_start=parent.line_start,
                  line_end=parent.line_end, title=parent.title,
                  heading_path=" > ".join(parent.heading_path),
                  retrieval_query_ids=[], retrieval_query_matches={},
                  _assigned_requirement_ids=[])
    source["_reference_evidence"].update(text=text, char_start=a, char_end=b, owner={
        "text": raw[a:header_end], "char_start": a, "char_end": header_end,
        "scope_start": a, "scope_end": b, "logical_id": parent.logical_id,
    } if parent.level else None)
    lineage = original_body_derivation_binding(
        question=structure.question, body=text, candidate=source, native_candidate=seed)
    checked = _checked_original_candidate(
        question=structure.question, evidence_text=text, candidate=source,
        expected_project_identity=structure.expected_project_identity,
        lifecycle_intent=source.get("_lifecycle_intent", "current"))
    _, reason = prepare_reference_probe({}, candidate=source, evidence_text=text)
    if (lineage is None or checked is None or reason is not None or
            not (checked[0].qualified or checked[0].reason == "source_valid_relevance_unassessed")):
        raise StructuralContextError("Structural source hydration rejected", path=doc.path,
                                     char_start=a, char_end=b, qualification_reason=reason or
                                     (checked[0].reason if checked else "missing_qualification"))
    evidence_id = "ev-" + hashlib.sha256(f"{doc.identity}:{a}:{b}".encode()).hexdigest()[:24]
    row = _docs_source(source, display_snippet=text, evidence_id=evidence_id)
    if row is None:
        raise StructuralContextError("Structural source projection rejected", path=doc.path)
    row.update(snippet=text, project_identity=seed.get("project_identity"),
               line_start=parent.line_start, line_end=parent.line_end,
               authority=str(seed.get("authority") or "supporting"),
               scope=str(seed.get("doc_scope") or "project"),
               retrieval_query_ids=[], retrieval_query_matches={}, _assigned_requirement_ids=[])
    bound = _snapshot_entry(source, row)
    # Host-only provenance for the terminal revalidator; never a serialized grant.
    bound["structural_native_candidate"] = seed
    bound["structural_recipe"] = structure.recipe
    return row, bound


def build_units(payload, snapshot, retrieval, *, recipe=STRUCTURAL_RECIPE):
    """Build all checked own bodies, with ancestors as scoring context only."""
    if recipe not in {STRUCTURAL_RECIPE, EVIDENCE_STRUCTURAL_RECIPE, REFERENCE_STRUCTURAL_RECIPE}:
        raise StructuralContextError("Unknown structural recipe")
    plan = retrieval.get("documentation_query_plan") or {}
    question = str(plan.get("original_question") or retrieval.get("question") or "")
    expected = retrieval.get("project_identity")
    documents = {}
    for row in payload.get("sources") or ():
        source = (snapshot.get(row.get("evidence_id")) or {}).get("source")
        if not isinstance(source, dict):
            raise StructuralContextError("Missing checked native snapshot")
        _check_seed(source, question, expected)
        ref = source["_reference_evidence"]
        identity = _identity(source)
        if identity not in documents:
            raw = ref["raw_document"]
            documents[identity] = _Document(identity, ref["source"]["canonical_path"], raw, [],
                parse_markdown_parents(raw, ref["source"]["document_id"]))
        documents[identity].seeds.append(source)
    structure = StructuralUnits((), {}, documents, question, expected, {
        "structural_recipe": recipe, "status": "complete",
        "documents": len(documents), "incomplete_dependencies": [],
    }, recipe=recipe)
    units = []
    for identity, doc in documents.items():
        _prepare_structure(doc)
        for index, parent in enumerate(doc.parents):
            # Check *every* hydrated section before its bytes reach the scorer,
            # including introductory context and otherwise empty headings.
            _hydrate(doc, index, structure)
        for index, parent in enumerate(doc.parents):
            body_start = parent.char_start
            if parent.level:
                body_start += len(doc.raw[parent.char_start:parent.char_end].splitlines(keepends=True)[0])
            body = doc.raw[body_start:parent.char_end]
            if not body.strip():
                continue
            unit_id = "unit-" + hashlib.sha256(f"{identity}:{parent.char_start}:{parent.char_end}".encode()).hexdigest()
            ancestors = list(doc.ancestors[index])
            if index and doc.parents[0].level == 0:
                ancestors.insert(0, 0)
            context = "".join(doc.raw[doc.parents[i].char_start:doc.parents[i].char_end] for i in ancestors)
            context += doc.raw[parent.char_start:body_start]
            heading_context = "".join(
                doc.raw[doc.parents[i].char_start:doc.parents[i].char_end].splitlines(keepends=True)[0]
                for i in (*ancestors, index) if doc.parents[i].level)
            units.append(ScoringUnit(unit_id, body, context, heading_context))
            structure.metadata[unit_id] = {
                "path": doc.path, "source_identity": identity, "section_index": index,
                "char_start": parent.char_start, "char_end": parent.char_end,
                "body_char_start": body_start, "heading_path": list(parent.heading_path),
                "line_start": parent.line_start, "line_end": parent.line_end,
                "source_sha256": doc.seeds[0]["_reference_evidence"]["source"]["content_sha256"],
            }
    structure.units = tuple(units)
    structure.receipt.update(units=len(units), hydrated_sections=sum(len(d.parents) for d in documents.values()))
    return structure


def recheck_structural_row(row, entry, retrieval):
    """Terminal same-call check for hydrated rows (not a serialized capability).

    Legacy native-rank finalization only accepts unexpanded windows. Callers of
    this recipe can use this checker plus ordinary projection/source-gateway
    validation instead. Returns a receipt, or raises StructuralContextError.
    """
    source = entry.get("source")
    seed = entry.get("structural_native_candidate")
    if (entry.get("structural_recipe") not in {STRUCTURAL_RECIPE, EVIDENCE_STRUCTURAL_RECIPE, REFERENCE_STRUCTURAL_RECIPE} or
            not isinstance(source, dict) or not isinstance(seed, dict)):
        raise StructuralContextError("Missing structural provenance")
    ref = source.get("_reference_evidence") or {}
    native_ref = seed.get("_reference_evidence") or {}
    if (_identity(source) != _identity(seed) or any(ref.get(k) != native_ref.get(k) for k in
            ("source", "member_binding", "project_doc_content_hash", "raw_document"))):
        raise StructuralContextError("Structural source identity changed")
    raw = native_ref.get("raw_document")
    if not isinstance(raw, str):
        raise StructuralContextError("Missing structural raw source")
    parents = parse_markdown_parents(raw, native_ref["source"]["document_id"])
    matching = [i for i, p in enumerate(parents) if
                (p.char_start, p.char_end) == (ref.get("char_start"), ref.get("char_end"))]
    if len(matching) != 1:
        raise StructuralContextError("Structural span is not a complete parser section")
    plan = retrieval.get("documentation_query_plan") or {}
    structure = StructuralUnits((), {}, {},
        str(plan.get("original_question") or retrieval.get("question") or ""),
        retrieval.get("project_identity"), {}, recipe=entry["structural_recipe"])
    doc = _Document(_identity(seed), native_ref["source"]["canonical_path"], raw, [seed], parents)
    checked_row, _ = _hydrate(doc, matching[0], structure)
    if any(row.get(key) != checked_row.get(key) for key in (
        "evidence_id", "snippet", "path_or_url", "project_identity", "line_start", "line_end",
        "authority", "scope", "version_binding", "instruction_trust", "content_sha256",
    )):
        raise StructuralContextError("Structural public source changed")
    return {"structural_recipe": structure.recipe, "status": "complete",
            "char_start": ref["char_start"], "char_end": ref["char_end"]}


def _closing(text, start, opening, closing):
    """Balanced delimiters, with no artificial nesting limit."""
    depth, index = 1, start + 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == opening:
            depth += 1
        elif text[index] == closing:
            depth -= 1
            if not depth:
                return index
        index += 1
    return None


def _destination(value):
    value = value.lstrip()
    if value.startswith("<") and ">" in value:
        return unescape(value[1:value.index(">")])
    return unescape(value.split()[0]) if value else ""


def _edges(syntax, definitions, *, report_assets=False):
    """Recognize explicit Markdown/HTML links; code was masked by the parser.

    Ordinary URLs without a fragment are not subtree dependencies. Reference
    definitions themselves are dependencies even when their URL has no fragment.
    """
    index = 0
    while index < len(syntax):
        if syntax[index] != "[":
            index += 1
            continue
        end = _closing(syntax, index, "[", "]")
        if end is None:
            index += 1
            continue
        label = syntax[index + 1:end]
        after = end + 1
        if syntax[after:after + 1] == "(":
            target_end = _closing(syntax, after, "(", ")")
            if target_end is not None:
                yield ("asset" if report_assets and index and syntax[index - 1] == "!" else "url"), _destination(syntax[after + 1:target_end])
                index = target_end + 1
                continue
        if syntax[after:after + 1] == "[":
            reference_end = _closing(syntax, after, "[", "]")
            if reference_end is not None:
                yield ("asset" if report_assets and index and syntax[index - 1] == "!" else "definition"), _label(syntax[after + 1:reference_end] or label)
                index = reference_end + 1
                continue
        if label.startswith("^"):
            yield "definition", _label(label)
        elif _label(label) in definitions:
            yield ("asset" if report_assets and index and syntax[index - 1] == "!" else "definition"), _label(label)
        elif report_assets:
            yield "unsupported", label
        index = end + 1
    for match in re.finditer(r"<(?:[A-Za-z][\w:-]*)\b[^>]*?\bhref\s*=\s*(['\"])(.*?)\1[^>]*>", syntax):
        yield "url", unescape(match[2])
    for match in re.finditer(r"<([^<>\s]+#[^<>\s]+)>", syntax):
        yield "url", match[1]
    if report_assets:
        for match in re.finditer(r"<(?:img|video|audio|source)\b[^>]*>", syntax, flags=re.I):
            yield "asset", match[0]
        for match in re.finditer(r"<((?:https?://|mailto:)[^<>\s]+)>", syntax):
            yield "url", match[1]
        for match in re.finditer(r"<[A-Za-z][^>]*\bhref\s*=\s*[^\s'\"][^>]*>", syntax):
            yield "unsupported", match[0]


def close_selection(structure, selected_ids, payload, snapshot, retrieval):
    """Close selected subtrees, introductions and explicit edges to a fixpoint.

    Return (public rows, bound snapshot, receipt). No network or new document
    authorization occurs here: cross-document targets must be in the checked
    same-call scope. An unavailable/ambiguous edge is an explicit dependency gap.
    """
    plan = retrieval.get("documentation_query_plan") or {}
    if (str(plan.get("original_question") or retrieval.get("question") or "") != structure.question
            or retrieval.get("project_identity") != structure.expected_project_identity):
        raise StructuralContextError("Structural request binding changed")
    reference_mode = structure.recipe == REFERENCE_STRUCTURAL_RECIPE
    wanted, queue, incomplete = set(), deque(), ([] if reference_mode else list(structure.receipt.get("incomplete_dependencies", ())))
    processed_edges = 0
    paths = defaultdict(list)
    for identity, doc in structure.documents.items():
        paths[doc.path].append(identity)

    def add(identity, index, subtree=False):
        doc = structure.documents[identity]
        indices = range(index, doc.subtrees[index]) if subtree else (index,)
        for current in indices:
            for item in (*doc.ancestors[current], current):
                key = (identity, item)
                if key not in wanted:
                    wanted.add(key)
                    queue.append(key)
            if current and doc.parents[0].level == 0 and (identity, 0) not in wanted:
                wanted.add((identity, 0))
                queue.append((identity, 0))

    def gap(doc, index, target, reason):
        item = {"reason_code": "incomplete_dependency", "path": doc.path,
                "char_start": doc.parents[index].char_start, "target": target, "reason": reason}
        if item not in incomplete:
            incomplete.append(item)

    selected = set(selected_ids)
    for unit_id in selected:
        if unit_id not in structure.metadata:
            raise ValueError("Unknown structural unit identity: " + str(unit_id))
        meta = structure.metadata[unit_id]
        add(meta["source_identity"], meta["section_index"], subtree=structure.recipe == STRUCTURAL_RECIPE)
    while queue:
        identity, index = queue.popleft()
        doc = structure.documents[identity]
        edges = deque(_edges(doc.syntax[index], doc.definitions, report_assets=reference_mode))
        seen_edges = set()
        while edges:
            kind, target = edges.popleft()
            if (kind, target) in seen_edges:
                continue
            seen_edges.add((kind, target))
            processed_edges += 1
            if kind == "asset":
                gap(doc, index, target, "unsupported_asset_dependency")
                continue
            if kind == "unsupported":
                gap(doc, index, target, "unsupported_reference_syntax")
                continue
            if kind == "definition":
                if reference_mode and not target:
                    gap(doc, index, target, "unsupported_definition_label")
                    continue
                matches = doc.definitions.get(target, ())
                if len(matches) != 1:
                    gap(doc, index, target, "missing_or_ambiguous_definition")
                    continue
                owner, destination = matches[0]
                add(identity, owner)
                if not target.startswith("^"):
                    edges.append(("url", _destination(destination)))
                continue
            try:
                url = urlsplit(target)
            except ValueError:
                gap(doc, index, target, "invalid_link_target")
                continue
            if not url.fragment and not reference_mode:
                continue
            if url.scheme or url.netloc or url.query:
                gap(doc, index, target, "target_not_in_checked_scope")
                continue
            path = (posixpath.normpath(posixpath.join(posixpath.dirname(doc.path), unquote(url.path)))
                    if url.path else doc.path)
            if reference_mode and (not target or "\\" in url.path or (url.path and not path.lower().endswith((".md", ".markdown")))):
                gap(doc, index, target, "unsupported_local_document_target")
                continue
            candidates = paths.get(path, ())
            if len(candidates) != 1:
                gap(doc, index, target, "target_not_in_checked_scope")
                continue
            other_id = candidates[0]
            other = structure.documents[other_id]
            # No crossing project/version/generation even if paths coincide.
            if (other.seeds[0]["_reference_evidence"]["source"]["scope"] !=
                    doc.seeds[0]["_reference_evidence"]["source"]["scope"]):
                gap(doc, index, target, "target_scope_mismatch")
                continue
            if reference_mode and not url.fragment:
                for target_index in range(len(other.parents)):
                    add(other_id, target_index)
                continue
            matches = set(other.anchors.get(unquote(url.fragment), ()))
            if len(matches) != 1:
                gap(doc, index, target, "missing_or_ambiguous_anchor")
                continue
            if structure.recipe == STRUCTURAL_RECIPE or reference_mode:
                add(other_id, next(iter(matches)), subtree=True)
    rows, bound = [], {}
    for identity, index in sorted(wanted, key=lambda key: (structure.documents[key[0]].path, key)):
        row, entry = _hydrate(structure.documents[identity], index, structure)
        rows.append(row)
        bound[row["evidence_id"]] = entry
    receipt = {**structure.receipt, "selected_units": len(selected), "delivered_spans": len(rows),
               "incomplete_dependencies": incomplete,
               "status": "incomplete_dependency" if incomplete else "complete"}
    if reference_mode:
        receipt.update(closure_complete=not incomplete, processed_dependency_edges=processed_edges,
                       coverage="unverified", dependency_rule="all_delivered_bodies_addressed_extent")
    return rows, bound, receipt

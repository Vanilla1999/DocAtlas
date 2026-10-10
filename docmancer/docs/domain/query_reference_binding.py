"""Pure occurrence-aware query reference resolution."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Literal, Sequence
import hashlib
import json
from pathlib import PurePosixPath
import re

from .query_terms import documentation_technical_anchors
Role = Literal["source_locator", "symbol_identity", "semantic_subject", "retrieval_anchor", "unresolved"]
ResolutionState = Literal["resolved", "ambiguous", "missing", "unresolved"]
@dataclass(frozen=True, slots=True)
class ScopeKey:
    project_id: str
    version: str
    snapshot_id: str
@dataclass(frozen=True, slots=True)
class CatalogSource:
    document_id: str
    scope: ScopeKey
    canonical_path: str
    content_sha256: str
@dataclass(frozen=True, slots=True)
class QueryMention:
    mention_id: str
    start: int
    end: int
    text: str
    syntax_role: Role
    explicit: bool
@dataclass(frozen=True, slots=True)
class ResolvedReference:
    mention: QueryMention
    role: Role
    state: ResolutionState
    source_ids: tuple[str, ...]
    reason: str
@dataclass(frozen=True, slots=True)
class ReferencePlan:
    question: str
    references: tuple[ResolvedReference, ...]
    scope: ScopeKey
    catalog_complete: bool


# Shared with the source catalog. Unknown extensions never create stem aliases.
DOCUMENT_SUFFIXES = frozenset({".md", ".mdx", ".rst", ".txt", ".adoc"})
_PATH = re.compile(
    r"(?<![\w/\\])(?:(?:[A-Za-z]:|~)?[/\\](?:[\w.-]+[/\\])*[\w.-]+|"
    r"(?:\.{1,2}[/\\])?(?:[\w.-]+[/\\])+[\w.-]+)"
)
_QUOTED = re.compile(r'`([^`\n]{1,160})`|"([^"\n]{1,160})"')
_DOCUMENT_NAME = re.compile(
    r"(?<![\w./\\-])\w[\w.-]*\.(?:" + "|".join(sorted(suffix[1:] for suffix in DOCUMENT_SUFFIXES))
    + r")(?![\w/\\-]|\.(?=\S))", re.I,
)


@lru_cache(maxsize=512)
def query_mentions(question: str) -> tuple[QueryMention, ...]:
    """Extract literal paths/quotes and technical spellings at original offsets.

    No surrounding natural language assigns roles or nominates actors. Bare
    capitalization remains unresolved, never a semantic subject.
    """
    spans: list[tuple[int, int, Role, bool]] = []

    def add(start: int, end: int, role: Role, explicit: bool) -> None:
        if start < end and not any(start < b and a < end for a, b, _, _ in spans):
            spans.append((start, end, role, explicit))

    for match in _QUOTED.finditer(question):
        start, end = match.span(1 if match[1] is not None else 2)
        value = question[start:end]
        suffix = PurePosixPath(value.replace("\\", "/")).suffix.casefold()
        path = suffix in DOCUMENT_SUFFIXES
        add(start, end, "source_locator" if path else "symbol_identity", True)
    for match in _PATH.finditer(question):
        value = match[0].rstrip(".:,")
        suffix = PurePosixPath(value.replace("\\", "/")).suffix.casefold()
        add(match.start(), match.start() + len(value),
             "source_locator" if suffix in DOCUMENT_SUFFIXES else "symbol_identity", True)
    for match in _DOCUMENT_NAME.finditer(question):
        add(*match.span(), "source_locator", True)
    for value in sorted(documentation_technical_anchors(question), key=lambda value: (-len(value), value)):
        for match in re.finditer(r"(?<!\w)" + re.escape(value) + r"(?!\w)", question):
            role = "symbol_identity" if any(c in value for c in "._/:+-") else "unresolved"
            add(*match.span(), role, role != "unresolved")
    query_id = hashlib.sha256(question.encode("utf-8")).hexdigest()
    return tuple(QueryMention(f"{query_id}:{a}:{b}", a, b, question[a:b], role, explicit)
                 for a, b, role, explicit in sorted(spans))


def normalize_reference_path(value: str) -> str:
    """Separator normalization, not case folding, traversal collapse or rebasing."""
    return value.replace("\\", "/").removeprefix("./")


def _source_ids(name: str, catalog: Sequence[CatalogSource], suffixes: frozenset[str]) -> tuple[str, ...]:
    requested = normalize_reference_path(name)
    if (requested.startswith(("/", "~/")) or ".." in requested.split("/")
            or re.match(r"^[A-Za-z]:", requested)):
        return ()
    paths = [(source.document_id, normalize_reference_path(source.canonical_path)) for source in catalog]
    tiers = [paths]
    if "/" not in requested:
        tiers.extend((
            [(identity, PurePosixPath(path).name) for identity, path in paths],
            [(identity, PurePosixPath(path).stem) for identity, path in paths
             if PurePosixPath(path).suffix.casefold() in suffixes],
        ))
    for casefold in (False, True):
        for tier in tiers:
            found = {identity for identity, alias in tier if
                     (alias.casefold() == requested.casefold() if casefold else alias == requested)}
            if found:
                return tuple(sorted(found))
    return ()



def document_statement_mentions(question: str) -> tuple[QueryMention, QueryMention] | None:
    """A closed filename nomination and one unchanged literal body identifier.

    Only the frame is case-insensitive. The whole filename label and identifier
    retain their exact spelling and original character coordinates. Catalog
    membership, source identity and useful body content are checked separately.
    """
    match = re.fullmatch(
        r"\s*(?i:what)[ \t]+(?i:does)[ \t]+(?i:the)[ \t]+"
        r"(?P<label>[^\W_]+(?: [^\W_]+)*)[ \t]+(?i:say)[ \t]+(?i:about)[ \t]+"
        r"(?P<literal>\w+)\?\s*", question,
    )
    if match is None:
        return None
    target = next((mention for mention in query_mentions(question)
                   if (mention.start, mention.end) == match.span("literal")
                   and mention.text == match["literal"] and mention.text.isidentifier()
                   and not mention.explicit and mention.syntax_role == "unresolved"), None)
    if target is None:
        return None
    start, end = match.span("label")
    digest = hashlib.sha256(question.encode("utf-8")).hexdigest()
    return QueryMention(f"{digest}:{start}:{end}", start, end, match["label"],
                        "source_locator", True), target


def _structural_filename_label(path: str, suffixes: frozenset[str]) -> str | None:
    """Whole case-preserving stem; only single ASCII separators can differ."""
    normalized = normalize_reference_path(path)
    if (not normalized or normalized.startswith(("/", "~/"))
        or any(part in {"", ".", ".."} for part in normalized.split("/"))
        or re.match(r"^[A-Za-z]:", normalized)):
        return None
    leaf = PurePosixPath(normalized)
    if leaf.suffix.casefold() not in suffixes:
        return None
    stem = leaf.stem
    if re.fullmatch(r"[^\W_]+(?:[-_ ][^\W_]+)*", stem) is None:
        return None
    return stem.replace("-", " ").replace("_", " ")


def _structural_source_ids(label: str, catalog: Sequence[CatalogSource],
                           suffixes: frozenset[str]) -> tuple[str, ...]:
    # Count catalog entries, not distinct IDs or ranked hits. A collision cannot
    # disappear through deduplication, a basename tier, or identical file bytes.
    return tuple(sorted(source.document_id for source in catalog
                        if _structural_filename_label(source.canonical_path, suffixes) == label))


def naming_catalog_inventory(catalog: Sequence[CatalogSource], *, scope: ScopeKey,
                             catalog_complete: bool) -> dict:
    """Snapshot-owned inventory only; no caller/chunk metadata nominates rows."""
    return {
        "schema_version": 1, "scope": asdict(scope), "complete": catalog_complete,
        "sources": [asdict(source) for source in sorted(
            catalog, key=lambda source: (source.canonical_path, source.document_id))],
    }


def naming_catalog_digest(inventory: dict) -> str:
    """Bind the full inventory to its prepared plan; a digest is not authority."""
    encoded = json.dumps(inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _checked_naming_catalog(plan: dict, evidence: dict, identity: dict) -> tuple[CatalogSource, ...] | None:
    inventory = evidence.get("naming_catalog")
    scope = identity.get("scope")
    if (not isinstance(inventory, dict)
        or set(inventory) != {"schema_version", "scope", "complete", "sources"}
        or type(inventory.get("schema_version")) is not int or inventory["schema_version"] != 1
        or inventory.get("complete") is not True or plan.get("catalog_complete") is not True
        or not isinstance(scope, dict) or set(scope) != {"project_id", "version", "snapshot_id"}
        or any(type(scope.get(key)) is not str for key in scope)
        or not scope["project_id"] or not scope["snapshot_id"]
        or inventory.get("scope") != scope or plan.get("scope") != scope):
        return None
    rows = inventory.get("sources")
    if not isinstance(rows, list):
        return None
    sources, identities, paths = [], set(), set()
    for row in rows:
        if (not isinstance(row, dict)
            or set(row) != {"document_id", "scope", "canonical_path", "content_sha256"}
            or not isinstance(row.get("scope"), dict) or row["scope"] != scope
            or any(type(row.get(key)) is not str or not row[key]
                   for key in ("document_id", "canonical_path", "content_sha256"))
            or re.fullmatch(r"[0-9a-f]{64}", row["content_sha256"]) is None):
            return None
        path = normalize_reference_path(row["canonical_path"])
        if (path.startswith(("/", "~/")) or re.match(r"^[A-Za-z]:", path)
            or any(part in {"", ".", ".."} for part in path.split("/"))
            or row["document_id"] in identities or path in paths):
            return None
        identities.add(row["document_id"])
        paths.add(path)
        sources.append(CatalogSource(row["document_id"], ScopeKey(**scope),
                                     row["canonical_path"], row["content_sha256"]))
    if (sum(asdict(source) == identity for source in sources) != 1
        or plan.get("naming_catalog_sha256") != naming_catalog_digest(inventory)):
        return None
    return tuple(sources)


def resolve_references(
    question: str, *, catalog: Sequence[CatalogSource], scope: ScopeKey,
    catalog_complete: bool = True, document_suffixes: frozenset[str] = DOCUMENT_SUFFIXES,
) -> ReferencePlan:
    """Link occurrences to a complete already-allowed snapshot, never top-k."""
    allowed = tuple(source for source in catalog if source.scope == scope)
    references = []
    statement = document_statement_mentions(question)
    mentions = query_mentions(question)
    if statement is not None:
        locator, _target = statement
        mentions = tuple(sorted(
            (locator, *(mention for mention in mentions
                        if not (mention.start < locator.end and locator.start < mention.end))),
            key=lambda mention: (mention.start, mention.end),
        ))
    for mention in mentions:
        if statement is not None and mention.mention_id == statement[0].mention_id:
            if catalog_complete is not True or not scope.project_id or not scope.snapshot_id:
                ids, state, reason = (), "unresolved", "incomplete_source_catalog"
            else:
                ids = _structural_source_ids(mention.text, allowed, document_suffixes)
                state = "resolved" if len(ids) == 1 else "ambiguous" if ids else "missing"
                reason = {"resolved": "unique_structural_catalog_source",
                          "ambiguous": "ambiguous_structural_source_locator",
                          "missing": "missing_structural_source_locator"}[state]
            references.append(ResolvedReference(mention, "source_locator", state, ids, reason))
            continue
        role = mention.syntax_role
        ids: tuple[str, ...] = ()
        state: ResolutionState = "resolved"
        reason = "explicit_reference_role"
        # A double-quoted simple stem is a literal catalog nomination. Backtick
        # symbols and qualified spellings retain symbol identity on collision;
        # explicit documentation paths/filenames already carry locator syntax.
        # Basename/stem/casefold tiers are path resolution, not topic aliases.
        quoted_stem = (
            mention.start > 0 and mention.end < len(question)
            and question[mention.start-1] == question[mention.end] == '"'
            and re.fullmatch(r"[\w-]+", mention.text) is not None
        )
        if role == "symbol_identity" and mention.explicit and quoted_stem:
            ids = _source_ids(mention.text, allowed, document_suffixes)
            if ids:
                role = "source_locator"
        if role == "source_locator":
            if not catalog_complete or not scope.project_id or not scope.snapshot_id:
                ids, state, reason = (), "unresolved", "incomplete_source_catalog"
            else:
                ids = _source_ids(mention.text, allowed, document_suffixes)
                state = "resolved" if len(ids) == 1 else "ambiguous" if ids else "missing"
                reason = {"resolved": "unique_catalog_source", "ambiguous": "ambiguous_source_locator", "missing": "missing_source_locator"}[state]
                if not mention.explicit and not ids:
                    role, state, reason = "unresolved", "unresolved", "unresolved_reference_role"
        elif role == "unresolved":
            state, reason = "unresolved", "unresolved_reference_role"
        references.append(ResolvedReference(mention, role, state, ids, reason))
    return ReferencePlan(question, tuple(references), scope, catalog_complete)


def reference_body_question(plan: dict) -> str:
    """Retain the original retrieval text; references are separate constraints."""
    return str(plan.get("question") or "")


def _valid_reference_plan(plan: dict, scope: dict) -> bool:
    if not isinstance(plan, dict) or plan.get("scope") != scope:
        return False
    question, references = plan.get("question"), plan.get("references")
    if not isinstance(question, str) or not isinstance(references, (list, tuple)):
        return False
    digest = hashlib.sha256(question.encode("utf-8")).hexdigest()
    for ref in references:
        if not isinstance(ref, dict) or not isinstance(ref.get("mention"), dict):
            return False
        mention = ref["mention"]
        if (type(ref.get("role")) is not str
            or ref["role"] not in {"source_locator", "symbol_identity", "semantic_subject", "retrieval_anchor", "unresolved"}
            or type(ref.get("state")) is not str
            or ref["state"] not in {"resolved", "ambiguous", "missing", "unresolved"}
            or type(ref.get("reason")) is not str
            or type(mention.get("explicit")) is not bool
            or not isinstance(ref.get("source_ids"), (list, tuple))
            or any(type(value) is not str for value in ref["source_ids"])):
            return False
        start, end = mention.get("start"), mention.get("end")
        if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(question)
            or question[start:end] != mention.get("text")
            or mention.get("mention_id") != f"{digest}:{start}:{end}"):
            return False
    return True


def prepare_reference_probe(probe, *, candidate, evidence_text: str):
    """Verify current source/occurrence against prepared snapshot; pure, no I/O.

    Serialized internal dictionaries are validated, never granted authority by
    their Python type or an incoming qualified/trusted flag. Trace bindings are
    recomputed; the application-owned raw source window supplies the evidence.
    """
    from .query_terms import documentation_query_terms, query_constraint_roles
    from .technical_tokens import technical_term_pattern
    result = dict(probe)
    result.pop("bound_subject_context", None)
    source = candidate or {}
    root = source.get("_reference_root_plan")
    if not isinstance(root, dict):
        if source.get("_reference_evidence") or probe.get("reference_bindings"):
            return result, "missing_reference_plan"
        return result, None  # existing strict local policy, no invented owner
    evidence = source.get("_reference_evidence")
    if not isinstance(evidence, dict) or evidence.get("schema_version") != 1:
        return result, "missing_source_reference_evidence"
    identity = evidence.get("source") or {}
    scope = identity.get("scope") or {}
    if not scope.get("project_id") or not scope.get("snapshot_id") or not _valid_reference_plan(root, scope):
        return result, "reference_scope_mismatch"
    for key in ("project_identity", "repository_identity"):
        if source.get(key) and source[key] != scope["project_id"]:
            return result, "reference_project_mismatch"
    if source.get("generation_id", scope["snapshot_id"]) != scope["snapshot_id"]:
        return result, "reference_snapshot_mismatch"
    if "resolved_version" in source and str(source.get("resolved_version") or "") != scope.get("version", ""):
        return result, "reference_version_mismatch"
    for key in ("path", "path_or_url", "project_doc_path", "source_path"):
        if source.get(key) and normalize_reference_path(str(source[key])) != normalize_reference_path(str(identity.get("canonical_path") or "")):
            return result, "reference_path_mismatch"
    file_snapshot_hash = str(evidence.get("project_doc_content_hash") or "").removeprefix("sha256:")
    for key in ("_source_snapshot_sha256", "project_doc_content_hash"):
        if source.get(key) and (
            not file_snapshot_hash
            or str(source[key]).removeprefix("sha256:") != file_snapshot_hash
        ):
            return result, "reference_content_mismatch"
    if (source.get("source_content_hash")
            and str(source["source_content_hash"]).removeprefix("sha256:")
                != identity.get("content_sha256")):
        return result, "reference_content_mismatch"
    start, end = evidence.get("char_start"), evidence.get("char_end")
    text = str(evidence.get("text") or "")
    if type(start) is not int or type(end) is not int or end-start != len(text):
        return result, "invalid_reference_window"
    span = (source["char_start"], source["char_end"]) if "char_start" in source and "char_end" in source else source.get("char_span") or ()
    if len(span) != 2 or any(type(pos) is not int for pos in span) or not start <= span[0] <= span[1] <= end:
        return result, "reference_window_mismatch"
    visible = evidence_text.strip()
    window = text[span[0]-start:span[1]-start]
    offset = window.find(visible)
    if not visible or offset < 0 or window.find(visible, offset+1) >= 0:
        return result, "reference_body_mismatch"
    visible_start = span[0] + offset
    plan = (source.get("_reference_plans") or {}).get(str(probe.get("query_text") or ""))
    if plan is not None and not _valid_reference_plan(plan, scope):
        return result, "reference_plan_mismatch"
    bindings = []
    seen = set()
    current_source = CatalogSource(
        str(identity.get("document_id") or ""),
        ScopeKey(str(scope.get("project_id") or ""), str(scope.get("version") or ""),
                 str(scope.get("snapshot_id") or "")),
        str(identity.get("canonical_path") or ""), str(identity.get("content_sha256") or ""),
    )
    for item in (root, plan):
        if item is None:
            continue
        statement = document_statement_mentions(item["question"])
        if statement is not None:
            catalog = _checked_naming_catalog(item, evidence, identity)
            if catalog is None:
                return result, "invalid_structural_source_catalog"
            expected = resolve_references(item["question"], catalog=catalog,
                                          scope=current_source.scope, catalog_complete=True)
            # A missing/rewritten source reference cannot downgrade a closed
            # filename request into an unconstrained body lookup.
            if len(item["references"]) != len(expected.references):
                return result, "structural_source_plan_mismatch"
            for actual_ref, expected_ref in zip(item["references"], expected.references):
                if (actual_ref["mention"] != asdict(expected_ref.mention)
                    or actual_ref["role"] != expected_ref.role
                    or actual_ref["state"] != expected_ref.state
                    or actual_ref["reason"] != expected_ref.reason
                    or tuple(actual_ref["source_ids"]) != expected_ref.source_ids):
                    return result, "structural_source_plan_mismatch"
        else:
            # Recheck existing literal syntax as well as the current path. A
            # forged old-style role cannot bypass the closed-frame verifier.
            expected = resolve_references(item["question"], catalog=(current_source,),
                                          scope=current_source.scope, catalog_complete=True)
        expected_locators = {ref.mention.mention_id: ref for ref in expected.references
                             if ref.role == "source_locator"}
        for ref in item["references"]:
            mention = ref["mention"]
            if mention["mention_id"] in seen or ref.get("role") != "source_locator":
                continue
            seen.add(mention["mention_id"])
            if ref.get("state") != "resolved":
                return result, str(ref.get("reason") or "unresolved_source_locator")
            if identity.get("document_id") not in ref.get("source_ids", ()):
                return result, "source_locator_mismatch"
            recomputed = expected_locators.get(mention["mention_id"])
            if (recomputed is None or recomputed.state != "resolved"
                or asdict(recomputed.mention) != mention
                or recomputed.source_ids != (current_source.document_id,)):
                return result, "source_locator_mismatch"
            binding = {"mention_id": mention["mention_id"], "role": "source_locator", "field": "path", **identity}
            if statement is not None:
                binding["syntax"] = "structural_filename"
            bindings.append(binding)
    if plan is not None:
        body_question = reference_body_question(plan)
        exact_plan = plan
        if result.get("mode") == "exact_path":
            body_question = reference_body_question(root)
            exact_plan = root
            result.pop("mode", None)
        roles = query_constraint_roles(body_question)
        # Only verified source-locator occurrences are path constraints rather
        # than body identities. Mask their coordinates for exact extraction;
        # original query/body text and separately mentioned symbols stay intact.
        exact_chars = list(body_question)
        bound_locator_ids = {binding["mention_id"] for binding in bindings}
        for ref in exact_plan.get("references") or ():
            mention = ref["mention"]
            if ref.get("role") == "source_locator" and mention["mention_id"] in bound_locator_ids:
                start, end = mention["start"], mention["end"]
                exact_chars[start:end] = " " * (end-start)
        body_exact = query_constraint_roles("".join(exact_chars)).hard_exact
        # Independent lookup coverage is query-local. Root source constraints
        # above remain mandatory, but a host facet need not repeat every root
        # symbol. Audited parent coverage still uses the existing parent terms.
        result.update(query_terms=list(documentation_query_terms(body_question)),
            exact_terms=list(body_exact), bound_subjects=list(roles.bound_subjects),
            retrieval_anchors=list(roles.retrieval_anchors),
            reference_body_query=body_question)
    from .source_subject_binding import prepared_owner_rejection
    owner_reason = prepared_owner_rejection(evidence)
    if owner_reason is not None:
        return result, owner_reason
    owner = evidence.get("owner") or {}
    owner_text = str(owner.get("text") or "")
    if (owner_text and type(owner.get("scope_start")) is int and type(owner.get("scope_end")) is int
        and owner["scope_start"] <= visible_start <= visible_start+len(visible) <= owner["scope_end"]
        and owner.get("char_end", 0)-owner.get("char_start", 0) == len(owner_text)):
        result["bound_subject_context"] = owner_text
    for ref in (plan or root).get("references") or ():
        role, mention = ref["role"], ref["mention"]
        if role not in {"symbol_identity", "semantic_subject"}:
            continue
        match = re.search(technical_term_pattern(mention["text"], exact=True), visible, re.I)
        field, origin = "body", visible_start
        if match is None and role == "semantic_subject" and result.get("bound_subject_context"):
            match = re.search(technical_term_pattern(mention["text"], exact=True), owner_text, re.I)
            field, origin = "heading", owner["char_start"]
        if match:
            bindings.append({"mention_id": mention["mention_id"], "role": role, "field": field, **identity,
                "char_start": origin+match.start(), "char_end": origin+match.end()})
    result.update(reference_bindings=bindings, reference_visible_span=[visible_start, visible_start+len(visible)])
    return result, None

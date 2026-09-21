"""Pure occurrence-aware query reference resolution."""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, Sequence
import hashlib
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
_NAME = r'(?:`(?P<quoted>[^`\n]{1,160})`|"(?P<double>[^"\n]{1,160})"|(?P<bare>[\w~./\\:+-]+))'
_CONTEXT = re.compile(
    r"(?<!\w)(?P<context>file|document|файл(?:е|а|у|ом)?|документ(?:е|а|у|ом)?|"
    r"constant|class|function|method|symbol|flag|key|констант(?:а|ы|е|у)|"
    r"класс(?:а|е)?|функци(?:я|и|ю)|метод(?:а|е)?|library|package|"
    r"библиотек(?:а|и|е|у)|пакет(?:а|е)?)(?!\w)\s+" + _NAME, re.I,
)
_SOURCE_CONTEXT = re.compile(r"(?:file|document|файл\w*|документ\w*)\Z", re.I)
_SUBJECT_CONTEXT = re.compile(r"(?:library|package|библиотек\w*|пакет\w*)\Z", re.I)
_SOURCE_PREFIX = re.compile(
    r"(?:\b(?:in|from|within|according\s+to|read|open|for|about|and|or|в|из|согласно)\s+(?:the\s+)?|^)$", re.I,
)
_WEAK_SOURCE = re.compile(r"(?<!\w)(?:in|from|according\s+to)\s+the\s+" + _NAME, re.I)
_NAMED_DOCUMENT_SOURCE = re.compile(r"(?<!\w)according\s+to\s+(?:the\s+)?" + _NAME, re.I)
_PATH = re.compile(r"(?<![\w/\\])(?:~?[/\\]|\.{1,2}[/\\])?(?:[\w.-]+[/\\])+[\w.-]+")
_QUOTED = re.compile(r'`([^`\n]{1,160})`|"([^"\n]{1,160})"')
# Grammatical anaphora/determiners are not newly named entities. A concrete
# antecedent can still be retained by the existing exact/need lineage policy.
_NON_ENTITY_ACTORS = frozenset({"a", "an", "the", "it", "its", "they", "their", "our", "your", "this", "that", "these", "those", "we", "you", "i"})
_PREDICATES = frozenset({"is", "are", "was", "were", "does", "do", "returns", "return", "raises", "raise", "has", "have"})
_ROLE_WORDS = frozenset({"file", "document", "constant", "class", "library", "package", "function", "method"})
# A bare preposition followed by its complement describes a role, not a name.
# Quoted names and technical spellings (for.run, with_retries) do not match.
_ROLE_COMPLEMENT = re.compile(r"(?:for|with|without|in|from|для|с|без|в|из)\s+\S", re.I)


def _name_span(match: re.Match[str]) -> tuple[int, int]:
    group = next(key for key in ("quoted", "double", "bare") if match.group(key) is not None)
    start, end = match.span(group)
    if group == "bare":
        end = start + len(match[group].rstrip(".:,"))
    return start, end


@lru_cache(maxsize=512)
def query_mentions(question: str) -> tuple[QueryMention, ...]:
    """Extract only declared grammatical relations; preserve original offsets.

    Role priority is contextual role > full path/quoted identity > lexical
    nomination. Bare capitalization nominates an unresolved occurrence, never
    a semantic subject. Unsupported natural-language forms remain unresolved.
    """
    spans: list[tuple[int, int, Role, bool]] = []

    def add(start: int, end: int, role: Role, explicit: bool) -> None:
        if start < end and not any(start < b and a < end for a, b, _, _ in spans):
            spans.append((start, end, role, explicit))

    for match in _CONTEXT.finditer(question):
        start, end = _name_span(match)
        if match.group("bare") and question[start:end].casefold() in _PREDICATES:
            continue
        if match.group("bare") and _ROLE_COMPLEMENT.match(question, start):
            continue
        if _SOURCE_CONTEXT.fullmatch(match["context"]):
            literal = match.group("quoted") is not None or match.group("double") is not None
            if not (literal or _SOURCE_PREFIX.search(question[:match.start()])):
                continue  # "document headings" is not a named document.
            role: Role = "source_locator"
        elif _SUBJECT_CONTEXT.fullmatch(match["context"]):
            role = "semantic_subject"
        else:
            role = "symbol_identity"
        add(start, end, role, True)
    # Declared actor relations also recognize lowercase names; bare casing is
    # never sufficient and ordinary noun phrases are not promoted to entities.
    for pattern in (r"\bif\s+(?:one|a|an|any)\s+(?P<actor>[\w.-]+)\s+(?:function|task|method)\b",
                    r"\b(?:what\s+is|what\s+are)\s+(?P<actor>[\w.-]+)\s+default\b",
                    r"\b(?:when\s+do|when\s+does)\s+(?P<actor>[\w.-]+)\s"):
        for match in re.finditer(pattern, question, re.I):
            if match["actor"].casefold() not in _NON_ENTITY_ACTORS and not any(c in match["actor"] for c in "._/\\:+-"):
                add(*match.span("actor"), "semantic_subject", True)
    # "According to Guide.md" names a document only when the spelling itself
    # has a supported documentation suffix. Bare "in HTTPX" stays ambiguous.
    for match in _NAMED_DOCUMENT_SOURCE.finditer(question):
        start, end = _name_span(match)
        if PurePosixPath(question[start:end].replace("\\", "/")).suffix.casefold() in DOCUMENT_SUFFIXES:
            add(start, end, "source_locator", False)
    for match in _WEAK_SOURCE.finditer(question):
        start, end = _name_span(match)
        if question[start:end].casefold() not in _ROLE_WORDS:
            add(start, end, "source_locator", False)
    for match in _QUOTED.finditer(question):
        start, end = match.span(1 if match[1] is not None else 2)
        value = question[start:end]
        suffix = PurePosixPath(value.replace("\\", "/")).suffix.casefold()
        path = ("/" in value or "\\" in value) and suffix in DOCUMENT_SUFFIXES
        add(start, end, "source_locator" if path else "symbol_identity", True)
    for match in _PATH.finditer(question):
        value = match[0].rstrip(".:,")
        suffix = PurePosixPath(value.replace("\\", "/")).suffix.casefold()
        add(match.start(), match.start() + len(value),
            "source_locator" if suffix in DOCUMENT_SUFFIXES else "symbol_identity", True)
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


def resolve_references(
    question: str, *, catalog: Sequence[CatalogSource], scope: ScopeKey,
    catalog_complete: bool = True, document_suffixes: frozenset[str] = DOCUMENT_SUFFIXES,
) -> ReferencePlan:
    """Link occurrences to a complete already-allowed snapshot, never top-k."""
    allowed = tuple(source for source in catalog if source.scope == scope)
    references = []
    for mention in query_mentions(question):
        role = mention.syntax_role
        ids: tuple[str, ...] = ()
        state: ResolutionState = "resolved"
        reason = "explicit_reference_role"
        if role == "source_locator":
            if not catalog_complete or not scope.project_id or not scope.snapshot_id:
                state, reason = "unresolved", "incomplete_source_catalog"
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
    """Remove locator occurrences only from the body probe, not the source plan."""
    question = str(plan.get("question") or "")
    chars = list(question)
    for reference in plan.get("references") or ():
        if reference.get("role") != "source_locator":
            continue
        mention = reference.get("mention") or {}
        start, end = mention.get("start"), mention.get("end")
        if type(start) is not int or type(end) is not int or question[start:end] != mention.get("text"):
            continue
        prefix = re.search(r"(?:(?:in|from|within|according\s+to|в|из|согласно)\s+)?(?:the\s+)?(?:file|document|файл\w*|документ\w*)\s+[`\"]?$", question[:start], re.I)
        if prefix:
            start = prefix.start()
        elif start and question[start-1] in '`"':
            start -= 1
        if end < len(question) and question[end] in '`"':
            end += 1
        chars[start:end] = " " * (end-start)
    return "".join(chars)


def _valid_reference_plan(plan: dict, scope: dict) -> bool:
    if not isinstance(plan, dict) or plan.get("scope") != scope:
        return False
    question = str(plan.get("question") or "")
    digest = hashlib.sha256(question.encode("utf-8")).hexdigest()
    for ref in plan.get("references") or ():
        mention = ref.get("mention") or {}
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
    from dataclasses import asdict
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
    for key in ("_source_snapshot_sha256", "project_doc_content_hash", "source_content_hash"):
        if source.get(key) and str(source[key]).removeprefix("sha256:") != identity.get("content_sha256"):
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
    for item in (root, plan):
        for ref in (item or {}).get("references") or ():
            mention = ref["mention"]
            if mention["mention_id"] in seen or ref.get("role") != "source_locator":
                continue
            seen.add(mention["mention_id"])
            if ref.get("state") != "resolved":
                return result, str(ref.get("reason") or "unresolved_source_locator")
            if identity.get("document_id") not in ref.get("source_ids", ()):
                return result, "source_locator_mismatch"
            bindings.append({"mention_id": mention["mention_id"], "role": "source_locator", "field": "path", **identity})
    if plan is not None:
        body_question = reference_body_question(plan)
        if result.get("mode") == "exact_path":
            body_question = reference_body_question(root)
            result.pop("mode", None)
        roles = query_constraint_roles(body_question)
        original_roles = query_constraint_roles(reference_body_question(root))
        # Independent lookup coverage is query-local. Root source constraints
        # above remain mandatory, but a host facet need not repeat every root
        # symbol. Audited parent coverage still uses the existing parent terms.
        source_only_names = {ref["mention"]["text"].casefold() for ref in root["references"]
            if ref["role"] == "source_locator"} - set(original_roles.hard_exact) - set(original_roles.bound_subjects)
        parent_terms = [term for term in result.get("parent_exact_terms", ())
            if term.casefold() not in source_only_names]
        result.update(query_terms=list(documentation_query_terms(body_question)),
            exact_terms=list(roles.hard_exact), bound_subjects=list(roles.bound_subjects),
            parent_exact_terms=parent_terms, retrieval_anchors=list(roles.retrieval_anchors),
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

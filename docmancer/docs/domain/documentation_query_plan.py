"""Retrieval-only query plan that never authorizes an answer or edit."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from docmancer.docs.domain.question_frame_core import split_question_clauses
from docmancer.docs.domain.question_plan import retrieval_needs
from docmancer.docs.domain.question_component_rewrite import rewrite_component
from docmancer.docs.domain.question_semantic_frames import match_comparison_frame
from docmancer.docs.domain.project_retrieval_intent import (
    build_project_retrieval_aliases,
    project_retrieval_disposition,
)
from docmancer.docs.domain.query_terms import (
    documentation_exact_terms,
    documentation_query_terms,
    documentation_technical_anchors,
    is_exact_technical_token,
    query_constraint_roles,
    supplemental_query_is_useful,
)
from docmancer.docs.domain.technical_terms import extract_technical_terms


QueryRelation = Literal["direct", "audited_rewrite", "host_lookup", "exact_anchor"]


@dataclass(frozen=True, slots=True)
class DocumentationLookup:
    query_id: str
    text: str
    origin: str
    coverage_required: bool = True
    facet_id: str | None = None
    requirement_id: str | None = None
    relation: QueryRelation = "direct"
    public_parent_query_id: str | None = None
    preferred_catalog_roles: tuple[str, ...] = ()
    forbidden_catalog_roles: tuple[str, ...] = ()
    forbidden_evidence_terms: tuple[str, ...] = ()
    parent_exact_terms: tuple[str, ...] = ()
    component_rewrite_audit: tuple[str, int, int, str] | None = None
    need_subject: str | None = None
    need_relation: str | None = None
    need_context: str | None = None

    def __post_init__(self) -> None:
        if self.relation not in {"direct", "audited_rewrite", "host_lookup", "exact_anchor"}:
            raise ValueError(f"unsupported documentation query relation: {self.relation}")
        if self.relation == "audited_rewrite" and not self.public_parent_query_id:
            raise ValueError("audited rewrites require a public parent query")
        if self.relation in {"direct", "host_lookup"} and self.public_parent_query_id:
            raise ValueError(f"{self.relation} queries cannot derive parent coverage")
        for field in (
            "preferred_catalog_roles", "forbidden_catalog_roles", "forbidden_evidence_terms",
            "parent_exact_terms",
        ):
            object.__setattr__(self, field, tuple(getattr(self, field)))


@dataclass(frozen=True, slots=True)
class DocumentationQueryPlan:
    original_question: str
    queries: tuple[DocumentationLookup, ...]
    explicit_paths: tuple[str, ...] = ()
    unresolved_parts: tuple[str, ...] = ()
    component_contract: tuple[dict[str, object], ...] = ()
    component_scope_complete: bool = True
    schema_version: str = "documentation-query-plan-v2"

    def as_payload(self) -> dict[str, object]:
        public_origins = {"original", "host_lookup", "exact_anchor", "exact_path"}
        return {
            "schema_version": self.schema_version,
            "original_question": self.original_question,
            "query_ids": [query.query_id for query in self.queries],
            "required_query_ids": [
                query.query_id for query in self.queries if query.coverage_required
            ],
            "public_query_ids": [
                query.query_id for query in self.queries
                if query.origin in public_origins
            ],
            "queries": [
                {
                    "query_id": query.query_id,
                    "text": query.text,
                    "origin": query.origin,
                    "coverage_required": query.coverage_required,
                    "facet_id": query.facet_id,
                    "requirement_id": query.requirement_id,
                    "relation": query.relation,
                    "public_parent_query_id": query.public_parent_query_id,
                    "preferred_catalog_roles": list(query.preferred_catalog_roles),
                    "forbidden_catalog_roles": list(query.forbidden_catalog_roles),
                    "forbidden_evidence_terms": list(query.forbidden_evidence_terms),
                    "parent_exact_terms": list(query.parent_exact_terms),
                    "need_subject": query.need_subject,
                    "need_relation": query.need_relation,
                    "need_context": query.need_context,
                    **({"component_rewrite_audit": {
                        "rule": query.component_rewrite_audit[0],
                        "query_span_start": query.component_rewrite_audit[1],
                        "query_span_end": query.component_rewrite_audit[2],
                        "query_span_text": query.component_rewrite_audit[3],
                    }} if query.component_rewrite_audit else {}),
                }
                for query in self.queries
            ],
            "explicit_paths": list(self.explicit_paths),
            "unresolved_parts": list(self.unresolved_parts),
            "_component_contract": [dict(item) for item in self.component_contract],
            "component_scope_complete": self.component_scope_complete,
        }


# Audited rewrites may derive public-parent coverage. Unlike optional search
# aliases, they must consume a complete reviewed relation, not a bag of stems.
_REQUEST_BOUNDARY = r"(?:the )?(?:documentation )?request boundary"
_HOST_BOUNDARY_LOOKUP_RE = re.compile(
    r"(?:"
    r"(?:what|which)(?: (?:inputs?|arguments?))? (?:does|can) "
    + _REQUEST_BOUNDARY + r" accept|"
    r"(?:what|which) (?:inputs?|arguments?) (?:are|can be) accepted (?:by|at) "
    + _REQUEST_BOUNDARY + r")[?!.]?", re.I,
)
_HOST_SELECTION_LOOKUP_RE = re.compile(
    r"(?:"
    r"how (?:do|can) (?:the )?retrieved (?:chunks|candidates) become selected (?:visible )?sources|"
    r"how (?:are|can) (?:the )?retrieved (?:chunks|candidates) (?:be )?selected as (?:visible )?sources|"
    r"how (?:does|can) (?:the )?retrieval(?: (?:process|pipeline))? select (?:visible )?(?:source )?(?:chunks|candidates|sources)"
    r")[?!.]?", re.I,
)


_HOST_NEGATION_RE = re.compile(
    r"\b(?:not|never|no|cannot|can't|can’t|won't|won’t|doesn't|doesn’t|"
    r"does\s+not|do\s+not|did\s+not|must\s+not|should\s+not)\b", re.I,
)
_HOST_REWRITE_QUALIFIER_RE = re.compile(
    r"\b(?:except|only|without|avoid(?:ed|ing|s)?|outdated|archive|archived|"
    r"previously|legacy|conditional|conditionally|another|different)\b|\baudit\s+log\b",
    re.I,
)


_UNVERIFIED_PREMISE_RE = re.compile(
    r"\b(?:unknown|imaginary|hypothetical|fictitious|nonexistent|made[- ]?up|"
    r"неизвестн\w*|воображаем\w*|гипотетич\w*|несуществующ\w*)\b", re.I,
)
_NOVEL_TOPIC_QUALIFIER_RE = re.compile(
    r"(?:\bfor\s+(?:the\s+)?[a-z][a-z-]+\s+[a-z][a-z-]+|"
    r"\band\s+the\s+(?:[a-z][a-z-]+\s+){1,3}(?:subsystem|system|module)|"
    r"\bдля\s+(?!кажд\w*\s|эт\w*\s|мо\w*\s|ваш\w*\s|сво\w*\s)[а-яё][а-яё-]+\s+[а-яё][а-яё-]+)", re.I,
)
_ORIGINAL_RETRIEVAL_INTENTS = frozenset({
    "product_overview", "project_architecture", "retrieval_pipeline",
    "project_docs_sync", "troubleshooting", "index_cleanup",
    "project_storage", "index_chunking", "evidence_selection",
    "offline_usage", "docs_mcp_public_tools",
    "getting_started", "contributor_start", "docs_mcp_workflow",
    "project_docs_configuration", "testing_contribution",
})
_HOST_AUDITED_RETRIEVAL_INTENTS = frozenset({
    "testing_contribution", "index_chunking", "evidence_selection",
})
_CONDITIONAL_SURFACE_RE = re.compile(r"\b(?:if|when|unless|если|когда)\b", re.I)


def _can_derive_original_from_intent(question: str, aliases: tuple[object, ...]) -> bool:
    """Audit a single reviewed retrieval intent without changing the public question."""
    intent_ids = {getattr(alias, "intent_id", None) for alias in aliases}
    if not aliases or len(intent_ids) != 1 or not intent_ids <= _ORIGINAL_RETRIEVAL_INTENTS:
        return False
    if (
        technical_anchors(question)
        or _HOST_NEGATION_RE.search(question)
        or _UNVERIFIED_PREMISE_RE.search(question)
        or _NOVEL_TOPIC_QUALIFIER_RE.search(question)
        or _CONDITIONAL_SURFACE_RE.search(question)
    ):
        return False
    return all(bool(getattr(alias, "force_context_only", False)) for alias in aliases)



_REVIEWED_CONDITIONAL_TROUBLESHOOTING_RE = re.compile(
    r"(?:"
    r"(?:what\s+should\s+i\s+check|what\s+do\s+i\s+check|how\s+(?:do|should)\s+i\s+troubleshoot)"
    r"\s*,?\s*(?:if|when)\s+(?:(?:the|my|project|repository)\s+){0,3}"
    r"documentation\s+(?:is\s+)?(?:stale|outdated)\s+(?:or|and)\s+"
    r"(?:nothing(?:\s+is)?\s+found|no\s+results(?:\s+are)?\s+found|search\s+returns\s+no\s+results)"
    r"|(?:что\s+проверить|как\s+диагностировать)\s*,?\s*(?:если|когда)\s+"
    r"(?:(?:проектн\w*|репозиторн\w*)\s+)?документац\w*\s+устар\w*\s+"
    r"(?:или|и)\s+(?:ничего\s+не\s+находится|ничего\s+не\s+найдено|нет\s+результатов)"
    r")\s*[?!.]*\s*$",
    re.I,
)


def _reviewed_conditional_troubleshooting_frame(question: str) -> bool:
    return _REVIEWED_CONDITIONAL_TROUBLESHOOTING_RE.fullmatch(question) is not None


def _host_lookup_can_derive_original(
    original_question: str, lookup_text: str,
) -> bool:
    """Audit only checked meanings or reviewed single-intent rewrites."""
    from .admission_meaning import questions_have_same_supported_meaning
    if questions_have_same_supported_meaning(original_question, lookup_text):
        return True
    original_aliases = build_project_retrieval_aliases(original_question)
    lookup_aliases = build_project_retrieval_aliases(lookup_text)
    original_intents = {alias.intent_id for alias in original_aliases}
    conditional_troubleshooting = (
        _reviewed_conditional_troubleshooting_frame(original_question)
        and original_intents == {"troubleshooting"}
        and bool(original_aliases)
        and all(alias.force_context_only for alias in original_aliases)
        and not technical_anchors(original_question)
        and not _HOST_NEGATION_RE.search(original_question)
        and not _UNVERIFIED_PREMISE_RE.search(original_question)
        and not _NOVEL_TOPIC_QUALIFIER_RE.search(original_question)
    )
    if not (
        _can_derive_original_from_intent(original_question, original_aliases)
        or conditional_troubleshooting
    ):
        return False
    if _HOST_REWRITE_QUALIFIER_RE.search(lookup_text):
        return False
    if _CONDITIONAL_SURFACE_RE.search(lookup_text):
        return False
    lookup_intents = {alias.intent_id for alias in lookup_aliases}
    if len(lookup_intents) != 1 or lookup_intents != original_intents:
        return False
    if not lookup_aliases or not all(alias.force_context_only for alias in lookup_aliases):
        return False
    def canonical_texts(rows: tuple[object, ...]) -> set[str]:
        return {
            re.sub(r"^docatlas\s+", "", str(getattr(alias, "text", "")).casefold()).strip()
            for alias in rows if str(getattr(alias, "text", "")).strip()
        }
    return bool(canonical_texts(original_aliases) & canonical_texts(lookup_aliases))

def _audited_host_lookup_rewrites(
    original_question: str, lookup_text: str,
) -> tuple[str, ...]:
    """Return bounded domain-owned retrieval rewrites for one positive host facet.

    These rewrites may derive *retrieval* coverage for their explicit host parent;
    they never create proof obligations, answer support, or edit authority. Exact
    technical terms and negative relations remain verbatim and are never widened.
    """
    text = " ".join(str(lookup_text or "").strip().split())
    if (
        not text
        or technical_anchors(text)
        or _HOST_NEGATION_RE.search(text)
        or _HOST_REWRITE_QUALIFIER_RE.search(text)
    ):
        return ()
    original_anchors = {value.casefold() for value in technical_anchors(original_question)}
    if "get_docs_context" in original_anchors:
        if _HOST_BOUNDARY_LOOKUP_RE.fullmatch(text):
            return ("get_docs_context question project_path lookup_queries module_path scope",)
        if _HOST_SELECTION_LOOKUP_RE.fullmatch(text):
            return (
                "retrieval gateway filtered project chunks",
                "selection maximizes distinct visible query coverage",
            )
    aliases = build_project_retrieval_aliases(text)
    intent_ids = {alias.intent_id for alias in aliases}
    if len(intent_ids) != 1 or not intent_ids <= _HOST_AUDITED_RETRIEVAL_INTENTS:
        return ()
    return tuple(dict.fromkeys(alias.text for alias in aliases if alias.force_context_only))


def _subject_relation_groups(question: str) -> tuple[str, ...]:
    """Build bounded subject-bearing probes from relations already in the question.

    These are retrieval hypotheses only. They preserve user-provided subjects,
    conditions, and comparison axes without adding an expected outcome. The
    caller spends the existing optional-query slots on them before falling back
    to isolated lexical hints.
    """
    groups: list[str] = []

    def side_alternatives(value: str) -> tuple[str, ...]:
        """Expand one slash alternative while preserving the surrounding phrase."""
        match = re.search(r"\b([A-Za-z][A-Za-z0-9_-]*)\s*/\s*([A-Za-z][A-Za-z0-9_-]*)\b", value)
        if match is None:
            return (" ".join(value.split()),)
        prefix, suffix = value[:match.start()], value[match.end():]
        return tuple(dict.fromkeys(
            " ".join(f"{prefix}{choice}{suffix}".split())
            for choice in match.group(1, 2)
        ))

    # Reuse the semantic comparison parser first. This covers surfaces such as
    # "How should X treat A compared with B?" without inventing answer-side
    # vocabulary. The cross-side probe can find an explicit contrast; the two
    # side/context probes can retrieve complementary evidence when the contract
    # is documented separately for each side.
    semantic_comparison = match_comparison_frame(question)
    if semantic_comparison is not None and semantic_comparison.context:
        left = " ".join(semantic_comparison.left.split())
        right = " ".join(semantic_comparison.right.split())
        context = " ".join(str(semantic_comparison.context or "").split())
        pair = f"{left} {right} different separate".strip()
        if supplemental_query_is_useful(pair):
            groups.append(pair[:500])
        for side in (left, right):
            value = " ".join(part for part in (side, context) if part).strip()
            if value and supplemental_query_is_useful(value):
                groups.append(value[:500])

    # Preserve the established axis-aware surface for "How do A and B differ".
    # It may add more specific probes; tuple de-duplication below keeps the
    # optional-query budget bounded.
    comparison = re.match(
        r"^\s*how\s+do\s+(.+?)\s+and\s+(.+?)\s+differ(?:\s+in\s+(.+?))?[?.!]*\s*$",
        question,
        re.I,
    )
    if comparison is not None:
        left, right, axis = (value.strip(" ,;?.!") if value else "" for value in comparison.groups())
        left_variants = side_alternatives(left)
        right_variants = side_alternatives(right)
        axis_parts = [
            part.strip(" ,;?.!")
            for part in re.split(r"\s+(?:and|or)\s+", axis, flags=re.I)
            if part.strip(" ,;?.!")
        ] if axis else []
        axis_text = " ".join(axis_parts)
        pair_index = 0
        for left_value in left_variants:
            for right_value in right_variants:
                # Keep two independent retrieval hypotheses inside the same
                # bounded slot budget: one relation-aware paraphrase and, when
                # slash alternatives exist, one plain lexical cross-side view.
                relation_suffix = " different separate" if pair_index == 0 else ""
                value = f"{left_value} {right_value}{relation_suffix}".strip()
                pair_index += 1
                if value and supplemental_query_is_useful(value):
                    groups.append(value[:500])
        for side in (left_variants[0], " ".join(re.sub(r"\s*/\s*", " ", right).split())):
            value = " ".join(part for part in (side, axis_text) if part).strip()
            if value and supplemental_query_is_useful(value):
                groups.append(value[:500])

    # Passive state alternatives are common in conditional questions. Preserve
    # the bounded subject phrase (not just its first noun) plus every user-named
    # state. This keeps "documentation needed ... not indexed" distinct from a
    # generic mention of already-indexed content.
    condition = re.search(r"\b(?:when|if)\s+(.+?)(?:[?.!]|$)", question, re.I)
    if condition is not None:
        value = condition.group(1).strip(" ,;?.!")
        state = re.match(
            r"(.+?)\s+(?:is|are|was|were|has\s+(?:not\s+)?been|have\s+(?:not\s+)?been)\s+"
            r"([A-Za-z][A-Za-z0-9_-]+)\s+(?:or|and)\s+([A-Za-z][A-Za-z0-9_-]+)(?:\s+yet)?$",
            value,
            re.I,
        )
        if state is not None:
            subject_terms = documentation_query_terms(state.group(1))
            subject = " ".join(subject_terms[:4])
            negated = bool(re.search(r"\bnot\b", value, re.I))
            for named_state in state.group(2, 3):
                probe = " ".join(part for part in (subject, "not" if negated else "", named_state) if part)
                if probe and supplemental_query_is_useful(probe):
                    groups.append(probe[:500])
        elif value and len(value.split()) >= 2 and supplemental_query_is_useful(value):
            groups.append(value[:500])

    return tuple(dict.fromkeys(groups))


def build_documentation_query_plan(
    question: str, *, lookup_queries: tuple[str, ...] = (), explicit_path: str | None = None,
    requirements: object | None = None,
) -> DocumentationQueryPlan:
    retrieval_aliases = build_project_retrieval_aliases(question)
    single_facet = len({alias.intent_id for alias in retrieval_aliases}) == 1
    trusted_original_policy = _can_derive_original_from_intent(question, retrieval_aliases)
    preferred_roles = tuple(dict.fromkeys(
        role for alias in retrieval_aliases for role in alias.preferred_catalog_roles
    )) if trusted_original_policy else ()
    forbidden_roles = tuple(dict.fromkeys(
        role for alias in retrieval_aliases for role in alias.forbidden_catalog_roles
    )) if trusted_original_policy else ()
    forbidden_evidence_terms = tuple(dict.fromkeys(
        term for alias in retrieval_aliases for term in alias.forbidden_evidence_terms
    )) if trusted_original_policy else ()
    question_roles = query_constraint_roles(question)
    parent_exact_terms = tuple(dict.fromkeys((*question_roles.hard_exact, *question_roles.bound_subjects)))
    force_context_only = (
        project_retrieval_disposition(question) == "broad_context"
        and any(alias.force_context_only for alias in retrieval_aliases)
    )
    queries = [DocumentationLookup(
        "query-original", question.strip(), "original",
        not force_context_only,
        relation="direct",
        preferred_catalog_roles=() if explicit_path else preferred_roles,
        forbidden_catalog_roles=() if explicit_path else forbidden_roles,
        forbidden_evidence_terms=() if explicit_path else forbidden_evidence_terms,
    )]
    from .admission_grammar import NEW_RELATIONS, parse_admission_frame
    supported_needs = (need for need in retrieval_needs(question) if (
        need.relation in {"default", "exception", "requirement", *NEW_RELATIONS}
        or (need.relation == "behavior" and (parse_admission_frame(need.query_span_text) is not None or re.search(
            r"\b(?:if|when)\b.+?\bis\s+(?:not\s+enabled|disabled|enabled)\b",
            " ".join(value for value in (need.context, need.query_span_text) if value),
            re.I,
        )))
    ))
    for index, need in enumerate(supported_needs, start=1):
        text = " ".join(value for value in (need.context, need.query_span_text) if value).strip()
        if need.subject and need.subject.casefold() not in text.casefold():
            text = f"{need.subject} {text}"
        if text:
            queries.append(DocumentationLookup(
                f"query-need-{index}", text, "retrieval_need", False,
                facet_id=f"retrieval-need:{need.need_id}", relation="host_lookup",
                need_subject=need.subject or None, need_relation=need.relation,
                need_context=need.context or None,
            ))
    seen = {query.text.casefold() for query in queries}

    def host_policies(text: str) -> dict[str, tuple[str, ...]]:
        aliases = build_project_retrieval_aliases(text)
        if not aliases and single_facet:
            aliases = retrieval_aliases
        one_facet = len({alias.intent_id for alias in aliases}) == 1
        return {
            field: tuple(dict.fromkeys(
                value for alias in aliases
                if one_facet or field == "preferred_catalog_roles"
                for value in getattr(alias, field)
            ))
            for field in ("preferred_catalog_roles", "forbidden_catalog_roles", "forbidden_evidence_terms")
        }

    requirement_hints = tuple(
        str(value).strip()
        for value in getattr(requirements, "retrieval_hints", ())
        if str(value).strip()
    )
    if explicit_path and explicit_path.casefold() not in seen:
        queries.append(DocumentationLookup(
            "query-path-1", explicit_path, "exact_path", False,
            relation="exact_anchor", public_parent_query_id="query-original",
        ))
        seen.add(explicit_path.casefold())
    for index, anchor in enumerate(technical_anchors(question), start=1):
        if anchor.casefold() in seen:
            continue
        queries.append(DocumentationLookup(
            f"query-anchor-{index}", anchor, "exact_anchor", False,
            relation="exact_anchor", public_parent_query_id="query-original",
        ))
        seen.add(anchor.casefold())
    # Preserve lexical recall for prose compounds without promoting them into
    # public exact-identity directions or deriving original-question coverage.
    lexical_slots = 12 - sum(query.origin == "exact_anchor" for query in queries)
    for index, term in enumerate(extract_technical_terms(question), start=1):
        if lexical_slots <= 0:
            break
        if (term.kind != "plain_term" or not is_exact_technical_token(term.raw)
                or term.raw.casefold() in seen):
            continue
        queries.append(DocumentationLookup(
            f"query-hint-lexical-{index}", term.raw, "lexical_topic", False,
            relation="host_lookup",
        ))
        seen.add(term.raw.casefold())
        lexical_slots -= 1
    host_rows: list[tuple[str, str]] = []
    for index, text in enumerate(lookup_queries[:5], start=1):
        cleaned = text.strip()
        # An exact repeat of the original adds no new direction or authority.
        if not cleaned or cleaned == question.strip():
            continue
        parent_query_id = f"query-lookup-{index}"
        derives_original = _host_lookup_can_derive_original(question, cleaned)
        queries.append(DocumentationLookup(
            parent_query_id, cleaned, "host_lookup", False,
            relation="audited_rewrite" if derives_original else "host_lookup",
            public_parent_query_id="query-original" if derives_original else None,
            parent_exact_terms=parent_exact_terms if derives_original else (),
            **host_policies(cleaned),
        ))
        host_rows.append((parent_query_id, cleaned))
        seen.add(cleaned.casefold())
    host_rewrite_count = 0
    for parent_query_id, cleaned in host_rows:
        policies = host_policies(cleaned)
        host_roles = query_constraint_roles(cleaned)
        host_parent_exact_terms = tuple(dict.fromkeys((*host_roles.hard_exact, *host_roles.bound_subjects)))
        for rewrite in _audited_host_lookup_rewrites(question, cleaned):
            if host_rewrite_count >= 6:
                break
            host_rewrite_count += 1
            queries.append(DocumentationLookup(
                f"query-host-rewrite-{host_rewrite_count}", rewrite, "canonical_intent", False,
                relation="audited_rewrite", public_parent_query_id=parent_query_id,
                preferred_catalog_roles=policies["preferred_catalog_roles"],
                forbidden_catalog_roles=policies["forbidden_catalog_roles"],
                forbidden_evidence_terms=policies["forbidden_evidence_terms"],
                parent_exact_terms=host_parent_exact_terms,
            ))
            seen.add(rewrite.casefold())
    for index, alias in enumerate(retrieval_aliases, start=1):
        # Topic overlap, even for one facet, is not a complete equivalence audit.
        equivalent = (
            alias.text.casefold() == question.strip().casefold()
            or _can_derive_original_from_intent(question, retrieval_aliases)
            or (
                alias.intent_id == "installation_verification"
                and alias.text.endswith("local installation setup verification getting started")
                and re.fullmatch(
                    r"как установить (?:docatlas|docmancer|проект) локально и проверить,? что он работает\??",
                    " ".join(question.casefold().split()),
                ) is not None
            )
        )
        queries.append(DocumentationLookup(
            f"query-intent-{index}", alias.text, "canonical_intent", False,
            (
                f"intent-context:{alias.intent_id}"
                if alias.force_context_only else f"intent:{alias.intent_id}"
            ),
            relation="audited_rewrite" if equivalent else "host_lookup",
            public_parent_query_id="query-original" if equivalent else None,
            preferred_catalog_roles=alias.preferred_catalog_roles,
            forbidden_catalog_roles=alias.forbidden_catalog_roles,
            forbidden_evidence_terms=alias.forbidden_evidence_terms,
            parent_exact_terms=parent_exact_terms,
        ))
        seen.add(alias.text.casefold())
    normalized = re.sub(r"[^a-z0-9]+", " ", question.casefold()).strip()
    concept_queries = (
        (
            "project docs configuration" in normalized,
            "docatlas.project-docs.yaml project docs catalog configuration",
        ),
        (
            "project answer contract" in normalized and "document" in normalized,
            "project answer contract documentation docs/mcp-docs-server.md",
        ),
        (
            "refresh" in normalized and bool({"documentation", "docs"} & set(normalized.split())),
            "sync_project_docs project documentation after file changes",
        ),
        (
            "configure" in normalized and bool({"documentation", "docs"} & set(normalized.split())),
            "docatlas.yaml project docs configuration",
        ),
    )
    requirement_concepts = tuple(
        str(value).strip()
        for value in getattr(requirements, "concept_queries", ())
        if str(value).strip()
    )
    # Keep a subject-bearing raw clause together instead of spending all four
    # slots on the first individual hints. This adds no guessed action/fact.
    clause_groups = []
    for clause in split_question_clauses(question):
        text = clause.strip()
        if not text or len(text) > 500 or text.casefold() in seen:
            continue
        present_hints = [hint for hint in requirement_hints
            if supplemental_query_is_useful(hint)
            and re.search(r"(?<![\w.])" + re.escape(hint) + r"(?![\w.])", text, re.I)]
        if len(present_hints) >= 2:
            clause_groups.append(text)
    relation_groups = _subject_relation_groups(question)
    optional_queries = [
        # Relation groups are optional canonical search hypotheses so they can
        # contribute useful broad context without deriving public coverage.
        *((text, "canonical_intent") for text in relation_groups),
        *((text, "retrieval_hint") for text in clause_groups),
        *((text, "concept_alias") for applies, text in concept_queries if applies),
        *((text, "concept_alias") for text in requirement_concepts),
        *((text, "retrieval_hint") for text in requirement_hints),
    ]
    proof_obligations = getattr(requirements, "proof_obligations", None)
    if proof_obligations is None:
        proof_obligations = tuple(
            obligation for requirement in getattr(requirements, "requirements", ())
            if (obligation := requirement.as_proof_obligation()) is not None
        )
    optional_count = 0
    for obligation in proof_obligations:
        start, end = getattr(obligation, "query_span_start", None), getattr(obligation, "query_span_end", None)
        if start is None or end is None or not 0 <= start < end <= len(question):
            continue
        raw = question[start:end]
        rewritten = rewrite_component(raw)
        if rewritten is None or raw != getattr(obligation, "query_span_text", None) or optional_count >= 4:
            continue
        rule, facet, text = rewritten
        if any(getattr(obligation, field, None) != getattr(facet, field, None) for field in (
            "kind", "subject", "relation", "attribute", "item_kind", "response_mode",
            "target", "context", "expected_value", "cardinality", "value_kind",
            "subject_kind", "subject_aliases",
        )):
            continue
        optional_count += 1
        queries.append(DocumentationLookup(
            f"query-component-{optional_count}", text, "component_rewrite", False,
            requirement_id=obligation.obligation_id, relation="host_lookup",
            component_rewrite_audit=(rule, start, end, raw),
        ))
        seen.add(text.casefold())
    origin_counts = {"canonical_intent": 0, "concept_alias": 0, "retrieval_hint": 0}
    for text, origin in optional_queries:
        if (
            text.casefold() in seen
            or not supplemental_query_is_useful(text)
            or optional_count >= 4
        ):
            continue
        origin_counts[origin] += 1
        prefix = (
            "relation" if origin == "canonical_intent"
            else "concept" if origin == "concept_alias" else "hint"
        )
        queries.append(DocumentationLookup(
            f"query-{prefix}-{origin_counts[origin]}",
            text,
            origin,
            False,
            relation="host_lookup",
            **host_policies(text),
        ))
        optional_count += 1
        seen.add(text.casefold())
    return DocumentationQueryPlan(
        original_question=question,
        component_scope_complete=getattr(requirements, "component_scope_complete", False),
        queries=tuple(queries),
        explicit_paths=(explicit_path,) if explicit_path else (),
        unresolved_parts=tuple(
            str(value) for value in getattr(requirements, "unresolved_parts", ()) if str(value)
        ),
        component_contract=tuple(
            {
                key: value
                for key, value in {
                    "component_id": str(item.obligation_id),
                    "query_span_start": getattr(item, "query_span_start", None),
                    "query_span_end": getattr(item, "query_span_end", None),
                    "query_span_text": getattr(item, "query_span_text", None),
                    "obligation_kind": getattr(item, "kind", None),
                    "subject": getattr(item, "subject", None),
                    "subject_kind": getattr(item, "subject_kind", None),
                    "subject_aliases": getattr(item, "subject_aliases", ()),
                    "attribute": getattr(item, "attribute", None),
                    "relation": getattr(item, "relation", None),
                    "target": getattr(item, "target", None),
                    "value_kind": getattr(item, "value_kind", None),
                    "expected_value": getattr(item, "expected_value", None),
                    "item_kind": getattr(item, "item_kind", None),
                    "cardinality": getattr(item, "cardinality", None),
                    "response_mode": getattr(item, "response_mode", None),
                    "context": getattr(item, "context", None),
                    "lifecycle_intent": getattr(item, "lifecycle_intent", None),
                }.items()
                if value is not None
            }
            for item in proof_obligations
            if getattr(item, "mandatory", False)
        ),
    )


_SOURCE_RELATION_QUESTION_RE = re.compile(
    r"^\s*(?:does|do|is|are)\s+.+?\s+"
    r"(?:prove|proves|define|defines|document|documents|establish|establishes)\s+"
    r"(?P<claim>.+?)\s*[?.!]*$",
    re.I,
)

_STANDALONE_TECHNICAL_RE = re.compile(
    r"(?<![\w/])(?:~?/|\.{1,2}/)?(?:[A-Za-z0-9_.-]+/)*"
    r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+(?![\w/])"
    r"|\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"
)


def technical_anchors(question: str) -> tuple[str, ...]:
    values = [match.group(0) for match in _STANDALONE_TECHNICAL_RE.finditer(question)]
    values.extend(
        value for value in documentation_technical_anchors(question)
        if not any(value in existing for existing in values)
    )
    values.extend(
        term.raw for term in extract_technical_terms(question)
        if term.kind != "plain_term"
        and term.raw.casefold() not in {"docatlas", "docmancer"}
        and is_exact_technical_token(term.raw)
        and not any(term.raw in existing for existing in values)
    )
    return tuple(dict.fromkeys(value for value in values if value))[:12]


def _relation_claim_query(question: str) -> str | None:
    match = _SOURCE_RELATION_QUESTION_RE.match(question)
    if match is None:
        return None
    claim = match.group("claim").strip()
    return claim[:500] if claim else None


__all__ = [
    "DocumentationLookup",
    "DocumentationQueryPlan",
    "QueryRelation",
    "build_documentation_query_plan",
    "technical_anchors",
]

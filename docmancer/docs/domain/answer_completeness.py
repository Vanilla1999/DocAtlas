from __future__ import annotations

import re
from typing import Any

from docmancer.docs.domain.project_doc_ranking import normalize_doc_path

SCHEMA_VERSION = "answer-completeness-1.0"
_PROOF_SOURCE_CLASSES = {"project_doc", "dependency_doc", "source_evidence"}
_SOURCE_BACKED_PROOF_SOURCE_CLASSES = {"source_evidence", "test_evidence"}
_ABSENT_EVIDENCE_CLASSES = {"absent_in_source"}
_STRONG_AUTHORITIES = {"primary", "primary_source", "source_of_truth"}

_QUOTED_TERM_RE = re.compile(r"[\"'`“”‘’«»„]+([^\"'`“”‘’«»„]{2,120})[\"'`“”‘’«»„]+")
_CODE_TERM_RE = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+\b"
    r"|\b[a-z][a-z0-9]+(?:_[a-z0-9]+)+\b"
    r"|\b[A-Za-z][A-Za-z0-9_]*(?:Cubit|Service|Repository|Screen|Controller|Route|Router|Navigator|Module|Utils|Api|API)\b"
)
_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_\-]{3,}")
_RUSSIAN_WORD_RE = re.compile(r"[А-Яа-яЁёA-Za-z0-9_\-]+")
_FILE_HINT_RE = re.compile(r"\b(?:[\w.-]+/)*[\w.-]+\.(?:py|dart|js|jsx|ts|tsx|go|rs|java|kt|swift|md)\b")
_LAYER_TERMS = ["UI", "Cubit", "Service", "Repository", "API", "Screen", "Route", "Navigator"]
_STORY_MARKERS = [
    "button",
    "status",
    "toast",
    "screen",
    "flow",
    "story",
    "scenario",
    "reopen",
    "closed",
    "active",
    "request",
    "method",
    "api",
    "кноп",
    "статус",
    "toast",
    "тост",
    "экран",
    "сценар",
    "истор",
    "заяв",
    "закры",
    "актив",
    "вернут",
    "вернуть",
    "создат",
    "создать",
    "перевест",
    "чат",
    "пол",
    "назван",
    "обязатель",
]
_RUSSIAN_REQUIREMENT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bсоздать\s+нов(?:ый|ую|ое|ые|ого|ой|ым)?\s+[А-Яа-яЁё][А-Яа-яЁё0-9_\-]{2,}\b",
        r"\bна\s+основании\s+закрыт(?:ой|ая|ую|ые|ого|ом|ым)?\s+заявк[А-Яа-яЁё0-9_\-]*\b",
        r"\bотправить\s+название\s+заявк[А-Яа-яЁё0-9_\-]*\s+в\s+чат\b",
        r"\bперв(?:ое|ый|ая|ые|ого|ой|ую|ым)?\s+обязательн(?:ое|ый|ая|ые|ого|ой|ую|ым)?\s+пол[ея]\b",
        r"\bвернуть\s+в\s+работу\b",
        r"\bзакрыт(?:ой|ая|ую|ые|ого|ом|ым)?\s+заявк[А-Яа-яЁё0-9_\-]*\b",
        r"\bотправить\s+статус\s+[А-Яа-яЁё][А-Яа-яЁё0-9_\-]{2,}\b",
        r"\b(?:переместить|перевести)\s+(?:е[её]|заявк[А-Яа-яЁё0-9_\-]*)\s+в\s+[А-Яа-яЁё][А-Яа-яЁё0-9_\-]{2,}\b",
    ]
]
_RUSSIAN_REQUIREMENT_ACTIONS = [
    "создать",
    "отправить",
    "вернуть",
    "перевести",
    "переместить",
    "показать",
    "добавить",
    "открыть",
    "закрыть",
    "выбрать",
    "сохранить",
    "обновить",
    "удалить",
    "передать",
    "заполнить",
    "получить",
    "загрузить",
    "скачать",
    "подключить",
    "настроить",
    "проверить",
]
_RUSSIAN_ACTION_RE = re.compile(r"\b(?:" + "|".join(map(re.escape, _RUSSIAN_REQUIREMENT_ACTIONS)) + r")\b", re.IGNORECASE)
_RUSSIAN_ACTION_SPLIT_RE = re.compile(
    r"[,;?!.\n]+|\s+(?:чтобы|если|когда|после\s+того\s+как|перед\s+тем\s+как)\s+|"
    r"\s+(?:и|или)\s+(?=(?:" + "|".join(map(re.escape, _RUSSIAN_REQUIREMENT_ACTIONS)) + r")\b)",
    re.IGNORECASE,
)
_WEAK_STORY_SINGLETONS = {
    "создать",
    "отправить",
    "вернуть",
    "закрытой",
    "закрытая",
    "закрытую",
    "заявки",
    "заявка",
    "экран",
}
_STOPWORDS = {
    "about",
    "after",
    "before",
    "does",
    "from",
    "have",
    "help",
    "how",
    "into",
    "make",
    "need",
    "should",
    "that",
    "this",
    "what",
    "when",
    "where",
    "which",
    "with",
    "use",
    "using",
    "как",
    "где",
    "для",
    "и",
    "или",
    "надо",
    "нужно",
    "после",
    "при",
    "про",
    "что",
    "чтобы",
    "это",
    "этой",
    "его",
    "её",
    "она",
    "они",
    "реализовать",
    "сделать",
}
_GENERIC_RELEVANCE_WORDS = {
    "agent", "answer", "answers", "architecture", "change", "changes", "class", "classes",
    "codebase", "context", "constraint", "constraints", "doc", "docs", "documented",
    "documentation", "exact", "feature", "features", "file", "files", "function", "functions",
    "implementation", "implement", "implements", "module", "overview", "product", "project", "protocol",
    "repo", "repository", "source", "sources", "structure", "structured",
    "system", "technical", "term", "terms", "test", "tests", "usage", "workflow",
    "архитектура", "архитектуры", "архитектуре", "архитектур", "структура", "структуры", "структуре",
}


def extract_project_answer_requirements(question: str) -> list[str]:
    return _extract_requirements(question)


def extract_query_relevance_terms(question: str, intent: Any | None = None) -> list[str]:
    explicit = extract_project_answer_requirements(question)
    if explicit:
        return explicit
    high_signal = _extract_high_signal_query_terms(question)
    if high_signal:
        return high_signal
    if _skip_high_signal_relevance_gate(question, intent):
        return []
    return high_signal


def evaluate_project_answer_completeness(
    *,
    question: str,
    context_pack: list[dict[str, Any]],
    answer_available: bool,
    intent: Any,
) -> dict[str, Any]:
    """Return a backward-compatible completeness contract for get_project_context."""

    explicit_requirements = extract_project_answer_requirements(question)
    requirements = explicit_requirements or extract_query_relevance_terms(question, intent=intent)
    fallback_relevance_query = bool(requirements and not explicit_requirements)
    story_specific_query = bool(explicit_requirements) and _is_story_specific_query(question, intent, requirements)
    if story_specific_query:
        proof_context_pack = _source_backed_context_pack(context_pack)
    elif fallback_relevance_query:
        proof_context_pack = context_pack
    else:
        proof_context_pack = _proof_context_pack(context_pack)
    context_text = _context_text(proof_context_pack)
    coverage_by_requirement = [_requirement_coverage(term, context_pack=proof_context_pack, context_text=context_text) for term in requirements]
    matched_terms = [item["term"] for item in coverage_by_requirement if item["matched"]]
    missing_terms = [item["term"] for item in coverage_by_requirement if not item["matched"]]
    coverage_score = (len(matched_terms) / len(requirements)) if requirements else (1.0 if answer_available else 0.0)
    source_search_required = bool(answer_available and missing_terms and (story_specific_query or fallback_relevance_query))
    navigational_context = _has_navigational_context(context_pack)

    has_strong_evidence = any(
        item.get("source_class") in ("dependency_doc", "source_evidence")
        or item.get("authority") in _STRONG_AUTHORITIES
        for item in proof_context_pack
    )
    has_exact_dependency = any(
        item.get("source_class") == "dependency_doc"
        and item.get("docs_exactness") == "exact"
        for item in context_pack
    )
    all_terms_covered = not missing_terms
    reason_codes: list[str] = []

    if not answer_available:
        answer_type = "unavailable"
        status = "unavailable"
    elif source_search_required and navigational_context:
        answer_type = "partial_navigational"
        status = "partial"
    elif source_search_required:
        answer_type = "partial"
        status = "partial"
    elif all_terms_covered and (has_strong_evidence or has_exact_dependency):
        answer_type = "exact"
        status = "exact"
    elif all_terms_covered:
        answer_type = "partial_navigational"
        status = "partial"
        reason_codes.append("missing_strong_evidence_for_exact")
    else:
        answer_type = "partial"
        status = "partial"
        reason_codes.append("story_terms_missing_from_source_evidence")

    if not answer_available and "no_trusted_context" not in reason_codes:
        reason_codes.append("no_trusted_context")
    if source_search_required and "story_terms_missing_from_source_evidence" not in reason_codes:
        reason_codes.append("story_terms_missing_from_source_evidence")
    if fallback_relevance_query and missing_terms and "high_signal_query_terms_missing_from_context" not in reason_codes:
        reason_codes.append("high_signal_query_terms_missing_from_context")
    if navigational_context and "navigational_context_present" not in reason_codes:
        reason_codes.append("navigational_context_present")

    recommended_next_actions = []
    if source_search_required:
        recommended_next_actions.append(_source_search_action(missing_terms=missing_terms, context_pack=context_pack))

    completeness = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "answer_type": answer_type,
        "coverage_score": round(coverage_score, 3),
        "matched_terms": matched_terms,
        "missing_terms": missing_terms,
        "coverage_by_requirement": coverage_by_requirement,
        "source_search_required": source_search_required,
        "reason_codes": reason_codes,
    }
    return {
        "answer_type": answer_type,
        "answer_completeness": completeness,
        "recommended_next_actions": recommended_next_actions,
    }


def _skip_high_signal_relevance_gate(question: str, intent: Any | None) -> bool:
    q = _normalize_text(question)
    if not q:
        return True
    if getattr(intent, "broad", False):
        return True
    if getattr(intent, "wants_architecture", False):
        return True
    if getattr(intent, "wants_how_to", False):
        return True
    if getattr(intent, "wants_release_history", False):
        return True
    return any(
        phrase in q
        for phrase in (
            "project structure",
            "architecture overview",
            "repo overview",
            "codebase overview",
            "how is this project structured",
        )
    )


def _extract_high_signal_query_terms(question: str) -> list[str]:
    terms: list[str] = []
    for match in _WORD_RE.findall(question or ""):
        term = _clean_term(match)
        if not term:
            continue
        normalized = _normalize_text(term)
        if not normalized or normalized in _STOPWORDS or normalized in _GENERIC_RELEVANCE_WORDS:
            continue
        has_digit = any(ch.isdigit() for ch in term)
        has_symbolish_shape = "_" in term or "-" in term or "." in term
        has_camel_shape = bool(re.search(r"[a-zа-яё][A-ZА-ЯЁ]", term))
        if len(normalized) >= 5 or has_digit or has_symbolish_shape or has_camel_shape:
            terms.append(term)
    return _dedupe_terms(terms[:8])


def _extract_requirements(question: str) -> list[str]:
    quoted = [_clean_term(match) for match in _QUOTED_TERM_RE.findall(question or "")]
    terms = [term for term in quoted if term]
    for match in _CODE_TERM_RE.findall(question or ""):
        term = _clean_term(match)
        if term:
            terms.append(term)
    if terms and not quoted and _looks_like_story_requirement_question(question):
        terms.extend(_extract_explicit_story_phrases(question))
        terms.extend(_extract_russian_story_requirement_chunks(question))
    elif not terms:
        terms.extend(_extract_explicit_story_phrases(question))
    if not terms:
        terms.extend(_extract_russian_story_requirement_chunks(question))
    if not terms:
        for match in _WORD_RE.findall(question or ""):
            term = _clean_term(match)
            if not term:
                continue
            normalized = _normalize_text(term)
            if normalized in _STOPWORDS:
                continue
            if any(marker in normalized for marker in _STORY_MARKERS):
                terms.append(term)
    return _dedupe_terms(terms)


def _looks_like_story_requirement_question(question: str) -> bool:
    normalized = _normalize_text(question)
    return any(marker in normalized for marker in _STORY_MARKERS) or bool(_RUSSIAN_ACTION_RE.search(question or ""))


def _extract_explicit_story_phrases(question: str) -> list[str]:
    phrases: list[str] = []
    for tail in re.findall(r":\s*([^?!.\n]{2,500})", question or ""):
        for chunk in re.split(r"[/;,]", tail):
            for part in re.split(r"\s+и\s+(?=[A-ZА-ЯЁ])", chunk):
                phrase = _clean_term(part)
                if not phrase:
                    continue
                words = _WORD_RE.findall(phrase)
                if not 1 <= len(words) <= 8:
                    continue
                normalized = _normalize_text(phrase)
                if normalized in _STOPWORDS:
                    continue
                if not re.search(r"[A-ZА-ЯЁ]", phrase):
                    continue
                phrases.append(phrase)
    return _dedupe_terms(_drop_weak_story_singletons(phrases))


def _extract_russian_story_requirement_chunks(question: str) -> list[str]:
    if not re.search(r"[А-Яа-яЁё]", question or ""):
        return []
    phrases: list[str] = []
    for pattern in _RUSSIAN_REQUIREMENT_PATTERNS:
        for match in pattern.finditer(question or ""):
            _append_requirement_chunk(phrases, match.group(0))
    if len(phrases) >= 3:
        return _dedupe_terms(phrases)

    for clause in _RUSSIAN_ACTION_SPLIT_RE.split(question or ""):
        for match in _RUSSIAN_ACTION_RE.finditer(clause):
            tail = clause[match.start() :]
            words = _RUSSIAN_WORD_RE.findall(tail)
            if len(words) < 2:
                continue
            phrase_words = words[:7]
            while phrase_words and _normalize_text(phrase_words[-1]) in _STOPWORDS:
                phrase_words.pop()
            if 2 <= len(phrase_words) <= 7:
                _append_requirement_chunk(phrases, " ".join(phrase_words))

    for match in re.finditer(
        r"\b(?:[А-Яа-яЁё][А-Яа-яЁё0-9_\-]*\s+){1,3}(?:заявк[А-Яа-яЁё0-9_\-]*|запрос[А-Яа-яЁё0-9_\-]*|пол[ея]|кнопк[А-Яа-яЁё0-9_\-]*|экран[А-Яа-яЁё0-9_\-]*|чат[А-Яа-яЁё0-9_\-]*|статус[А-Яа-яЁё0-9_\-]*|ошибк[А-Яа-яЁё0-9_\-]*)\b",
        question or "",
        re.IGNORECASE,
    ):
        _append_requirement_chunk(phrases, match.group(0))

    return _dedupe_terms(_drop_weak_story_singletons(phrases))


def _append_requirement_chunk(phrases: list[str], value: str) -> None:
    phrase = _clean_term(value)
    if not phrase:
        return
    words = _RUSSIAN_WORD_RE.findall(phrase)
    if len(words) < 2 or len(words) > 8:
        return
    if _normalize_text(words[0]) in _STOPWORDS:
        return
    normalized = _normalize_text(phrase)
    if normalized in _STOPWORDS:
        return
    if not any(marker in normalized for marker in _STORY_MARKERS + _RUSSIAN_REQUIREMENT_ACTIONS):
        return
    phrases.append(phrase)


def _drop_weak_story_singletons(terms: list[str]) -> list[str]:
    if not any(len(_RUSSIAN_WORD_RE.findall(term)) > 1 for term in terms):
        return terms
    filtered: list[str] = []
    for term in terms:
        words = _RUSSIAN_WORD_RE.findall(term)
        if len(words) == 1 and _normalize_text(term) in _WEAK_STORY_SINGLETONS:
            continue
        filtered.append(term)
    return filtered


def _requirement_coverage(term: str, *, context_pack: list[dict[str, Any]], context_text: str) -> dict[str, Any]:
    normalized_term = _normalize_text(term)
    matched = normalized_term in context_text if normalized_term else False
    source_paths = []
    if matched:
        for item in context_pack:
            item_text = _normalize_text(_item_text(item))
            if normalized_term in item_text:
                path = item.get("path") or ((item.get("source") or {}).get("path") if isinstance(item.get("source"), dict) else None)
                normalized_path = normalize_doc_path(path)
                if normalized_path and normalized_path not in source_paths:
                    source_paths.append(normalized_path)
    return {"term": term, "matched": matched, "source_paths": source_paths}


def _source_search_action(*, missing_terms: list[str], context_pack: list[dict[str, Any]]) -> dict[str, Any]:
    suggested_paths = []
    for item in context_pack:
        path = item.get("path") or ((item.get("source") or {}).get("path") if isinstance(item.get("source"), dict) else None)
        normalized_path = normalize_doc_path(path)
        if normalized_path and normalized_path not in suggested_paths:
            suggested_paths.append(normalized_path)

    return {
        "action": "search_project_sources",
        "tool": "code_search",
        "reason": "Selected docs are partial/navigational; exact story-specific terms are missing from source-backed snippets.",
        "query_terms": missing_terms[:8],
        "suggested_doc_paths": suggested_paths[:8],
        "suggested_symbols": _suggested_symbols(context_pack),
        "suggested_layers": _suggested_layers(context_pack),
    }


def _suggested_symbols(context_pack: list[dict[str, Any]]) -> list[str]:
    symbols: list[str] = []
    for item in context_pack:
        text = _item_text(item)
        for match in _FILE_HINT_RE.findall(text):
            _append_unique(symbols, match)
        for match in _CODE_TERM_RE.findall(text):
            _append_unique(symbols, match)
    return symbols[:12]


def _suggested_layers(context_pack: list[dict[str, Any]]) -> list[str]:
    text = _item_text({"content": _context_text_raw(context_pack)})
    layers: list[str] = []
    for layer in _LAYER_TERMS:
        if re.search(rf"\b{re.escape(layer)}\b", text):
            _append_unique(layers, layer)
    return layers


def _has_navigational_context(context_pack: list[dict[str, Any]]) -> bool:
    text = _normalize_text(_context_text_raw(context_pack))
    nav_markers = [
        "architecture",
        "overview",
        "project structure",
        "ui ->",
        "cubit",
        "service",
        "repository",
        "api",
        "routes",
        "screen",
        "selected as high level",
        "selected as internal architecture",
    ]
    return any(marker in text for marker in nav_markers)


def _is_story_specific_query(question: str, intent: Any, requirements: list[str]) -> bool:
    normalized = _normalize_text(question)
    if _QUOTED_TERM_RE.search(question or ""):
        return True
    if any(marker in normalized for marker in _STORY_MARKERS):
        return bool(requirements)
    return bool(requirements) and (getattr(intent, "wants_code_symbols", False) or getattr(intent, "wants_how_to", False))


def _context_text(context_pack: list[dict[str, Any]]) -> str:
    return _normalize_text(_context_text_raw(context_pack))


def _proof_context_pack(context_pack: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in context_pack if item.get("source_class") in _PROOF_SOURCE_CLASSES and _is_positive_proof_item(item)]


def _source_backed_context_pack(context_pack: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in context_pack
        if (
            item.get("source_class") in _SOURCE_BACKED_PROOF_SOURCE_CLASSES
            or _is_catalog_source_of_truth(item)
        )
        and _is_positive_proof_item(item)
    ]


def _is_catalog_source_of_truth(item: dict[str, Any]) -> bool:
    return (
        item.get("source_class") == "project_doc"
        and item.get("authority") == "source_of_truth"
    )


def _is_positive_proof_item(item: dict[str, Any]) -> bool:
    if item.get("source_class") == "source_evidence" and item.get("evidence_class") in _ABSENT_EVIDENCE_CLASSES:
        return False
    if item.get("source_class") == "source_evidence" and item.get("matched") is False:
        return False
    return True


def _context_text_raw(context_pack: list[dict[str, Any]]) -> str:
    return "\n".join(_item_text(item) for item in context_pack)


def _item_text(item: dict[str, Any]) -> str:
    source = item.get("source") if isinstance(item.get("source"), dict) else {}
    section = item.get("section") if isinstance(item.get("section"), dict) else {}
    parts = [
        item.get("path"),
        item.get("title"),
        item.get("heading_path"),
        item.get("content"),
        item.get("why_selected"),
        source.get("path") if source else None,
        source.get("title") if source else None,
        section.get("heading_path") if section else None,
    ]
    return "\n".join(str(part) for part in parts if part)


def _clean_term(term: str) -> str:
    return re.sub(r"\s+", " ", str(term or "").strip().strip(".,:;!?()[]{}"))


def _normalize_text(text: str) -> str:
    normalized = str(text or "").casefold().replace("ё", "е").replace("_", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _dedupe_terms(terms: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        key = _normalize_text(term)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(term)
    return deduped


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)

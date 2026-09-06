"""Closed RU relation rewrites, audited against individual original clauses."""
from __future__ import annotations

import re

from .question_plan_core import PlannedFacet, _unsafe_free_text


def rewrite_component(text: str) -> tuple[str, PlannedFacet, str] | None:
    # Only explicit Latin technical identities are carried across languages.
    # Unknown modifiers, negation, pronouns and extra requests are not translated.
    subject_pattern = r"(?P<subject>[A-Za-z_][A-Za-z0-9_.-]*(?: [A-Za-z_][A-Za-z0-9_.-]*){0,2})"
    forms = (
        (r"как установить ", "installation", "workflow", "How do I install {subject}?"),
        (r"как проверить установку ", "verification", "workflow", "How do I verify the installation of {subject}?"),
        (r"когда использовать ", "usage", "usage", "When should I use {subject}?"),
        (r"какие публичные инструменты (?:предоставляет|экспортирует) ", "public_tools", "inventory", "Which public tools does {subject} expose?"),
    )
    for prefix, relation, kind, template in forms:
        match = re.fullmatch(prefix + subject_pattern + r"[?!.]*", " ".join(text.strip().split()), re.I)
        if match is None:
            continue
        subject = match.group("subject").rstrip(".")
        if len(subject) > 160 or _unsafe_free_text(subject) or subject.casefold() in {
            "it", "this", "that", "them", "project", "system", "server",
        }:
            return None
        inventory = kind == "inventory"
        facet = PlannedFacet(
            kind, subject, relation=None if inventory else relation,
            attribute="public_tools" if inventory else None,
            item_kind="public_tool" if inventory else None,
            value_kind="identifier_list" if inventory else "text",
            response_mode="names" if inventory else "workflow" if kind == "workflow" else "value",
            span_text=text,
        )
        return f"ru_component:{relation}:v1", facet, template.format(subject=subject)
    return None

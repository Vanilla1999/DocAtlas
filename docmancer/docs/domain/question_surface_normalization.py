"""Bounded EN/RU surface adapters for Project Docs questions.

The adapters in this module do not construct proof obligations and do not
perform fuzzy matching.  They only rewrite complete, audited surface families
to canonical questions already owned by QuestionPlan.  The original user span
is retained by ``compile_question_plan`` when a normalized surface is accepted.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from docmancer.docs.domain.question_frame_core import clean_phrase, strip_request_wrapper


@dataclass(frozen=True, slots=True)
class SurfaceNormalization:
    text: str
    rule: str


def _result(text: str, rule: str) -> SurfaceNormalization:
    return SurfaceNormalization(text=text, rule=rule)


_SEMANTIC_IDENTITIES = {
    "evidence selection": "evidence selection",
    "question planning": "question planning",
    "выбор доказательств": "evidence selection",
    "планирование вопроса": "question planning",
    "планирования вопроса": "question planning",
}


def _semantic_identity(value: str) -> str:
    cleaned = clean_phrase(value)
    return _SEMANTIC_IDENTITIES.get(cleaned.casefold(), cleaned)


_RU_SEMANTIC_ALIASES = {
    "войти": "entry",
    "вход": "entry",
    "разрешение на вход": "permission for entry",
    "определить разрешение на вход": "determine permission for entry",
    "приёмом отложенной работы": "accepting queued work",
    "приемом отложенной работы": "accepting queued work",
    "отсутствует немедленное разрешение": "immediate permission is missing",
    "контракт разрешений": "permission contract",
}


def _ru_semantic_value(value: str) -> str:
    cleaned = clean_phrase(value)
    return _RU_SEMANTIC_ALIASES.get(cleaned.casefold(), cleaned)


def normalize_question_surface(question: str) -> SurfaceNormalization | None:
    """Return a semantics-preserving canonical surface for a complete question."""

    q = clean_phrase(strip_request_wrapper(question))
    if not q:
        return None

    # Reviewed Russian variants of the reusable semantic frames. Captured
    # technical identities are preserved; only closed relation vocabulary is
    # canonicalized so this adapter cannot become a general translator.
    match = re.fullmatch(
        r"какое\s+значение\s+([A-Za-z_][\w.]*)\s+разрешает\s+(.+?)\s+(.+)", q, re.I,
    )
    if match is not None:
        kind, subject, action = (_ru_semantic_value(match.group(i)) for i in range(1, 4))
        return _result(
            f"Which {kind} permits {subject} to {action}?",
            "semantic:decision_for_action_ru",
        )
    match = re.fullmatch(
        r"какое\s+значение\s+([A-Za-z_][\w.]*)\s+должен\s+(.+?)\s+передать\s+в\s+([A-Za-z_][\w.]*)",
        q, re.I,
    )
    if match is not None:
        argument, actor, callee = (_ru_semantic_value(match.group(i)) for i in range(1, 4))
        return _result(
            f"What {argument} value must {actor} pass to {callee}?",
            "semantic:argument_value_ru",
        )
    match = re.fullmatch(
        r"какой\s+проектный\s+(.+?)\s+применяется\s+к\s+(.+?)[, ]+когда\s+(.+)", q, re.I,
    )
    if match is not None:
        contract, actors, condition = (_ru_semantic_value(match.group(i)) for i in range(1, 4))
        if contract.casefold().endswith("contract"):
            actors = re.sub(r"\s*,?\s+и\s+", ", and ", actors, flags=re.I)
            return _result(
                f"What project {contract} applies to {actors} when {condition}?",
                "semantic:applicable_contract_ru",
            )
    match = re.fullmatch(r"что\s+делает\s+(.+?)[, ]+чтобы\s+(.+)", q, re.I)
    if match is not None:
        subject, purpose = (_ru_semantic_value(match.group(i)) for i in range(1, 3))
        return _result(
            f"What does {subject} do to {purpose}?",
            "semantic:purpose_behavior_ru",
        )
    match = re.fullmatch(r"как\s+(.+?)\s+определяет\s+(.+)", q, re.I)
    if match is not None:
        subject, purpose = (_ru_semantic_value(match.group(i)) for i in range(1, 3))
        return _result(
            f"How does {subject} determine {purpose}?",
            "semantic:purpose_determine_ru",
        )
    match = re.fullmatch(r"что\s+делает\s+(.+?)\s+перед\s+(.+)", q, re.I)
    if match is not None:
        subject, action = (_ru_semantic_value(match.group(i)) for i in range(1, 3))
        return _result(
            f"What does {subject} do before {action}?",
            "semantic:behavior_before_ru",
        )

    # Closed inventory families.  These normalize voice/modifier order and
    # product-local wording without changing the requested inventory.
    if re.fullmatch(
        r"(?:what|which)\s+source\s+types?\s+(?:can\s+docatlas\s+index|"
        r"does\s+(?:docatlas|indexing)\s+(?:support|accept))",
        q,
        re.I,
    ):
        return _result("Which source types are supported for indexing?", "inventory:source_en")
    if re.fullmatch(r"(?:list|name|show)\s+(?:the\s+)?supported\s+source\s+types?", q, re.I):
        return _result("List source types supported for indexing.", "inventory:source_modifier")
    if re.fullmatch(
        r"(?:what|which)\s+(?:document|file)\s+formats?\s+"
        r"(?:does\s+indexing\s+accept|are\s+supported\s+for\s+local\s+files?)",
        q,
        re.I,
    ):
        return _result("Which file formats are supported for indexing?", "inventory:format_en")
    if re.fullmatch(
        r"what\s+markers?\s+does\s+(?:the\s+)?offline(?:\s+test)?\s+suite\s+define",
        q,
        re.I,
    ):
        return _result("What test markers are defined for the offline suite?", "inventory:marker_en")

    if re.fullmatch(r"какие\s+типы\s+источников\s+можно\s+индексировать", q, re.I):
        return _result("Which source types are supported for indexing?", "inventory:source_ru_can")
    if re.fullmatch(r"какие\s+типы\s+источников\s+поддерживает\s+docatlas", q, re.I):
        return _result("Which source types are supported for indexing?", "inventory:source_ru_product")
    if re.fullmatch(r"какие\s+форматы\s+(?:локальных\s+)?файлов\s+поддержива(?:ются|ет\s+docatlas)", q, re.I):
        return _result("Which file formats are supported for indexing?", "inventory:format_ru")
    if re.fullmatch(r"какие\s+pytest[- ]?маркеры\s+есть\s+в\s+проекте", q, re.I):
        return _result("List the pytest markers.", "inventory:marker_ru")
    if re.fullmatch(r"какие\s+(?:тестовые|pytest[- ]?)\s*маркеры\s+доступны", q, re.I):
        return _result("List the pytest markers.", "inventory:marker_ru_available")

    # Action/workflow wording.  The target operation is closed: only the public
    # project-doc sync action and the offline suite are normalized here.
    if re.fullmatch(r"which\s+command\s+should\s+i\s+run\s+after\s+project\s+docs?\s+change", q, re.I):
        return _result("What command syncs project docs after file changes?", "action:sync_after_change")
    if re.fullmatch(r"refresh\s+project\s+documentation\s+after\s+(?:a\s+)?file\s+changes", q, re.I):
        return _result("What command syncs project docs after file changes?", "action:sync_imperative")
    if re.fullmatch(r"какой\s+командой\s+синхронизировать\s+(?:проектную\s+документацию|документацию\s+проекта)", q, re.I):
        return _result("How do I sync project docs after editing a file?", "action:sync_ru_command")
    if re.fullmatch(r"how\s+can\s+i\s+run\s+the\s+offline(?:\s+test)?\s+suite", q, re.I):
        return _result("How do I run the offline suite?", "workflow:offline_can")
    if re.fullmatch(r"как\s+запустить\s+офлайн[- ]?тесты(?:\s+docatlas)?", q, re.I):
        return _result("How do I run the offline suite?", "workflow:offline_ru")
    if re.fullmatch(r"как\s+(?:обновить|синхронизировать)\s+(?:документацию\s+проекта|проектную\s+документацию)(?:\s+после\s+изменения\s+файла)?", q, re.I):
        return _result("How do I sync project docs after editing a file?", "action:sync_ru")
    if re.fullmatch(r"how\s+do\s+i\s+configure\s+project\s+docs?\s+in\s+docmancer\.yaml", q, re.I):
        return _result("How do I configure a project in docmancer.yaml?", "workflow:project_docs_config")

    # Compound inventory/action surfaces are normalized as a whole so clause
    # splitting cannot lose the second requested facet.
    if re.fullmatch(
        r"(?:what|which)\s+source\s+types?\s+are\s+supported\s+for\s+indexing\s+"
        r"and\s+explain\s+clear-index",
        q,
        re.I,
    ):
        return _result(
            "Which source types are supported for indexing and how does clear-index work?",
            "compound:inventory_explain",
        )
    if re.fullmatch(r"what\s+source\s+types?\s+and\s+file\s+formats?\s+are\s+supported", q, re.I):
        return _result(
            "Which source types are supported for indexing and which file formats are supported for indexing?",
            "compound:source_format_inventory",
        )

    # Comparison punctuation/surface order.  This runs before clause splitting
    # so the explanatory tail after ':' is not mistaken for a second request.
    comparison = re.fullmatch(r"(.+?)\s+vs\.?\s+(.+?)[,:]\s*what\s+differs", q, re.I)
    if comparison is not None:
        left = _semantic_identity(comparison.group(1))
        right = _semantic_identity(comparison.group(2))
        if left and right and left.casefold() != right.casefold():
            return _result(
                f"How does {left} differ from {right}?",
                "comparison:vs_tail",
            )

    if re.fullmatch(r"чем\s+выбор\s+доказательств\s+отличается\s+от\s+планировани[яю]\s+вопроса", q, re.I):
        return _result("How does evidence selection differ from question planning?", "comparison:ru_difference")
    if re.fullmatch(r"сравни\s+выбор\s+доказательств\s+и\s+планировани[ея]\s+вопроса", q, re.I):
        return _result("Compare evidence selection with question planning.", "comparison:ru_compare")
    if re.fullmatch(r"чем\s+evidence\s+selection\s+отличается\s+от\s+question\s+planning", q, re.I):
        return _result("How does evidence selection differ from question planning?", "comparison:mixed_ru_difference")
    if re.fullmatch(r"сравни\s+evidence\s+selection\s+и\s+question\s+planning", q, re.I):
        return _result("Compare evidence selection with question planning.", "comparison:mixed_ru_compare")

    # Closed Docs MCP public-tool wording.
    if re.fullmatch(
        r"назови\s+(?:три\s+)?публичных\s+инструмент(?:а|ов)\s+docs\s+mcp\s+"
        r"и\s+когда\s+использовать\s+кажд(?:ый|ого)",
        q,
        re.I,
    ):
        return _result(
            "What are the three public Docs MCP tools and when do I use each one?",
            "public_tools:usage_ru",
        )
    if re.fullmatch(r"какие\s+публичные\s+инструменты\s+есть\s+у\s+docs\s+mcp", q, re.I):
        return _result("Which public Docs MCP tools are available?", "public_tools:inventory_ru")

    # Russian condition/premise surfaces with canonical project identities.
    if re.fullmatch(r"что\s+произойд[её]т[, ]+если\s+план\s+предпросмотра\s+устарел", q, re.I):
        return _result("What happens when the preview plan is stale?", "condition:preview_stale_ru")
    if re.fullmatch(r"что\s+происходит[, ]+когда\s+preview\s+plan\s+устарел", q, re.I):
        return _result("What happens when the preview plan is stale?", "condition:preview_stale_mixed_ru")
    if re.fullmatch(r"можно\s+ли\s+запустить\s+clear-index[, ]+пока\s+mcp\s+server\s+работает", q, re.I):
        return _result("Can clear-index run while the MCP server is alive?", "condition:mcp_alive_ru")
    if re.fullmatch(r"при\s+каких\s+условиях\s+cleanup\s+блокируется", q, re.I):
        return _result("Under which conditions is cleanup blocked?", "condition:cleanup_blocked_ru")
    if re.fullmatch(r"почему\s+clear-index\s+всегда\s+удаляет\s+удал[её]нные\s+коллекции\s+qdrant", q, re.I):
        return _result(
            "Why does clear-index always delete remote Qdrant collections?",
            "premise:remote_qdrant_always_ru",
        )
    if re.fullmatch(r"почему\s+clear-index\s+никогда\s+не\s+удаляет\s+удал[её]нные\s+коллекции\s+qdrant", q, re.I):
        return _result(
            "Why does clear-index never delete remote Qdrant collections?",
            "premise:remote_qdrant_ru",
        )
    if re.fullmatch(r"почему\s+у\s+docs\s+mcp\s+четыре\s+публичных\s+инструмента", q, re.I):
        return _result("Why are there four public Docs MCP tools?", "premise:public_tools_cardinality_ru")
    if re.fullmatch(r"при\s+каких\s+условиях\s+clear-index\s+нельзя\s+запускать", q, re.I):
        return _result("Under which conditions is clear-index blocked?", "condition:clear_index_blocked_ru")

    if re.fullmatch(r"где\s+документирован\s+контракт\s+ответа\s+проекта", q, re.I):
        return _result("Where is the project answer contract documented?", "location:project_answer_ru")
    if re.fullmatch(r"в\s+каком\s+файле\s+описан\s+project\s+answer\s+contract", q, re.I):
        return _result("Where is the project answer contract documented?", "location:project_answer_mixed_ru")

    # One documented state synonym: an expired preview plan is semantically a
    # stale preview plan for the clear-index apply contract.
    if re.fullmatch(r"what\s+happens\s+when\s+(?:the\s+)?preview\s+plan\s+expires", q, re.I):
        return _result("What happens when the preview plan is stale?", "condition:preview_expired")

    return None


__all__ = ["SurfaceNormalization", "normalize_question_surface"]

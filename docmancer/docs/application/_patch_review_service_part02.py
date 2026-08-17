"""PatchReviewService implementation shard 2."""
from __future__ import annotations

from ._patch_review_service_shared import *  # noqa: F401,F403


class _PatchReviewServicePart02:
    @staticmethod
    def _review_summary_quality_payload(
        task: str,
        changed_files: list[str],
        constraints: dict[str, Any],
        validation: dict[str, Any],
        *,
        summary_max_items: int = 5,
        summary_mode: str = "standard",
    ) -> dict[str, Any]:
        model = PatchReviewService._review_summary_model(
            task,
            changed_files,
            constraints,
            validation,
            summary_max_items=summary_max_items,
            summary_mode=summary_mode,
        )
        summary_mode = model["summary_mode"]
        actionable = model["actionable"]
        all_actionable = model["all_actionable"]
        low_context = model["low_context"]
        low_symbols = model["low_symbols"]
        unknown_buckets = model["unknown_buckets"]
        unknown_triage = model["unknown_triage"]
        residual_memos = model["residual_memos"]
        quality = model["quality"]
        signals = PatchReviewService._review_summary_quality_signals(
            actionable=actionable,
            low_context=low_context,
            low_symbols=low_symbols,
            unknown_buckets=unknown_buckets,
            unknown_triage=unknown_triage,
            residual_memos=residual_memos,
            validation=validation,
        )
        return {
            "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_quality.json"],
            "attachable": quality["attachable"],
            "summary_mode": summary_mode,
            "actionable_items_limit": summary_max_items,
            "actionable_items_count": len(actionable),
            "actionable_items_total_count": len(all_actionable),
            "low_value_top_items_count": len(low_context) + len(low_symbols),
            "unknown_bucket_count": len(unknown_buckets),
            "residual_memo_source_count": len(residual_memos),
            "satisfied_count": validation.get("satisfied", 0),
            "violated_count": validation.get("violated", 0),
            "unknown_count": validation.get("unknown", 0),
            "manual_review_count": validation.get("manual_review", 0),
            "reasons": quality["reasons"],
            "signals": signals,
            "unknown_triage": unknown_triage,
            "unknown_buckets": [
                {
                    "name": name,
                    "count": len(items),
                    "examples": [
                        {"constraint_id": item.get("constraint_id"), "reason": item.get("reason")}
                        for item in items[:2]
                    ],
                }
                for name, items in unknown_buckets.items()
            ],
            "claims_avoided": [
                "correctness_proof",
                "test_or_human_review_replacement",
                "broad_docatlas_superiority",
            ],
        }

    @staticmethod
    def _review_summary_quality_signals(
        *,
        actionable: list[dict[str, Any]],
        low_context: list[dict[str, Any]],
        low_symbols: list[dict[str, Any]],
        unknown_buckets: dict[str, list[dict[str, Any]]],
        unknown_triage: list[dict[str, Any]],
        residual_memos: list[dict[str, Any]],
        validation: dict[str, Any],
    ) -> list[dict[str, Any]]:
        signals = [
            {
                "code": "actionable_items_present" if actionable else "no_actionable_items",
                "severity": "info" if actionable else "warning",
                "count": len(actionable),
                "message": "Actionable checklist items are available." if actionable else "No actionable checklist items were selected.",
            },
            {
                "code": "violations_present" if validation.get("violated", 0) else "no_violations",
                "severity": "error" if validation.get("violated", 0) else "info",
                "count": validation.get("violated", 0),
                "message": "Validation found violated constraints." if validation.get("violated", 0) else "Validation found no violated constraints.",
            },
        ]
        if unknown_buckets:
            signals.append(
                {
                    "code": "unknown_buckets_present",
                    "severity": "warning",
                    "count": len(unknown_buckets),
                    "message": "Manual-review buckets remain.",
                }
            )
        manual_review_count = sum(item["count"] for item in unknown_triage if item.get("requires_manual_review"))
        if manual_review_count:
            signals.append(
                {
                    "code": "manual_review_required",
                    "severity": "warning",
                    "count": manual_review_count,
                    "message": "Unknown validation results require manual review; do not treat them as pass.",
                }
            )
        if low_context or low_symbols:
            signals.append(
                {
                    "code": "low_value_signals_present",
                    "severity": "warning",
                    "count": len(low_context) + len(low_symbols),
                    "message": "Low-confidence or noisy signals were kept out of the top checklist.",
                }
            )
        if residual_memos:
            signals.append(
                {
                    "code": "residual_memo_sources_present",
                    "severity": "warning",
                    "count": len(residual_memos),
                    "message": "Prior dogfood memo/task artifacts were excluded from top-level recommendations.",
                }
            )
        return signals

    @staticmethod
    def _review_summary_actions_payload(
        task: str,
        changed_files: list[str],
        constraints: dict[str, Any],
        validation: dict[str, Any],
        *,
        summary_max_items: int = 5,
        summary_mode: str = "standard",
    ) -> dict[str, Any]:
        model = PatchReviewService._review_summary_model(
            task,
            changed_files,
            constraints,
            validation,
            summary_max_items=summary_max_items,
            summary_mode=summary_mode,
        )
        summary_mode = model["summary_mode"]
        actionable = model["actionable"]
        violations = model["violations"]
        results_by_id = model["results_by_id"]
        return {
            "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_actions.json"],
            "summary_mode": summary_mode,
            "actionable_items_limit": summary_max_items,
            "actionable_items": [
                PatchReviewService._actionable_item_payload(
                    item,
                    results_by_id.get(str(item.get("id") or "")),
                    rank=index,
                )
                for index, item in enumerate(actionable, start=1)
            ],
            "violations": [
                {
                    "constraint_id": item.get("constraint_id"),
                    "reason": item.get("reason"),
                    "files": item.get("files", []),
                }
                for item in violations
            ],
            "claims_avoided": [
                "correctness_proof",
                "test_or_human_review_replacement",
                "broad_docatlas_superiority",
            ],
        }

    @staticmethod
    def _actionable_item_payload(item: dict[str, Any], result: dict[str, Any] | None, *, rank: int) -> dict[str, Any]:
        source = item.get("source")
        instruction = item.get("instruction")
        evidence = item.get("evidence")
        files = item.get("files") or []
        symbols = item.get("symbols") or []
        payload = {
            "rank": rank,
            "constraint_id": item.get("id"),
            "instruction": instruction,
            "source": source,
            "type": item.get("type"),
            "confidence": item.get("confidence"),
            "evidence": evidence,
            "source_files": files,
            "symbols": symbols,
            "files": files,
            "markdown": (
                f"- {PatchReviewService._markdown_text(instruction)} "
                f"(source: `{PatchReviewService._markdown_text(source)}`)"
            ),
            "evidence_markdown": f"  - evidence: {PatchReviewService._markdown_text(evidence)}" if evidence else None,
        }
        if result:
            payload["validation_status"] = result.get("status")
            payload["validation_reason"] = result.get("reason")
            payload["files"] = result.get("files", [])
        return payload

    @staticmethod
    def _markdown_text(value: Any, *, limit: int = MAX_PR_COMMENT_FIELD_CHARS) -> str:
        text = str(value or "")
        text = text.replace("`", "\\`").replace("@", "@\u200b")
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 16)].rstrip() + " … [truncated]"

    @staticmethod
    def _truncate_pr_comment(body: str) -> str:
        if len(body) <= MAX_PR_COMMENT_CHARS:
            return body
        return body[: MAX_PR_COMMENT_CHARS - 64].rstrip() + "\n\n_Comment truncated for provider limits._\n"

    @staticmethod
    def _constraints_markdown(packet: dict[str, Any]) -> str:
        lines = ["# Patch constraints", "", f"Task: {packet.get('task')}", "", "## Constraints"]
        for constraint in packet.get("constraints", []):
            lines.append(
                f"- [{constraint.get('type')}/{constraint.get('severity')}/{constraint.get('confidence')}] "
                f"{constraint.get('instruction')} (source: `{constraint.get('source')}`)"
            )
        if packet.get("symbol_candidates"):
            lines.extend(["", "## Symbol candidates"])
            for candidate in packet["symbol_candidates"]:
                lines.append(f"- `{candidate.get('term')}` -> `{candidate.get('matched_symbol')}` in `{candidate.get('source')}`: {candidate.get('evidence')}")
        if packet.get("warnings"):
            lines.extend(["", "## Warnings"])
            lines.extend(f"- {warning}" for warning in packet["warnings"])
        return "\n".join(lines) + "\n"

    @staticmethod
    def _review_summary(
        task: str,
        changed_files: list[str],
        constraints: dict[str, Any],
        validation: dict[str, Any],
        *,
        warnings: list[str] | None = None,
        untracked_files: list[str] | None = None,
        ignored_runtime_artifacts: list[str] | None = None,
        summary_max_items: int = 5,
        summary_mode: str = "standard",
    ) -> str:
        model = PatchReviewService._review_summary_model(
            task,
            changed_files,
            constraints,
            validation,
            summary_max_items=summary_max_items,
            summary_mode=summary_mode,
        )
        summary_mode = model["summary_mode"]
        warnings = warnings or []
        untracked_files = untracked_files or []
        ignored_runtime_artifacts = ignored_runtime_artifacts or []
        violations = model["violations"]
        generated_or_lock = model["generated_or_lock"]
        actionable = model["actionable"]
        manual_context = model["manual_context"]
        low_context = model["low_context"]
        symbol_limit = model["symbol_limit"]
        low_limit = model["low_limit"]
        excluded_limit = model["excluded_limit"]
        useful_symbols = model["useful_symbols"]
        low_symbols = model["low_symbols"]
        unknown_buckets = model["unknown_buckets"]
        excluded_sources = model["excluded_sources"]
        residual_memos = model["residual_memos"]
        quality = model["quality"]

        lines = [
            "# Patch review summary",
            "",
            "Status: review/audit artifact, not correctness proof.",
            "",
            f"Task: {task}",
            "",
            "## Changed files",
            *[f"- {path}" for path in changed_files],
            "",
            "## Review summary quality",
            f"- attachable: {quality['attachable']}",
            f"- summary_mode: {summary_mode}",
            f"- actionable_items_limit: {summary_max_items}",
            f"- actionable_items_count: {len(actionable)}",
            f"- low_value_top_items_count: {len(low_context) + len(low_symbols)}",
            f"- unknown_bucket_count: {len(unknown_buckets)}",
            f"- residual_memo_source_count: {len(residual_memos)}",
        ]
        if quality["reasons"]:
            lines.append("- reasons:")
            lines.extend(f"  - {reason}" for reason in quality["reasons"])
        lines.extend(["", "## Actionable PR checklist"])
        lines.extend(
            [f"- {item.get('instruction')} (source: `{item.get('source')}`)" for item in actionable]
            or ["- none"]
        )
        if summary_mode == "compact":
            lines.extend(["", "## Violations"])
            lines.extend([f"- {item.get('constraint_id')}: {item.get('reason')}" for item in violations] or ["- none"])
            lines.extend([
                "",
                "## Claims avoided",
                "- This artifact does not prove correctness.",
                "- This artifact does not replace tests or human review.",
                "- This artifact does not claim broad DocAtlas superiority.",
            ])
            return "\n".join(lines) + "\n"
        lines.extend(["", "## Manual review context"])
        lines.extend(
            [f"- {item.get('instruction')} (source: `{item.get('source')}`)" for item in manual_context]
            or ["- none"]
        )
        lines.extend(["", "## Low-confidence / noisy signals"])
        lines.extend([f"- {item.get('instruction')} (source: `{item.get('source')}`)" for item in low_context] or [])
        lines.extend(
            [
                f"- symbol `{item.get('matched_symbol')}` from `{item.get('source')}`: {item.get('reason')}"
                for item in low_symbols[:6]
            ]
            or ["- none"]
        )
        lines.extend([
            "",
            "## Validation",
            f"- satisfied: {validation.get('satisfied', 0)}",
            f"- violated: {validation.get('violated', 0)}",
            f"- unknown/manual review: {validation.get('unknown', 0) + validation.get('manual_review', 0)}",
            f"- unknown: {validation.get('unknown', 0)}",
            f"- manual_review: {validation.get('manual_review', 0)}",
            "",
            "## Violations",
        ])
        lines.extend([f"- {item.get('constraint_id')}: {item.get('reason')}" for item in violations] or ["- none"])
        lines.extend(["", "## Unknown/manual review buckets"])
        if unknown_buckets:
            for name, items in unknown_buckets.items():
                lines.append(f"- {name}: {len(items)}")
                for item in items[:2]:
                    lines.append(f"  - {item.get('constraint_id')}: {item.get('reason')}")
        else:
            lines.append("- none")
        lines.extend(["", "## Generated/lockfile checks"])
        lines.extend([f"- {item.get('constraint_id')}: {item.get('status')} — {item.get('reason')}" for item in generated_or_lock] or ["- none"])
        if constraints.get("symbol_candidates"):
            lines.extend(["", "## Source-of-truth / symbol notes"])
            if useful_symbols:
                for candidate in useful_symbols[:symbol_limit]:
                    lines.append(f"- `{candidate.get('term')}` -> `{candidate.get('matched_symbol')}` (`{candidate.get('source')}`)")
            if low_symbols:
                lines.append("- low-confidence/noisy symbols hidden from checklist:")
                lines.extend(f"  - `{candidate.get('matched_symbol')}` (`{candidate.get('source')}`)" for candidate in low_symbols[:low_limit])
        if excluded_sources:
            lines.extend(["", "## Excluded or ignored sources"])
            for item in excluded_sources[:excluded_limit]:
                lines.append(f"- {item.get('reason')}: `{item.get('path')}`")
            if len(excluded_sources) > excluded_limit:
                lines.append(f"- ... {len(excluded_sources) - excluded_limit} more excluded source(s)")
        if untracked_files:
            lines.extend(["", "## Untracked files"])
            lines.extend(f"- {path}" for path in untracked_files)
        if ignored_runtime_artifacts:
            lines.extend(["", "## Ignored runtime/cache artifacts"])
            lines.extend(f"- {path}" for path in ignored_runtime_artifacts[:20])
        if constraints.get("warnings") or validation.get("warnings") or warnings:
            lines.extend(["", "## Warnings"])
            lines.extend(f"- {warning}" for warning in warnings)
            lines.extend(f"- {warning}" for warning in constraints.get("warnings", []))
            lines.extend(f"- {warning}" for warning in validation.get("warnings", []))
        lines.extend([
            "",
            "## Claims avoided",
            "- This artifact does not prove correctness.",
            "- This artifact does not replace tests or human review.",
            "- This artifact does not claim broad DocAtlas superiority.",
        ])
        return "\n".join(lines) + "\n"

    @staticmethod
    def _summary_constraint_rank(item: dict[str, Any], changed_files: list[str], task: str) -> tuple[int, int, str]:
        source = str(item.get("source") or "")
        instruction = str(item.get("instruction") or "")
        evidence = str(item.get("evidence") or "")
        ctype = str(item.get("type") or "")
        confidence = str(item.get("confidence") or "low")
        haystack = f"{instruction} {evidence} {' '.join(item.get('symbols') or [])}".lower()
        haystack_compact = re.sub(r"[^a-z0-9]+", "", haystack)
        changed = " ".join(changed_files).lower()
        task_lower = task.lower()
        priority = 50
        if ctype in {"generated_file", "forbidden_edit"} or "generated" in haystack or "lockfile" in haystack:
            priority = min(priority, 10)
        if any(path and path.lower() in source.lower() for path in changed_files):
            priority = min(priority, 15)
        if any(token in haystack or token in haystack_compact for token in PatchReviewService._task_symbol_tokens(task_lower)):
            priority = min(priority, 20)
        if "policy" in task_lower and ("provider" in haystack or "policy" in haystack or "ui" in haystack):
            priority = min(priority, 22)
        if source.startswith("docs/research/docatlas-dogfood"):
            priority = max(priority, 80)
        if PatchReviewService._is_broad_context_source(source, instruction):
            priority = max(priority, 60)
        if PatchReviewService._has_only_low_value_symbols(item) or PatchReviewService._has_low_value_matched_symbol(item):
            priority = max(priority, 60)
        confidence_rank = {"high": 0, "medium": 1, "low": 2}.get(confidence, 3)
        if source and source.lower() in changed:
            priority -= 3
        return (priority, confidence_rank, str(item.get("id") or ""))

    @staticmethod
    def _summary_bucket(item: dict[str, Any], changed_files: list[str], task: str) -> str:
        rank = PatchReviewService._summary_constraint_rank(item, changed_files, task)[0]
        source = str(item.get("source") or "")
        confidence = str(item.get("confidence") or "low")
        if source.startswith("docs/research/docatlas-dogfood") or rank >= 75 or confidence == "low":
            return "low"
        if rank <= 25:
            return "actionable"
        return "manual"

    @staticmethod
    def _dedupe_constraints(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for item in items:
            key = str(item.get("id") or item.get("instruction") or "")
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    @staticmethod
    def _task_symbol_tokens(task_lower: str) -> set[str]:
        tokens = {
            token
            for token in re.findall(r"[a-zа-я0-9_]{3,}", task_lower, flags=re.IGNORECASE)
            if token not in TASK_TOKEN_STOPWORDS
            and token not in {value.lower() for value in LOW_VALUE_SYMBOLS}
        }
        compact_task = re.sub(r"[^a-zа-я0-9]+", "", task_lower, flags=re.IGNORECASE)
        for token in ("openinfo", "closemenu", "gotoscandocinit", "generated", "lockfile", "provider", "policy"):
            if token.lower() in task_lower:
                tokens.add(token.lower())
        for phrase in re.findall(r"[a-z][a-z0-9_]*(?:\s+[a-z][a-z0-9_]*)+", task_lower):
            compact_phrase = re.sub(r"[^a-z0-9]+", "", phrase)
            if len(compact_phrase) >= 6:
                tokens.add(compact_phrase)
        if compact_task and len(compact_task) <= 48:
            tokens.add(compact_task)
        if "быстрая информация" in task_lower or "quick-info" in task_lower or "quick info" in task_lower:
            tokens.add("openinfo")
        if "закры" in task_lower or "close menu" in task_lower or "штор" in task_lower:
            tokens.add("closemenu")
        if "scan" in task_lower or "скан" in task_lower:
            tokens.add("gotoscandocinit")
        return tokens

    @staticmethod
    def _is_low_value_symbol_candidate(item: dict[str, Any], task: str) -> bool:
        symbol = str(item.get("matched_symbol") or "")
        task_lower = task.lower()
        if symbol in LOW_VALUE_SYMBOLS or symbol.lower() in {value.lower() for value in LOW_VALUE_SYMBOLS}:
            explicit = symbol.lower() in task_lower
            return not explicit
        evidence = str(item.get("evidence") or "").strip()
        if evidence.startswith(("import ", "export ", "part ")):
            return True
        return False

    @staticmethod
    def _has_only_low_value_symbols(item: dict[str, Any]) -> bool:
        symbols = [str(symbol or "") for symbol in item.get("symbols") or []]
        if not symbols:
            return False
        low_value = {value.lower() for value in LOW_VALUE_SYMBOLS}
        return all(symbol in LOW_VALUE_SYMBOLS or symbol.lower() in low_value for symbol in symbols)

    @staticmethod
    def _has_low_value_matched_symbol(item: dict[str, Any]) -> bool:
        symbols = [str(symbol or "") for symbol in item.get("symbols") or []]
        if len(symbols) < 2:
            return False
        low_value = {value.lower() for value in LOW_VALUE_SYMBOLS}
        matched_symbol = symbols[-1]
        if matched_symbol not in LOW_VALUE_SYMBOLS and matched_symbol.lower() not in low_value:
            return False
        evidence = str(item.get("evidence") or "").strip()
        if evidence.startswith(("import ", "export ", "part ")):
            return True
        instruction = str(item.get("instruction") or "")
        return "matches existing project symbol" in instruction

    @staticmethod
    def _is_broad_context_source(source: str, instruction: str) -> bool:
        lowered = f"{source} {instruction}".lower()
        return (
            "external_oidc" in lowered
            or "rules that must not be violated" in lowered
            or "mainscreen owns global runtime" in lowered
        )

    @staticmethod
    def _unknown_buckets(unknowns: list[dict[str, Any]], constraints: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        by_id = {item.get("id"): item for item in constraints}
        buckets: dict[str, list[dict[str, Any]]] = {}
        for item in unknowns:
            constraint = by_id.get(item.get("constraint_id"), {})
            source = str(constraint.get("source") or "")
            reason = str(item.get("reason") or "")
            text = f"{item.get('constraint_id')} {reason} {source}".lower()
            if source.startswith("docs/research/docatlas-dogfood"):
                bucket = "Residual dogfood/research memo context"
            elif "source-of-truth" in text or "source_of_truth" in text or "ownership" in text or "owns" in text:
                bucket = "Source-of-truth ownership unknowns"
            elif "provider" in text or "ui" in text or "policy" in text or "presentation" in text:
                bucket = "Provider/UI policy ownership unknowns"
            elif "generated" in text or "lockfile" in text or "protected" in text:
                bucket = "Generated/lockfile/protected-file unknowns"
            elif "module" in text or "boundary" in text or "route" in text or "scan_doc" in text or "architecture" in text:
                bucket = "Module-boundary context unknowns"
            else:
                bucket = "Other low-confidence context"
            buckets.setdefault(bucket, []).append(item)
        return dict(sorted(buckets.items()))

    @staticmethod
    def _unknown_triage(unknowns: list[dict[str, Any]], constraints: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_id = {item.get("id"): item for item in constraints}
        buckets: dict[str, list[dict[str, Any]]] = {
            "missing_diff_evidence": [],
            "missing_test_evidence": [],
            "manual_review_required": [],
            "low_risk_unknown": [],
        }
        messages = {
            "missing_diff_evidence": "No decisive changed-file or diff evidence was found for this constraint.",
            "missing_test_evidence": "The unknown result depends on missing or inconclusive test evidence.",
            "manual_review_required": "A human reviewer must resolve an open product, ownership, or policy question.",
            "low_risk_unknown": "Low-confidence context remains unresolved; keep it visible for manual review.",
        }
        for item in unknowns:
            constraint = by_id.get(item.get("constraint_id"), {})
            manual_text = " ".join(
                str(value or "")
                for value in (
                    item.get("reason"),
                    constraint.get("instruction"),
                    constraint.get("evidence"),
                    constraint.get("source"),
                )
            ).lower()
            evidence_text = " ".join(
                str(value or "")
                for value in (
                    item.get("constraint_id"),
                    item.get("reason"),
                    constraint.get("instruction"),
                    constraint.get("evidence"),
                    constraint.get("source"),
                    constraint.get("type"),
                )
            ).lower()
            if PatchReviewService._has_manual_unknown_signal(manual_text):
                code = "manual_review_required"
            elif "test" in evidence_text or "coverage" in evidence_text or "regression" in evidence_text:
                code = "missing_test_evidence"
            elif PatchReviewService._has_missing_diff_unknown_signal(evidence_text):
                code = "missing_diff_evidence"
            else:
                code = "low_risk_unknown"
            buckets[code].append(item)
        return [
            {
                "code": code,
                "count": len(items),
                "requires_manual_review": True,
                "message": messages[code],
                "examples": [
                    PatchReviewService._unknown_triage_example(item, by_id.get(item.get("constraint_id"), {}))
                    for item in items[:2]
                ],
            }
            for code, items in buckets.items()
            if items
        ]

    @staticmethod
    def _unknown_triage_example(item: dict[str, Any], constraint: dict[str, Any]) -> dict[str, Any]:
        example = {
            "constraint_id": item.get("constraint_id"),
            "reason": item.get("reason"),
        }
        for field in ("source", "instruction", "evidence", "confidence"):
            value = constraint.get(field)
            if value:
                example[field] = value
        return example

    @staticmethod
    def _has_manual_unknown_signal(text: str) -> bool:
        manual_tokens = (
            "manual review",
            "manual reviewer",
            "manual approval",
            "manual decision",
            "manual triage",
            "human review",
            "human reviewer",
            "designer",
            "open question",
            "ownership",
            "source-of-truth",
            "source of truth",
            "policy",
            "дизайнер",
            "дизайнера",
            "дизайнером",
            "открытый вопрос",
            "открыт вопрос",
            "владель",
            "ответствен",
            "согласовать",
            "уточнить",
            "политик",
        )
        if any(token in text for token in manual_tokens):
            return True
        return bool(re.search(r"\bdesign\s+(?:input|question|approval|review|owner|dependency)\b", text))

    @staticmethod
    def _has_missing_diff_unknown_signal(text: str) -> bool:
        if any(
            token in text
            for token in (
                "diff",
                "changed-file",
                "changed file",
                "patch",
                "direct evidence",
                "not found",
                "missing evidence",
                "changed files unavailable",
                "changed files or diff unavailable",
                "not deterministically checkable from changed files",
                "not deterministic for this patch",
            )
        ):
            return True
        return any(token in text for token in ("source question", "source changed_files", "source changed files"))

    @staticmethod
    def _summary_quality(
        *,
        actionable: list[dict[str, Any]],
        actionable_total_count: int,
        low_context: list[dict[str, Any]],
        low_symbols: list[dict[str, Any]],
        unknown_buckets: dict[str, list[dict[str, Any]]],
        residual_memos: list[dict[str, Any]],
    ) -> dict[str, Any]:
        reasons: list[str] = []
        if len(actionable) < 3:
            reasons.append(f"only {len(actionable)} actionable checklist item(s)")
        if low_context or low_symbols:
            reasons.append(f"{len(low_context) + len(low_symbols)} low-confidence/noisy signal(s) kept outside checklist")
        if unknown_buckets:
            reasons.append(f"unknowns collapsed into {len(unknown_buckets)} bucket(s)")
        if residual_memos:
            reasons.append(f"{len(residual_memos)} residual dogfood memo source(s) excluded/demoted")
        attachable = "yes"
        if actionable_total_count < 3 or len(unknown_buckets) > 5:
            attachable = "no"
        elif low_context or low_symbols or residual_memos or unknown_buckets:
            attachable = "maybe"
        return {"attachable": attachable, "reasons": reasons}

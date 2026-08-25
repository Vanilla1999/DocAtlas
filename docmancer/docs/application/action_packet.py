from __future__ import annotations

from dataclasses import replace
from pathlib import PurePosixPath
import re
from typing import Any, Iterable, Mapping

from ._action_packet_shared import *  # noqa: F401,F403

from ._action_packet_part01 import *  # noqa: F401,F403

from ._action_packet_part02 import *  # noqa: F401,F403

from ._action_packet_part03 import *  # noqa: F401,F403
from ._action_packet_part03 import build_action_packet as _build_action_packet_impl

from ._action_packet_part04 import *  # noqa: F401,F403


PATCH_PROJECTION_RESERVE_TOKENS = 48
_TRUSTED_PROJECT_RULE_AUTHORITIES = frozenset({
    "canonical", "primary", "project_rule", "source_of_truth",
})
_GENERIC_PATH_TOKENS = frozenset({
    "application", "architecture", "contract", "docs", "flow", "gate", "lib", "module", "modules",
})


def _path_token_sequence(value: str) -> tuple[str, ...]:
    stem = PurePosixPath(str(value or "").replace("\\", "/")).stem
    return tuple(
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9]+", stem.replace("_", "-").replace("-", " "))
        if len(token) >= 3 and token.casefold() not in _GENERIC_PATH_TOKENS
    )


def _path_tokens(value: str) -> set[str]:
    return set(_path_token_sequence(value))


def _target_scope(path: str) -> str:
    stem = PurePosixPath(path.replace("\\", "/")).stem
    parts = [part for part in re.split(r"[_\-]+", stem) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) or stem


def _declared_authority_by_path(context_pack: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in context_pack:
        if not isinstance(item, Mapping):
            continue
        path = str(item.get("path") or item.get("source") or "").strip().replace("\\", "/").casefold()
        authority = str(item.get("authority") or item.get("repository_authority") or "").strip().casefold()
        if path and authority:
            values[path] = authority
    return values


def _behavioral_source_fact_contracts(
    *,
    required_evidence_paths: Iterable[str],
    required_target_paths: Iterable[str],
    context_pack: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Derive one bounded source-scoped behavior obligation per affected flow.

    Matching is based only on public source/target identities. It never embeds a
    benchmark answer string. A document path proves identity separately; this
    extra obligation requires substantive behavioral text from the same source.
    """

    docs = [
        str(path).strip().replace("\\", "/")
        for path in required_evidence_paths
        if str(path).strip().replace("\\", "/").casefold().startswith("docs/")
        and PurePosixPath(str(path)).suffix.casefold() in {".md", ".mdx", ".rst", ".adoc"}
    ]
    targets = [
        str(path).strip().replace("\\", "/")
        for path in required_target_paths
        if str(path).strip()
    ]
    if not docs or not targets:
        return ()
    authority_by_path = _declared_authority_by_path(context_pack)
    rows: list[dict[str, Any]] = []
    used_scopes: set[str] = set()
    for source_path in docs:
        source_sequence = _path_token_sequence(source_path)
        source_terms = set(source_sequence)
        ranked: list[tuple[tuple[Any, ...], str]] = []
        for target in targets:
            target_sequence = _path_token_sequence(target)
            target_terms = set(target_sequence)
            overlap = len(source_terms & target_terms)
            if not overlap:
                continue
            # Prefer the target whose leading domain noun matches the source
            # document before using generic lexical density. This prevents a
            # broad permission architecture document from stealing the browser
            # flow scope merely because both target names contain "permission".
            leading_domain_match = int(bool(
                source_sequence
                and target_sequence
                and source_sequence[0] == target_sequence[0]
            ))
            density = int(overlap * 1000 / max(1, len(target_terms)))
            ranked.append((
                (-overlap, -leading_domain_match, -density, len(target_terms), target.casefold()),
                target,
            ))
        if not ranked:
            continue
        target = min(ranked, key=lambda row: row[0])[1]
        scope = _target_scope(target)
        if not scope or scope in used_scopes:
            continue
        used_scopes.add(scope)
        declared = authority_by_path.get(source_path.casefold(), "")
        rows.append({
            "kind": "source_fact",
            "source_path": source_path,
            "scope": scope,
            "modality": "required",
            "requirement_id": f"behavioral_contract:{scope}",
            "public_provenance": "public_task_contract",
            "proof_role": "project_rule" if declared in _TRUSTED_PROJECT_RULE_AUTHORITIES else "generic_fact",
        })
    return tuple(rows)


def _normalize_explicit_project_rule_authority(
    context_pack: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Align selector and packet authority without widening trust.

    Only an already-explicit ``project_rule`` declaration is normalized to the
    packet builder's existing trusted ``source_of_truth`` vocabulary. Ordinary
    Markdown/README sources remain untouched and cannot gain authority here.
    """

    rows: list[dict[str, Any]] = []
    for raw in context_pack:
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        if str(item.get("authority") or "").casefold() == "project_rule":
            item["authority"] = "source_of_truth"
        if str(item.get("repository_authority") or "").casefold() == "project_rule":
            item["repository_authority"] = "source_of_truth"
        rows.append(item)
    return tuple(rows)


def _explicit_mutation_contract(
    question: str,
    required_target_paths: Iterable[str],
    *,
    provenance: str,
):
    contract = build_mutation_intent(question)
    bound = with_explicit_path_targets(contract, required_target_paths, provenance=provenance)
    plan = bound.request_plan
    if bound.operation == "none" and plan is not None and plan.operation != "none":
        bound = replace(bound, operation=plan.operation)
    return bound


def build_action_packet(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Build a packet whose internal fit budget includes projection overhead."""

    question = str(kwargs.get("question") or (args[0] if args else ""))
    required_evidence_paths = tuple(kwargs.get("required_evidence_paths") or ())
    required_target_paths = tuple(kwargs.get("required_target_paths") or ())
    behavioral_required = bool(kwargs.get("behavioral_contract_required"))
    raw_context = tuple(
        item for item in (kwargs.get("context_pack") or ())
        if isinstance(item, Mapping)
    )
    normalized_context = _normalize_explicit_project_rule_authority(raw_context)
    if raw_context:
        kwargs["context_pack"] = normalized_context

    public_requirements = list(kwargs.get("public_requirements") or ())
    if behavioral_required:
        public_requirements.extend(_behavioral_source_fact_contracts(
            required_evidence_paths=required_evidence_paths,
            required_target_paths=required_target_paths,
            context_pack=normalized_context,
        ))
    if public_requirements:
        by_identity: dict[str, Any] = {}
        for row in public_requirements:
            if isinstance(row, Mapping):
                identity = str(row.get("requirement_id") or "") or repr(sorted(row.items()))
            else:
                identity = str(row)
            by_identity.setdefault(identity, row)
        kwargs["public_requirements"] = tuple(by_identity.values())

    if kwargs.get("mutation_intent_contract") is None and required_target_paths:
        kwargs["mutation_intent_contract"] = _explicit_mutation_contract(
            question,
            required_target_paths,
            provenance="explicit_task_contract" if behavioral_required else "explicit_required_target",
        )

    if behavioral_required and "max_tokens" in kwargs:
        requested = max(MIN_ACTION_PACKET_TOKENS, int(kwargs["max_tokens"]))
        if requested > MIN_ACTION_PACKET_TOKENS + PATCH_PROJECTION_RESERVE_TOKENS:
            kwargs["max_tokens"] = requested - PATCH_PROJECTION_RESERVE_TOKENS

    return _build_action_packet_impl(*args, **kwargs)


__all__=[n for n in globals() if not n.startswith("__")]

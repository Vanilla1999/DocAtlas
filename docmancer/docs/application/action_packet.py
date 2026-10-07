from __future__ import annotations

from typing import Any, Iterable, Mapping

from ._action_packet_shared import *  # noqa: F401,F403

from ._action_packet_part01 import *  # noqa: F401,F403

from ._action_packet_part02 import *  # noqa: F401,F403

from ._action_packet_part03 import *  # noqa: F401,F403
from ._action_packet_part03 import build_action_packet as _build_action_packet_impl

from ._action_packet_part04 import *  # noqa: F401,F403


def _explicit_mutation_contract(
    question: str,
    required_target_paths: Iterable[str],
    *,
    provenance: str,
):
    # Required paths declare evidence obligations, not permission or operation.
    contract = MutationIntentContract("none", "unknown", ())
    bound = with_explicit_path_targets(contract, required_target_paths, provenance=provenance)
    return bound


def build_action_packet(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Build a packet preserving explicit requirements and selection budgets."""

    question = str(kwargs.get("question") or (args[0] if args else ""))
    required_target_paths = tuple(kwargs.get("required_target_paths") or ())
    behavioral_required = bool(kwargs.get("behavioral_contract_required"))
    raw_context = tuple(
        item for item in (kwargs.get("context_pack") or ())
        if isinstance(item, Mapping)
    )
    if raw_context:
        kwargs["context_pack"] = raw_context

    public_requirements = list(kwargs.get("public_requirements") or ())
    if public_requirements:
        by_identity: dict[str, Any] = {}
        for row in public_requirements:
            if isinstance(row, Mapping):
                identity = str(row.get("requirement_id") or "") or repr(sorted(row.items()))
            else:
                identity = str(row)
            by_identity.setdefault(identity, row)
        public_requirements = list(by_identity.values())
        kwargs["public_requirements"] = tuple(public_requirements)

    if kwargs.get("mutation_intent_contract") is None and required_target_paths:
        kwargs["mutation_intent_contract"] = _explicit_mutation_contract(
            question,
            required_target_paths,
            provenance="explicit_task_contract" if behavioral_required else "explicit_required_target",
        )

    return _build_action_packet_impl(*args, **kwargs)


__all__=[n for n in globals() if not n.startswith("__")]

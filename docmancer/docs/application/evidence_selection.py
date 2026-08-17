"""Deterministic, provider-free minimal evidence selection.

The selector owns evidence eligibility and fitting.  Formatters receive only a
validated whole-item subset and remain responsible for serialization safety,
not for deciding which source facts are important."""

from __future__ import annotations

from ._evidence_selection_shared import *  # noqa: F401,F403

from ._evidence_selection_part01 import *  # noqa: F401,F403

from ._evidence_selection_part02 import *  # noqa: F401,F403

from ._evidence_selection_part03 import *  # noqa: F401,F403

from ._evidence_selection_part04 import *  # noqa: F401,F403

__all__=[n for n in globals() if not n.startswith("__")]

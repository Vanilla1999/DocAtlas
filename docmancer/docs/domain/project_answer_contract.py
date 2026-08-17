"""Bounded semantic contract for project-documentation answers.

The contract deliberately separates *retrieval hints* from *proof obligations*.
Hints may widen recall, but only a locally valid answer unit can discharge an
obligation.  The public MCP input surface remains unchanged; this module is an
internal, immutable boundary shared by query planning, evidence selection, and
projection validation."""

from __future__ import annotations

from ._project_answer_contract_shared import *  # noqa: F401,F403

from ._project_answer_contract_part01 import *  # noqa: F401,F403

from ._project_answer_contract_part02 import *  # noqa: F401,F403

__all__=[n for n in globals() if not n.startswith("__")]

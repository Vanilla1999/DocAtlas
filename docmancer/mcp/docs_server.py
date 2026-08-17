"""`doc-atlas mcp docs-serve`: stdio MCP server for library documentation."""

from __future__ import annotations

from ._docs_server_shared import *  # noqa: F401,F403

from ._docs_server_part01 import *  # noqa: F401,F403

__all__=[n for n in globals() if not n.startswith("__")]

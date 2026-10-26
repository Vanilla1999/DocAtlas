"""`doc-atlas mcp docs-serve`: stdio MCP server for library documentation."""
from __future__ import annotations

from ._docs_server_shared import *  # noqa: F401,F403
from ._docs_server_part01 import *  # noqa: F401,F403


def serve(config_path=None) -> None:
    """Select the installed host presentation, never from a tool argument."""
    from .native_delivery import active
    if active():
        import asyncio
        from ._docs_server_part01 import create_local_mcp_service
        from .opencode_server import run
        asyncio.run(run(create_local_mcp_service(config_path)))
    else:
        from ._docs_server_part01 import serve as legacy_serve
        legacy_serve(config_path)


__all__ = [n for n in globals() if not n.startswith("__")]

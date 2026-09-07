"""Library documentation registry and MCP service."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docmancer.docs.service import LibraryDocsService

__all__ = ["LibraryDocsService"]


def __getattr__(name: str):
    # Domain imports must not initialize application services or retrieval adapters.
    if name == "LibraryDocsService":
        from docmancer.docs.service import LibraryDocsService

        return LibraryDocsService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

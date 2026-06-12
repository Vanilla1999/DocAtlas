from __future__ import annotations

from filelock import FileLock

from docmancer.docs.resolver import normalize_library_name
from docmancer.mcp import paths


class FilesystemLockGateway:
    def lock_for(self, library_id: str) -> FileLock:
        lock_dir = paths.docmancer_home() / "locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        safe = normalize_library_name(library_id) or "library"
        return FileLock(str(lock_dir / f"docs-{safe}.lock"))

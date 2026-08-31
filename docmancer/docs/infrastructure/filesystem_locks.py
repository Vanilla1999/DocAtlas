from __future__ import annotations

from filelock import FileLock

from docmancer.core.product_identity import ensure_owned_home, resolve_home
from docmancer.docs.resolver import normalize_library_name


class FilesystemLockGateway:
    def lock_for(self, library_id: str) -> FileLock:
        resolution = resolve_home()
        owned_home = ensure_owned_home(resolution.path)
        lock_dir = owned_home / "locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        safe = normalize_library_name(library_id) or "library"
        return FileLock(str(lock_dir / f"docs-{safe}.lock"))

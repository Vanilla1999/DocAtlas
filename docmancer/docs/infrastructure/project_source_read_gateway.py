"""Read-only filesystem/index adapter for source continuations."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
from sqlite3 import Error as IndexReadError

from docmancer.docs.application.source_continuation import SourceReference
from docmancer.docs.project_docs_catalog import read_project_docs_catalog
from docmancer.retrieval.query_planning import metadata_matches_filters


class ProjectSourceReadGateway:
    """Authorize against current catalog and active index before source hydration.

    This first reader supports explicit maintained catalog entries. Discovery-only
    sources and catalog roots need their own exact catalog binding before they can
    be reopened; an existing citation remains useful when reopening is unavailable.
    """

    max_source_bytes = 1024 * 1024

    def __init__(self, store_factory, *, identity_for_root=None):
        self.store_factory = store_factory
        if identity_for_root is None:
            from docmancer.docs.application.project_docs_service import ProjectDocsService
            identity_for_root = ProjectDocsService._repository_identity
        self.identity_for_root = identity_for_root

    def authorize(self, reference: SourceReference) -> str | None:
        root = Path(reference.project_root)
        relative = PurePosixPath(reference.path)
        if (not root.is_absolute() or root.resolve() != root
            or relative.is_absolute() or '..' in relative.parts
            or not relative.parts or '\\' in reference.path
            or relative.suffix.lower() not in {'.md', '.markdown', '.txt', '.rst'}):
            return 'source_unavailable'
        try:
            if self.identity_for_root(root) != reference.project_identity:
                return 'source_unavailable'
            catalog = read_project_docs_catalog(root)
            if not catalog.present or not catalog.valid:
                return 'source_unavailable'
            entry = next((entry for entry in catalog.entries if entry.path == reference.path), None)
            if entry is None:
                return 'source_unavailable'
            digest = 'sha256:' + hashlib.sha256(json.dumps(
                asdict(entry), ensure_ascii=False, sort_keys=True, separators=(',', ':'),
            ).encode()).hexdigest()
            if (digest != reference.catalog_entry_hash or entry.status != 'active'
                or entry.authority not in {'source_of_truth', 'supporting'}):
                return 'source_unavailable'
            store = self.store_factory()
            source = str(root / reference.path)
            metadata = store.source_metadata(source)
            if not isinstance(metadata, dict):
                return 'source_unavailable'
            if metadata.get('project_doc_content_hash') != reference.content_sha256:
                return 'source_changed'
            filters = {
                'project_path': str(root), 'project_identity': reference.project_identity,
                'source_class': 'project_file', 'doc_scope': reference.scope,
                'authority': reference.authority, 'lifecycle_status': 'active',
                'project_doc_path': reference.path,
            }
            if reference.module_path:
                filters['module_path'] = reference.module_path
            # Active-generation metadata is the same pre-hydration boundary used
            # by retrieval. A sources-table row alone cannot establish activity.
            ids = store.section_ids_for_source(source)
            if not ids:
                return 'source_unavailable'
            active = store.section_filter_metadata_for(ids[:1]).get(ids[0])
            if not active or not metadata_matches_filters(active, filters, source=source):
                return 'source_unavailable'
            if active.get('project_doc_content_hash') != reference.content_sha256:
                return 'source_changed'
            if active.get('project_doc_catalog_entry_hash') != digest:
                return 'source_unavailable'
            return None
        except (OSError, ValueError, RuntimeError, AttributeError, IndexReadError):
            return 'source_unavailable'

    def read_snapshot(self, reference: SourceReference) -> bytes:
        """Open each path component without following symlinks, then bound bytes."""
        if not hasattr(os, 'O_NOFOLLOW') or os.open not in os.supports_dir_fd:
            raise OSError('safe source opening unavailable on this platform')
        root = Path(reference.project_root)
        relative = PurePosixPath(reference.path)
        parts = (*root.parts[1:], *relative.parts)
        if (not root.is_absolute() or relative.is_absolute() or not relative.parts
            or '\\' in reference.path or any(part in {'.', '..', ''} for part in parts)):
            raise ValueError('invalid source path')
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        parent = os.open('/', directory_flags)
        try:
            for component in parts[:-1]:
                child = os.open(component, directory_flags, dir_fd=parent)
                os.close(parent)
                parent = child
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            with os.fdopen(fd, 'rb') as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > self.max_source_bytes:
                    raise ValueError('source is not a bounded regular file')
                raw = source.read(self.max_source_bytes + 1)
                if len(raw) > self.max_source_bytes:
                    raise ValueError('source grew beyond byte budget')
                return raw
        finally:
            os.close(parent)

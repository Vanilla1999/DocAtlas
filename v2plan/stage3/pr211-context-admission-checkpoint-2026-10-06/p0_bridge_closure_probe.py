"""Inspect real facade wrappers and exercise synchronization without business calls."""
from __future__ import annotations

import importlib
import inspect
import json
import sys


TARGETS = (
    ("docmancer.core.sqlite_store", "SQLiteStore", "_BOILERPLATE_KEYWORDS"),
    ("docmancer.connectors.fetchers.web", "WebFetcher", "re"),
    ("docmancer.retrieval.dispatch", "RetrievalDispatcher", "re"),
    ("docmancer.docs.application.patch_constraints_service", "PatchConstraintsService", "PHRASE_ALIASES"),
    ("docmancer.docs.application.project_docs_service", "ProjectDocsService", "re"),
    ("docmancer.docs.application.project_context_service", "ProjectContextService", "LOW_TRUST_QUERY_TERMS"),
    ("docmancer.docs.application.unified_context_service", "UnifiedDocsContextService", "_PATCH_TASK_TERMS"),
    ("docmancer.docs.application.patch_review_service", "PatchReviewService", "LOW_VALUE_SYMBOLS"),
    ("docmancer.docs.application.library_docs_service", "LibraryDocsApplicationService", "re"),
)


def main() -> None:
    rows = []
    for module_name, class_name, global_name in TARGETS:
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
        wrappers = []
        for name, descriptor in vars(cls).items():
            value = descriptor.__func__ if isinstance(descriptor, (staticmethod, classmethod)) else descriptor
            if inspect.isfunction(value) and getattr(value, "__docatlas_shard_bridge__", False):
                original = inspect.unwrap(value)
                wrappers.append({"name": name, "wrapper_globals_module": value.__globals__.get("__name__"),
                                 "original_module": original.__module__, "original_qualname": original.__qualname__,
                                 "source_line": original.__code__.co_firstlineno})
        syncs = [value for key, value in vars(module).items() if key.startswith("__docatlas_shard_sync_")]
        assert wrappers and syncs
        sync = syncs[0]
        closure = inspect.getclosurevars(sync).nonlocals
        shards = [sys.modules[name] for name in closure["shard_names"]]
        if global_name not in vars(module):
            global_name = next(name for name in sorted(vars(module))
                               if not name.startswith("_") and name != class_name
                               and any(name in vars(shard) for shard in shards))
        assert global_name in vars(module), (module_name, global_name)
        affected = [shard for shard in shards if global_name in vars(shard)]
        assert affected
        saved = [(module, vars(module)[global_name]), *[(shard, vars(shard)[global_name]) for shard in affected]]
        sentinel = object()
        try:
            vars(module)[global_name] = sentinel
            sync()
            propagated = all(vars(shard)[global_name] is sentinel for shard in affected)
            assert propagated
        finally:
            for owner, value in saved:
                vars(owner)[global_name] = value
        assert all(vars(owner)[global_name] is value for owner, value in saved)
        rows.append({"public_module": module_name, "class": class_name, "wrappers": wrappers,
                     "shards": [shard.__name__ for shard in shards], "tested_global": global_name,
                     "propagated_to": [shard.__name__ for shard in affected],
                     "synchronization_verified": propagated, "restored": True})
    print(json.dumps({"schema": "p0-real-class-bridge-closure-v1", "rows": rows,
                      "limitations": "Synchronization closures invoked directly; business methods not invoked. This proves concrete facade-to-shard override reachability, not all runtime caller paths or semantic quality."}, indent=2))


if __name__ == "__main__":
    main()

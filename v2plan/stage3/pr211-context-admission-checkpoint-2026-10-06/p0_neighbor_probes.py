"""Diagnostic read-only probes via public facades; no source scan or network."""
from __future__ import annotations

import hashlib
import inspect
import json
import platform
from pathlib import Path

from docmancer.docs.application.patch_constraints_service import PatchConstraintsService
from docmancer.docs.application.patch_review_service import PatchReviewService
from docmancer.docs.discovery_candidates import discovery_candidates_for


def main() -> None:
    questions = ["закрыть меню", "close menu", "быстрая информация", "scan", "скан"]
    helpers = [PatchConstraintsService._task_terms, PatchReviewService._task_symbol_tokens]
    paths = ["docmancer/_internal/shard_compat.py",
             "docmancer/docs/application/_patch_constraints_service_part02.py",
             "docmancer/docs/application/_patch_review_service_part02.py",
             "docmancer/docs/discovery_candidates.py"]
    result = {
        "schema": "p0-neighbor-probes-v1", "python": platform.python_version(),
        "source_hashes": {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
        "helper_origins": [{"name": f.__qualname__, "bridge": bool(getattr(f, "__docatlas_shard_bridge__", False)),
                            "wrapper_globals": f.__globals__["__name__"],
                            "implementation": inspect.unwrap(f).__globals__["__name__"]} for f in helpers],
        "task_cases": [{"question": q, "constraint_terms": PatchConstraintsService._task_terms(q),
                        "review_terms": sorted(PatchReviewService._task_symbol_tokens(q))} for q in questions],
        "discovery_cases": [{"library": name, "ecosystem": eco,
                             "candidates": discovery_candidates_for(name, eco)}
                            for name, eco in [("fastapi", "python"), ("FASTAPI", "python"),
                                              ("fastapi server", "python"), ("unknown-library", "python"),
                                              ("riverpod", "flutter")]],
        "limitations": "Synthetic helper observations, not end-to-end quality or approval of registry authority.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

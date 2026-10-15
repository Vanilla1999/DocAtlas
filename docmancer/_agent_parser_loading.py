"""Lazy parser-class loading shared by the high-level agent."""
from __future__ import annotations

import importlib


def _import_class(dotted_path: str) -> type:
    module_path, class_name = dotted_path.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)

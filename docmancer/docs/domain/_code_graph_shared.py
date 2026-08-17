from __future__ import annotations

import posixpath
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from hashlib import sha1
from pathlib import Path
from typing import Any, Sequence

from docmancer.docs.domain.source_map import collect_project_source_facts

_FILE_NODE_KIND = "file"
_SYMBOL_NODE_KIND = "symbol"
_KNOWN_EDGE_KINDS = {
    "contains",
    "imports",
    "exports",
    "references",
    "unresolved_import",
    "unresolved_export",
    "unresolved_reference",
}
_CONFIDENCE_SCORES = {
    "exact": 1.0,
    "parser": 0.9,
    "regex": 0.7,
    "heuristic": 0.45,
    "unresolved": 0.1,
}
_PY_EXTENSIONS = (".py", "/__init__.py")
_DART_EXTENSIONS = (".dart",)
_JS_TS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx", "/index.js", "/index.jsx")
_CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z]{2})(?=[A-Z][a-z])")

__all__=[n for n in globals() if not n.startswith('__')]

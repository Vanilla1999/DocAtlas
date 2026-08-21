#!/usr/bin/env python3
"""Execute the reviewed materializer without its obsolete regex cleanup step."""
from pathlib import Path

path = Path(__file__).with_name("_materialize_recoverable_docs_failures.py")
source = path.read_text(encoding="utf-8")
start = source.index("# Fix the generated exact-rephrase marker.")
end = source.index("# Exact-document recovery reuses canonical stored sections")
source = source[:start] + source[end:]
exec(compile(source, str(path), "exec"), {"__name__": "__main__", "__file__": str(path)})

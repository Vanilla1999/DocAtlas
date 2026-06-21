from __future__ import annotations

from docmancer.docs.resolver import normalize_lookup_key


_KNOWN_DISCOVERY_CANDIDATES = {
    ("python", "mcp"): [
        {
            "library": "mcp",
            "ecosystem": "python",
            "name": "Model Context Protocol Python SDK",
            "docs_url": "https://github.com/modelcontextprotocol/python-sdk",
            "confidence": "medium",
            "why": "candidate matched python ecosystem and mcp query",
        }
    ],
    ("dart", "riverpod"): [
        {
            "library": "riverpod",
            "ecosystem": "dart",
            "name": "Riverpod Dart API docs",
            "docs_url": "https://pub.dev/documentation/riverpod/latest/",
            "confidence": "medium",
            "why": "candidate matched dart ecosystem and riverpod query",
        }
    ],
    ("dart", "flutter_riverpod"): [
        {
            "library": "flutter_riverpod",
            "ecosystem": "dart",
            "name": "Flutter Riverpod API docs",
            "docs_url": "https://pub.dev/documentation/flutter_riverpod/latest/",
            "confidence": "medium",
            "why": "candidate matched dart ecosystem and flutter_riverpod query",
        }
    ],
    ("python", "fastapi"): [
        {"library": "fastapi", "ecosystem": "python", "name": "FastAPI documentation", "docs_url": "https://fastapi.tiangolo.com/", "confidence": "high", "why": "candidate matched python ecosystem and fastapi query"}
    ],
    ("python", "pydantic"): [
        {"library": "pydantic", "ecosystem": "python", "name": "Pydantic documentation", "docs_url": "https://docs.pydantic.dev/latest/", "confidence": "high", "why": "candidate matched python ecosystem and pydantic query"}
    ],
    ("python", "httpx"): [
        {"library": "httpx", "ecosystem": "python", "name": "HTTPX documentation", "docs_url": "https://www.python-httpx.org/", "confidence": "high", "why": "candidate matched python ecosystem and httpx query"}
    ],
}


def discovery_candidates_for(library: str, ecosystem: str | None) -> list[dict]:
    normalized_library = normalize_lookup_key(library)
    normalized_ecosystem = normalize_lookup_key(ecosystem or "") if ecosystem else None
    keys: list[tuple[str, str]] = []
    if normalized_ecosystem:
        keys.append((normalized_ecosystem, normalized_library))
        if normalized_ecosystem == "pub":
            keys.append(("dart", normalized_library))
    else:
        keys.extend(key for key in _KNOWN_DISCOVERY_CANDIDATES if key[1] == normalized_library)
    candidates: list[dict] = []
    for key in keys:
        candidates.extend(dict(item) for item in _KNOWN_DISCOVERY_CANDIDATES.get(key, []))
    return candidates

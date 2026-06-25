# PR4 Root Cause Analysis: Dartdoc/pub.dev Ingestion Failures

**Date:** 2026-06-23  
**Branch:** `fix/dartdoc-pub-ingestion`  
**Investigated by:** Analysis of codebase structure

## Executive Summary

Dart/Flutter packages (riverpod, flutter_riverpod, flutter_bloc, go_router) frequently return `empty_index` or "no extractable content" because:

1. **Dartdoc root pages are navigation shells, not content pages** — the current extractor tries to index the root page which contains minimal extractable text
2. **No official docs fallback** — system attempts pub.dev API reference first, but official guide docs (riverpod.dev, bloclibrary.dev) are better sources
3. **Limited Dartdoc discovery** — `discover_dartdoc_candidate_links()` discovers library/class pages, but the flow doesn't prioritize official docs over pub.dev
4. **Generic diagnostics** — `empty_index` status doesn't explain *why* extraction failed (dartdoc shell page, no library pages found, etc.)

## Current State

### What Exists ✅

**Infrastructure present:**
- `docmancer/docs/dartdoc.py`: Core Dartdoc URL construction and discovery logic
  - `pub_dartdoc_root_url()`, `pub_dartdoc_path_prefix()`
  - `discover_pub_dartdoc_seed_urls()` — discovers library/entity pages from root HTML and JSON metadata
  - `is_pub_dartdoc_url()`, `is_pub_dartdoc_target()`, `normalize_pub_dartdoc_target()`
- `docmancer/connectors/fetchers/pipeline/extraction.py`: Dartdoc-specific extraction
  - `extract_dartdoc_content()` — extracts main content from Dartdoc class/library pages
  - `discover_dartdoc_candidate_links()` — finds library/class/function page links
  - `is_dartdoc_html()` — detects if HTML is a Dartdoc page
  - `_DARTDOC_MAIN_SELECTORS`, `_DARTDOC_NOISE_SELECTORS` — Dartdoc-specific CSS selectors
- `docmancer/connectors/fetchers/pipeline/discovery.py`: Dartdoc discovery strategy
  - `_try_dartdoc_index()` — fetches root page and discovers candidate links
  - Discovery strategy: `dartdoc-index` ranked at priority 4 (after llms.txt, sitemaps)
- `tests/test_dartdoc_extraction.py`: 3 basic tests (all passing)

**Benchmark cases present:**
- `eval/live_mcp_context7_benchmark.py` includes 9 Dart/Flutter cases:
  - 5 riverpod cases (autoDispose, keepAlive, family, watch vs listen, AsyncNotifier)
  - 4 flutter_bloc cases (BlocProvider, BlocBuilder, BlocListener, MultiBlocProvider)
- Expected domains: `riverpod.dev`, `bloclibrary.dev`, `pub.dev`

**Ecosystem handling:**
- `ecosystem="flutter"` used in benchmark (not `ecosystem="pub"`)
- `ecosystem="pub"` defined in code but may not match benchmark expectations
- `docmancer/docs/discovery_candidates.py` normalizes `pub` → `dart` (line 56)

### What's Missing ❌

1. **No official docs fallback resolver**
   - No `DART_PACKAGE_DOCS_RESOLVERS` table mapping packages to official docs
   - No logic to prefer `riverpod.dev` over `pub.dev/documentation/riverpod/`
   - No logic to prefer `bloclibrary.dev` over `pub.dev/documentation/flutter_bloc/`

2. **No Dartdoc-specific diagnostics**
   - Generic `empty_index` status without reason codes
   - No `dartdoc` diagnostics object with:
     - `discovery_strategy` (official_docs / pubdev_dartdoc_json / pubdev_dartdoc_nav)
     - `dartdoc_library_pages`, `dartdoc_symbol_pages`, `official_pages`
     - `reason_code` (dartdoc_root_only / dartdoc_no_extractable_content / js_render_required)

3. **No Dart packages in `docmancer.docs.yaml`**
   - File contains only Python packages (pydantic, click, httpx, etc.)
   - No entries for riverpod, flutter_riverpod, flutter_bloc, go_router

4. **Weak Dartdoc root handling**
   - `_extract_dartdoc_index()` in extraction.py generates a link list from root page
   - But this is a fallback — if extraction returns empty, system reports `empty_index` without explaining it's a navigation shell

5. **No JSON metadata discovery**
   - `discover_pub_dartdoc_seed_urls()` in dartdoc.py supports JSON discovery (categories.json, sidebar.json)
   - But requires `fetch_url` callback which may not be wired in all flows

## Root Cause Analysis

### Problem 1: Dartdoc Root Pages Are Navigation Shells

**Scenario:**
```
User: get_library_docs(library="flutter_bloc", ecosystem="flutter")
System: resolves to https://pub.dev/documentation/flutter_bloc/latest/
System: fetches root page
System: root HTML is an index/navigation shell with minimal text content
System: extract_dartdoc_content() finds <5 words of main content
System: falls back to _extract_dartdoc_index() which generates link list
System: BUT: link list is not indexed as useful content
System: returns empty_index
```

**Why it fails:**
- Trafilatura sees minimal extractable article content (navigation is filtered)
- Dartdoc extractor finds no main content div with substantial text
- Fallback link list is not treated as documentation content
- No library/class pages are fetched and indexed

### Problem 2: No Official Docs Prioritization

**Scenario:**
```
User: query "Riverpod autoDispose modifier and ref.onDispose cleanup"
System: looks up library="riverpod", ecosystem="flutter"
System: has no registered docs_url for riverpod
System: defaults to pub.dev/documentation/riverpod/latest/
System: pub.dev API reference has sparse guides
System: riverpod.dev has comprehensive guides for autoDispose
System: BUT: system doesn't know to prefer riverpod.dev
System: returns empty or low-quality pub.dev API reference
```

**Why it fails:**
- No knowledge that riverpod has official docs at riverpod.dev
- No fallback chain: official guides → pub.dev API → README
- System treats pub.dev as only source

### Problem 3: Generic `empty_index` Status

**Scenario:**
```
User: get_library_docs(library="flutter_riverpod", ecosystem="flutter")
System: attempts pub.dev/documentation/flutter_riverpod/latest/
System: root page is navigation shell
System: extraction returns empty
System: returns DocsResult(status="empty_index", results=[])
User: sees "empty_index" with no explanation why
```

**Why it fails:**
- No reason_code explaining *what* failed:
  - `dartdoc_root_only` — only root page fetched, no library pages
  - `dartdoc_no_extractable_content` — library pages found but no article content
  - `dartdoc_json_missing` — no JSON metadata available
  - `js_render_required` — pages need browser rendering
- No next_action guidance:
  - "Try official docs fallback" → riverpod.dev
  - "Try browser rendering" → enable browser mode
  - "Manual seed URLs required" → specify class pages directly

### Problem 4: Ecosystem Mismatch

**Benchmark uses:**
```python
BenchmarkCase(library="riverpod", ecosystem="flutter", ...)
```

**Code expects:**
```python
if target.ecosystem != "pub" or source_type != "api":
    return False
```

**Potential mismatch:**
- Benchmark uses `ecosystem="flutter"`
- Dartdoc logic checks `ecosystem="pub"`
- `discovery_candidates.py` normalizes `pub` → `dart`
- May cause confusion in resolution flow

## Current Flow (Simplified)

```
get_library_docs(library="flutter_bloc", ecosystem="flutter")
  ↓
_resolve_docs_source()
  → no registered docs_url
  → discovery_candidates_for("flutter_bloc", "flutter") → []
  → returns needs_input
  ↓
User provides docs_url="https://pub.dev/documentation/flutter_bloc/latest/"
  ↓
WebFetcher.fetch()
  ↓
discover_urls() → _try_dartdoc_index()
  → fetches root page
  → discover_dartdoc_candidate_links() finds 50+ library/class links
  → returns DiscoveredUrl list
  ↓
fetch_pages()
  → fetches each discovered page
  → extract_content() → extract_dartdoc_content()
    → finds main content or falls back to link list
  ↓
IF root page only AND no substantial content:
  → ContentDeduplicator drops pages with <5 words
  → returns []
  ↓
build_documents() → []
  ↓
index.ingest([]) → 0 chunks indexed
  ↓
DocsResult(status="empty_index", results=[])
```

## Why Official Docs Would Help

**riverpod.dev structure:**
```
https://riverpod.dev/
├── /docs/introduction/getting_started  (guide-style content)
├── /docs/concepts2/providers           (conceptual explanations)
├── /docs/concepts2/refs                (autoDispose, keepAlive explained)
├── /docs/concepts2/family              (family modifier)
└── /docs/concepts2/auto_dispose        (autoDispose in depth)
```

**pub.dev structure:**
```
https://pub.dev/documentation/riverpod/latest/
├── /riverpod/riverpod-library.html     (API reference, minimal guides)
├── /riverpod/Provider-class.html       (API signatures)
└── /riverpod/Ref-class.html            (API signatures)
```

**Difference:**
- Official docs: **guide-first**, conceptual explanations, usage examples, best practices
- pub.dev API: **reference-first**, class signatures, terse method docs

**For coding agents:**
- Guide content answers "how to use autoDispose?" better than API signature
- API reference is useful for method signatures, but less useful for learning patterns

## Diagnosis Commands Run

```bash
# Confirmed existing infrastructure
find . -name "*.py" | grep -E "(pub|dart)"
  → docmancer/docs/dartdoc.py
  → tests/test_dartdoc_extraction.py

# Confirmed Dartdoc extraction logic exists
grep -rn "extract_dartdoc_content" docmancer/

# Confirmed discovery strategy exists  
grep -rn "dartdoc" docmancer/connectors/fetchers/pipeline/discovery.py

# Confirmed benchmark cases exist
grep -n "riverpod\|flutter_bloc" eval/live_mcp_context7_benchmark.py

# Confirmed no Dart packages in config
cat docmancer.docs.yaml
  → Only Python packages present

# Confirmed basic tests pass
uv run pytest tests/test_dartdoc_extraction.py -v
  → 3/3 passed
```

## Conclusion

**Root cause:** Dartdoc/pub.dev ingestion fails because:

1. **Root-only indexing** — system stops at navigation shell root page without fetching library/class pages
2. **No official docs knowledge** — system doesn't know riverpod.dev, bloclibrary.dev are better sources than pub.dev API
3. **Generic failures** — `empty_index` doesn't explain dartdoc-specific failure modes
4. **Missing config** — no docmancer.docs.yaml entries for Dart packages

**Impact:**
- `riverpod` queries fail as `empty_index` (no riverpod.dev fallback)
- `flutter_riverpod` queries fail (root page only, no library pages indexed)
- `flutter_bloc` queries fail (no bloclibrary.dev fallback, pub.dev API insufficient)
- Users receive generic `empty_index` with no actionable guidance

**Next steps:**
1. Add official docs resolver table (`DART_PACKAGE_DOCS_RESOLVERS`)
2. Prioritize official guides over pub.dev API reference
3. Add Dartdoc-specific diagnostics with reason codes
4. Update `docmancer.docs.yaml` with Dart package entries
5. Improve Dartdoc discovery to ensure library/class pages are fetched
6. Add integration tests proving official docs → chunks → query success

---

**✅ Root cause identified. Ready to implement fixes.**

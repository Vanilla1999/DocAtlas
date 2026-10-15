"""Check installed SDK against an explicitly prepared isolated real index."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from receipts import database, files, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import docmancer
    from docmancer import DocmancerClient
    assert Path(docmancer.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    fixture = json.loads(args.fixture.read_text())
    project, storage = Path(fixture["project"]), Path(fixture["storage_path"])
    documents = fixture["documents"]
    for relative, text in documents.items():
        assert (project / relative).read_bytes() == text.encode()
    sdk = DocmancerClient(db_path=str(storage))
    before = database(storage), files(project)
    started = time.perf_counter()
    small = sdk.get_chunks("Observatory", limit=1, budget=100)
    tight = sdk.get_context("Observatory", limit=1, budget=100)
    wide = sdk.get_chunks("Observatory", limit=20, budget=12000)
    text = sdk.get_context("Observatory", limit=20, budget=12000)
    bare = sdk.get_chunks("Photograph", limit=20, budget=12000, expand="none")
    adjacent = sdk.get_chunks("Photograph", limit=20, budget=12000, expand="adjacent")
    page = sdk.get_chunks("Photograph", limit=20, budget=12000, expand="page")
    expanded_text = sdk.get_context("Photograph", limit=20, budget=600, expand="adjacent")
    zero_chunks = sdk.get_chunks("Observatory", limit=0, budget=0)
    zero_text = sdk.get_context("Observatory", limit=0, budget=0)
    assert len(small) == 1 and sum(c.metadata["token_estimate"] for c in small) <= 100
    assert all(c.metadata["docmancer_tokens"] <= 100 for c in small)
    assert (len(tight) + 3) // 4 <= 100
    assert len(wide) == 3 and (len(text) + 3) // 4 <= 12000
    for relative in ("docs/packing.md", "docs/transport.md", "docs/storage.md"):
        assert documents[relative] in text
    fact = "Complete every dispatch checklist step before handing over an optical case."
    assert not any(fact in c.text for c in bare)
    assert any(fact in c.text for c in adjacent)
    assert any(fact in c.text for c in page)
    assert fact in expanded_text and (len(expanded_text) + 3) // 4 <= 600
    assert not zero_chunks and zero_text == ""
    for chunk in [*small, *wide, *bare, *adjacent, *page]:
        raw = documents[Path(chunk.source).relative_to(project).as_posix()]
        start, end = chunk.metadata["char_span"]
        assert raw[start:end] == chunk.text
        assert chunk.metadata["content_hash"] == sha(chunk.text.encode())
        assert chunk.metadata["source_content_hash"] == sha(raw.encode())
        assert chunk.metadata["doc_scope"] == "project"
        assert chunk.metadata["generation_id"] == fixture["generation_id"]
    assert before == (database(storage), files(project))
    save(args.output, dict(status="PASS", boundary="installed SDK, source-tree prepared SQLite",
         origin=docmancer.__file__, calls=10, model_calls=0,
         seconds=time.perf_counter()-started, small_count=len(small), tight_text=tight,
         wide_text=text, expanded_text=expanded_text, adjacent=[c.model_dump() for c in adjacent],
         page=[c.model_dump() for c in page], state_unchanged=True))


if __name__ == "__main__":
    main()

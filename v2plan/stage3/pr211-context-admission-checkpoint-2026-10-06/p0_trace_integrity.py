"""Check observed trace integrity without redefining quality gates."""
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path


BASE = Path("v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06")


def main() -> None:
    rows = []
    for path in sorted((BASE / "archives").glob("p0-stages-*.json.gz")):
        data = json.loads(gzip.decompress(path.read_bytes()))
        blobs = data["text_blobs"]
        failures = []
        references = 0

        def restore(value):
            if isinstance(value, dict):
                if set(value) == {"text_blob_sha256"}:
                    return blobs.get(value["text_blob_sha256"])
                return {key: restore(item) for key, item in value.items()}
            if isinstance(value, list):
                return [restore(item) for item in value]
            return value

        def walk(value):
            nonlocal references
            if isinstance(value, dict):
                if "text_blob_sha256" in value:
                    references += 1
                    digest = value["text_blob_sha256"]
                    if digest not in blobs:
                        failures.append("missing text blob:" + digest)
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(data["calls"])
        for digest, text in blobs.items():
            if hashlib.sha256(text.encode()).hexdigest() != digest:
                failures.append("incorrect text hash:" + digest)
        events = Counter()
        final_sources = 0
        citation_checks = []
        empty_stage_returns = Counter()
        index_checks = []
        for database in data.get("actual_sqlite_index_manifests", []):
            for table in database["tables"]:
                material = json.dumps(table["rows"], sort_keys=True, ensure_ascii=False).encode()
                if hashlib.sha256(material).hexdigest() != table["rows_sha256"]:
                    failures.append("index table rows hash mismatch:" + table["name"])
                if table["name"] == "generation_sources":
                    for source in table["rows"]:
                        content = source["content"]
                        raw_hash = hashlib.sha256(content.encode()).hexdigest()
                        source_path = Path(source["source"])
                        index_checks.append({"path": str(source_path), "indexed_content_sha256": raw_hash,
                                             "stored_hash_matches": raw_hash == source["content_hash"],
                                             "file_bytes_match": source_path.is_file() and source_path.read_bytes() == content.encode()})
        for call in data["calls"]:
            for event in call["stage_events"]:
                events[event["function"]] += 1
                if event["result"] == {}:
                    empty_stage_returns[event["function"]] += 1
            snapshot = call["final_snapshot"]
            for source in call["final_payload"].get("sources", []):
                final_sources += 1
                if source.get("evidence_id") not in snapshot:
                    failures.append("final evidence_id absent from snapshot")
                if not source.get("content_sha256"):
                    failures.append("final source lacks content hash")
                snippet = source.get("snippet", "")
                source_path = Path(source.get("path_or_url", ""))
                start, end = source.get("line_start"), source.get("line_end")
                check = {"path": str(source_path), "evidence_id": source.get("evidence_id"),
                         "snippet_sha256": hashlib.sha256(snippet.encode()).hexdigest(),
                         "source_digest_matches": call.get("source_digest_checks", {}).get(source.get("evidence_id")),
                         "projected_row_matches_snapshot": source == restore(snapshot.get(source.get("evidence_id"), {}).get("projected_source"))}
                if source_path.is_file() and isinstance(start, int) and isinstance(end, int):
                    lines = source_path.read_text().splitlines()
                    excerpt = "\n".join(lines[max(0, start - 1):end])
                    check["snippet_within_declared_lines"] = snippet.strip() in excerpt
                else:
                    check["snippet_within_declared_lines"] = None
                citation_checks.append(check)
                if not check["source_digest_matches"] or not check["projected_row_matches_snapshot"] or check["snippet_within_declared_lines"] is not True:
                    failures.append("citation integrity failed:" + str(source.get("evidence_id")))
        metrics = data["report"].get("metrics", {})
        rows.append({"path": str(path.relative_to(BASE)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "calls": len(data["calls"]), "events": dict(events), "text_blob_references": references,
                     "unique_text_blobs": len(blobs), "final_sources": final_sources,
                     "empty_stage_returns": dict(empty_stage_returns), "integrity_failures": failures,
                     "citation_checks": citation_checks,
                     "indexed_source_checks": index_checks,
                     "useful_result_count": metrics.get("useful_result_count"),
                     "source_budget_violations": metrics.get("source_budget_violation_count"),
                     "token_budget_violations": metrics.get("token_budget_violation_count"),
                     "report_errors": data["report"].get("errors", []), "socket_attempts": data["socket_attempts"]})
    print(json.dumps({"schema": "p0-trace-integrity-v1", "rows": rows,
                      "limitations": "content_sha256 binds canonical original source material, not the cropped snippet alone. Source digest is checked before trace compaction. Line checks use current files and must be interpreted with pinned source hashes. This does not prove semantic relevance or complete profiler coverage."}, ensure_ascii=False, indent=2))
    if any(row["integrity_failures"] for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

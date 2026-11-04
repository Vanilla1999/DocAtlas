"""Evaluate saved pilot artifacts independently of production retrieval code.

Run with system Python: python3 review_results.py --artifacts /tmp/opencode/acq-pilot
No product calls, indexing, model inference or network requests are performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean

from review_delivery import review


def evaluate(root):
    oracle_path = Path(__file__).with_name("oracle.json")
    oracle = json.loads(oracle_path.read_text())
    results = []
    for corpus in ("L0", "L2"):
        for variant in ("v0", "v5"):
            for question in oracle["questions"]:
                stem = f'{corpus}-{variant}-{question["id"]}'
                metrics = json.loads((root / f"{stem}.metrics.json").read_text())
                project = Path(metrics["arguments"]["project_path"])
                delivery = review(project, oracle, question["id"],
                                  json.loads((root / f"{stem}.payload.json").read_text()))
                acquisition = json.loads((root / "acquire-stage" / f"acquired-{stem}.json").read_text())
                acquired = {}
                for fact in question["facts"]:
                    hits = []
                    for lane in acquisition["lanes"]:
                        for rank, row in enumerate(lane["rows"], 1):
                            md = row["metadata"]
                            if md.get("project_doc_path") != fact["path"] or fact["quote"] not in row["text"]:
                                continue
                            source = (project / fact["path"]).read_bytes()
                            assert "sha256:" + hashlib.sha256(source).hexdigest() == md["project_doc_content_hash"]
                            start, end = md["line_span"]
                            lines = source.decode().splitlines(keepends=True)
                            assert 1 <= start <= end <= len(lines)
                            assert row["text"] in "".join(lines[start - 1:end])
                            hits.append({"lane": lane["name"], "rank": rank,
                                         "section_id": md["section_id"]})
                    acquired[fact["id"]] = hits
                checks = metrics["source_checks"]
                assert all("error" not in row and all(row.get(key) is True for key in (
                    "identity_ok", "scope_ok", "authority_ok", "version_ok", "span_text_ok"
                )) for row in checks)
                results.append({
                    "corpus": corpus, "variant": variant, "question": question["id"],
                    "acquired": acquired, "delivery": delivery,
                    "stdio_seconds": metrics["seconds"], "temperature": metrics["temperature"],
                    "tokens": metrics["raw_cl100k_tokens"],
                    "acquire_seconds": sum(lane["seconds"] for lane in acquisition["lanes"]),
                    "union_count": len(acquisition["ordered_union_section_ids"]),
                })
    summaries = []
    for corpus in ("L0", "L2"):
        for variant in ("v0", "v5"):
            group = [x for x in results if x["corpus"] == corpus and x["variant"] == variant]
            summaries.append({
                "corpus": corpus, "variant": variant,
                "acquired_criteria": sum(bool(hits) for x in group for hits in x["acquired"].values()),
                "delivered_criteria": sum(f["canonical_quote_delivered"] for x in group for f in x["delivery"]["facts"]),
                "total_criteria": 9, "source_rows": sum(x["delivery"]["source_rows"] for x in group),
                "tokens": sum(x["tokens"] for x in group),
                "mean_stdio_seconds": mean(x["stdio_seconds"] for x in group),
                "mean_acquire_seconds": mean(x["acquire_seconds"] for x in group),
            })
    return {"oracle_sha256": hashlib.sha256(oracle_path.read_bytes()).hexdigest(),
            "summaries": summaries, "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.artifacts), ensure_ascii=False, indent=2))

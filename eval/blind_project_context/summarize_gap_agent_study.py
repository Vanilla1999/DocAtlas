"""Join immutable session accounting with the separately recorded manual rubric."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    runs = json.loads((args.out / "analysis.json").read_text())
    manual = json.loads((args.out / "manual-review.json").read_text())["answers"]
    summary = {}
    for arm in sorted({r["arm"] for r in runs}):
        group = [r for r in runs if r["arm"] == arm]
        facts = [manual[f"{r['corpus']}/{arm}/{r['case']}"]["facts"] for r in group]
        calls = [[c.get("input", {}) for f in r["flow"] for c in f["calls"]
                  if c["tool"] == "docatlas.get_docs_context"] for r in group]
        s = {"sessions": len(group), "facts": sum(map(sum, facts)), "fact_total": sum(map(len, facts)),
             "complete": sum(all(f) for f in facts),
             "mean_usage": {k: statistics.mean(r["usage"].get(k, 0) for r in group) for k in group[0]["usage"]},
             "median_input": statistics.median(r["usage"]["input_with_cache"] for r in group),
             "retrieval_calls": sum(map(len, calls)),
             "first_translation_sessions": sum(bool(cs and cs[0].get("search_question")) for cs in calls),
             "literal_evidence": sum(sum(r["literal_evidence"].values()) for r in group),
             "source_anomalies": sum(len(r["source_anomalies"]) for r in group),
             "unknown_cited_refs": sum(len(r["unknown_cited_refs"]) for r in group),
             "errors": sum(len(r["errors"]) for r in group),
             "code_errors": sum(f["code_error"] for r in group for f in r["flow"]),
             "tool_truncations": sum(f["truncated"] for r in group for f in r["flow"]),
             "invalid_continuations": sum(not all(c[k] for k in ("issued", "unchanged_arguments", "issued_next_portion"))
                 for r in group for c in r["continuation_checks"])}
        for name, predicate in (
            ("focused", lambda c: bool(c.get("source_path"))),
            ("continuation", lambda c: c.get("portion", 1) > 1),
            ("lookup", lambda c: bool(c.get("lookup_queries"))),
            ("translation", lambda c: bool(c.get("search_question"))),
        ):
            s[name + "_sessions"] = sum(any(predicate(c) for c in cs) for cs in calls)
            s[name + "_calls"] = sum(predicate(c) for cs in calls for c in cs)
        summary[arm] = s
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Reproduce the historical README charts; no network, inference, or new grades.

The inputs are frozen published session accounting and human semantic reviews.
Changing a benchmark requires a new reviewed protocol, not silently new hashes.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from html import escape
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "readme-assets" / "benchmarks"
SOURCE_COMMIT = "39d893b4d8886b8bbaa446ba1414271a93604b3b"
STEP14 = "eval/blind_project_context/step14-host-language-live"
STEP15 = "eval/blind_project_context/step15-grounded-live"
SOURCES = {
    "historical": (f"{STEP14}/results.json", "264c4ee5b496e6e8c6f80a56dad0e77152149c169aed595d115fef3dddb11cc7"),
    "tasks": (f"{STEP14}/tasks.json", "d091e3e94bb56a9d67a1514d23fc9417bb0dc8ee1718b69c4dad63ab8f0505eb"),
    "rubric": (f"{STEP14}/review-criteria.json", "bcc423940023b89b8692a9020438132a8c6ef38478d84cd52bb6dafdc7fcab5c"),
    "grounded": (f"{STEP15}/attempt-02/live-02/results.json", "4e93db69e548918de52f42c82a14c021ffdbf81df74707e8528e643259c081e8"),
    "review": (f"{STEP15}/semantic-review.json", "b3e1dc9232e18e033ab72a88faef7d69a4cab4e8d61815b012b9bfed2f79c67f"),
    "runtime": (f"{STEP15}/runtime-evidence.json", "d7ecef97c03a13f12ef924dfbd0bf327e1d2d5a482e744b3ab1545a42e3246fa"),
    "aggregate": (f"{STEP15}/preliminary-results.json", "1c62fe38912ff78ad0c03fd1a44f9c76522b1cb1970b7b11d9dca84e736d5a5c"),
}
LABELS = {
    "A": ("DocAtlas / Qwen", "Model preflight"),
    "B": ("DocAtlas / Qwen", "Host preflight"),
    "C": ("Direct files", "glob / grep / read"),
    "D": ("Grounded 3.2.1", "Lexical; no embeddings"),
}
USAGE_KEYS = ("input", "cached", "uncached", "output", "reasoning", "cache_write")
GRADES = ("full", "partial", "missing", "contradicted")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def frozen_inputs() -> dict:
    result = {}
    for key, (name, expected) in SOURCES.items():
        raw = (ROOT / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, f"Source hash mismatch: {name}")
        result[key] = json.loads(raw)
    return result


def summarize(inputs: dict) -> dict:
    historical, grounded, review = (inputs[k] for k in ("historical", "grounded", "review"))
    runtime, aggregate = inputs["runtime"], inputs["aggregate"]
    require(runtime["package_version"] == "3.2.1", "Unexpected Grounded version")
    require(runtime["indexed_embedding_count"] == 0, "This is the lexical-only study")
    require(aggregate["historical_results_sha256"] == SOURCES["historical"][1], "Historical binding changed")
    for key in ("tasks", "rubric"):
        require(review["basis"][f"{key}_sha256"] == SOURCES[key][1], f"Review {key} binding changed")
    task_sizes = {task["id"]: len(task["facts"]) for task in inputs["tasks"]}
    require(task_sizes == {"V-M1": 8, "V-M2": 6, "V-M3": 5, "V-M4": 0}, "Unexpected rubric")
    rows = historical["sessions"] + grounded
    require(len(rows) == 16, "Expected four sessions in each of four arms")
    expected_pairs = {(arm, task) for arm in LABELS for task in task_sizes}
    require({(r["arm"], r["task"]) for r in rows} == expected_pairs, "Missing or repeated sessions")
    sessions, arms = [], []
    for arm, (label, detail) in LABELS.items():
        usage_totals, grade_totals = Counter(), Counter()
        delivered_total = requests = 0
        for row in sorted((r for r in rows if r["arm"] == arm), key=lambda r: r["task"]):
            task, usage = row["task"], row["usage"]
            require(all(type(usage[k]) is int and usage[k] >= 0 for k in USAGE_KEYS), "Unknown usage is not zero")
            require(usage["input"] - usage["cached"] == usage["uncached"], "Input already includes cache")
            require(usage["reasoning"] <= usage["output"], "Reasoning is a subset of output here")
            require(type(row["provider_requests"]) is int and row["provider_requests"] > 0, "Missing request count")
            if arm == "D":
                require(row["usage_coverage_complete"], "Incomplete provider accounting")
            quality, delivered = None, None
            if task_sizes[task]:
                if arm == "D":
                    facts = review["tasks"][task]["facts"]
                    require(len(facts) == task_sizes[task], "Review fact count mismatch")
                    counts = Counter(fact["grade"] for fact in facts)
                    require(set(counts) <= set(GRADES), "Unknown review grade")
                    quality = {grade: counts[grade] for grade in GRADES}
                    delivered = sum(fact["delivered"] is True for fact in facts)
                    published = review["tasks"][task]["totals"]
                    require(quality == {grade: published[grade] for grade in GRADES}, "Review totals mismatch")
                    require(delivered == published["delivered"], "Delivery totals mismatch")
                else:
                    quality, delivered = row["quality"], row["source_facts_delivered"]
                require(all(type(quality[g]) is int and quality[g] >= 0 for g in GRADES), "Unknown grade count")
                require(sum(quality[g] for g in GRADES) == task_sizes[task], "Wrong grading denominator")
                require(delivered == task_sizes[task], "Delivery differs from published comparison")
                grade_totals.update(quality)
                delivered_total += delivered
            usage_totals.update({key: usage[key] for key in USAGE_KEYS})
            requests += row["provider_requests"]
            sessions.append({"arm": arm, "task": task, "usage": usage,
                             "model_calls": row["provider_requests"],
                             "delivered_positions": delivered, "answer_grades": quality})
        published = aggregate["totals"][arm]
        require(all(usage_totals[k] == published["usage"][k] for k in USAGE_KEYS), f"Usage mismatch: {arm}")
        require(requests == published["provider_requests"], f"Request total mismatch: {arm}")
        require(grade_totals["contradicted"] == 0, "Chart does not omit nonzero contradictions")
        require(sum(grade_totals.values()) == 19 and delivered_total == 19, "Wrong chart denominator")
        arms.append({"arm": arm, "label": label, "detail": detail,
                     "usage": dict(usage_totals), "model_calls": requests,
                     "delivered_positions": delivered_total,
                     "answer_grades": {g: grade_totals[g] for g in GRADES}})
    return {
        "study": "STEP14/STEP15 Meridian historical diagnostic",
        "source_commit": SOURCE_COMMIT,
        "docatlas_experimental_code": "220d2dab",
        "docatlas_profile": "Qwen minimal-context; one-hop-v1; concise-v1",
        "answering_model_display_name": "magnitcopilot",
        "questions_per_arm": 4, "runs_per_question_and_arm": 1,
        "english_documents": 6, "historical_scoring_positions": 19,
        "current_default_benchmark": False,
        "notes": [
            "The 19 positions contain repeated facts; V-M4 abstention is outside that denominator.",
            "A later draft study questioned shared V-M1 requirements; these four arms were not regraded.",
            "Input includes cache reads; output includes reasoning. No monetary cost is established.",
            "D ran after A/B/C without controlled caching or randomized order.",
            "B/V-M4 full end-to-end timing is missing; no latency comparison is generated.",
        ],
        "sources": [{"path": path, "sha256": digest} for path, digest in SOURCES.values()],
        "arms": arms, "sessions": sessions,
    }


def svg_text(x: float, y: float, value: str, size: int = 15,
             fill: str = "#334155", anchor: str = "start", weight: int = 400) -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{escape(value)}</text>')


def render_chart(data: dict, *, facts: bool) -> str:
    if facts:
        title = "Final-answer coverage under the historical rubric"
        subtitle = "19 scored positions, not 19 independent facts · Same magnitcopilot answering model"
        series = [("full", "Full", "#0f766e", "#ffffff"),
                  ("partial", "Partial", "#fbbf24", "#422006"),
                  ("missing", "Missing", "#be123c", "#ffffff")]
        maximum, ticks = 19, (0, 5, 10, 15, 19)
        footer = "All arms delivered 19/19 scored positions. These counts do not establish an overall winner."
        caveat = "A later study questioned shared-scenario requirements; it did not regrade these four arms."
    else:
        title = "Provider input across four sessions"
        subtitle = "Historical Qwen minimal-context / direct files / Grounded lexical · Not a current-default benchmark"
        series = [("uncached", "Uncached input", "#1d4ed8", "#ffffff"),
                  ("cached", "Cached input", "#bfdbfe", "#172554")]
        maximum, ticks = 30000, range(0, 30001, 5000)
        footer = "Input already includes cache reads. Output tokens and model calls are reported separately."
        caveat = "Provider usage, not money or MCP payload size. One run per question; cache was not controlled."
    description = "; ".join(
        f'{a["arm"]}: ' + ", ".join(
            f'{label} {(a["answer_grades"] if facts else a["usage"])[key]:,}'
            for key, label, _, _ in series) for a in data["arms"])
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="560" '
             'viewBox="0 0 1120 560" role="img" aria-labelledby="title description">',
             f'<title id="title">{escape(title)}</title>',
             f'<desc id="description">{escape(description + ". " + footer + " " + caveat)}</desc>',
             '<rect width="1120" height="560" rx="16" fill="#f8fafc"/>',
             '<g font-family="DejaVu Sans, Arial, sans-serif">',
             svg_text(32, 46, title, 26, "#0f172a", weight=700),
             svg_text(32, 76, subtitle, 15)]
    for i, (_, label, color, _) in enumerate(series):
        x = 345 + i * 205
        parts.extend([f'<rect x="{x}" y="102" width="14" height="14" rx="3" fill="{color}"/>',
                      svg_text(x + 23, 114, label, 14)])
    for tick in ticks:
        x = 345 + 620 * tick / maximum
        parts.append(f'<line x1="{x:.1f}" y1="138" x2="{x:.1f}" y2="432" stroke="#cbd5e1"/>')
        parts.append(svg_text(x, 456, f"{tick:,}", 13, anchor="middle"))
    for i, arm in enumerate(data["arms"]):
        y, x = 150 + i * 75, 345.0
        parts.extend([svg_text(32, y + 21, f'{arm["arm"]} · {arm["label"]}', 17, "#0f172a", weight=700),
                      svg_text(32, y + 43, arm["detail"], 14)])
        values = arm["answer_grades"] if facts else arm["usage"]
        total = sum(values[key] for key, _, _, _ in series)
        require(total <= maximum, "Chart scale would clip a bar")
        for key, _, color, text_color in series:
            value = values[key]
            if not value:
                continue
            width = 620 * value / maximum
            parts.append(f'<rect x="{x:.1f}" y="{y}" width="{width:.1f}" height="40" fill="{color}"/>')
            parts.append(svg_text(x + width / 2, y + 26, f"{value:,}", 16, text_color, "middle", 700))
            x += width
        parts.append(svg_text(x + 12, y + 26, f"{total:,}", 16, "#0f172a", weight=700))
    parts.extend([svg_text(32, 505, footer, 14), svg_text(32, 532, caveat, 14), '</g>', '</svg>'])
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check frozen inputs and committed outputs without writes")
    args = parser.parse_args()
    try:
        data = summarize(frozen_inputs())
        artifacts = {
            "grounded-meridian.json": json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            "grounded-input-tokens.svg": render_chart(data, facts=False),
            "grounded-answer-facts.svg": render_chart(data, facts=True),
        }
        if args.check:
            stale = [name for name, text in artifacts.items()
                     if not (OUTPUT / name).exists() or (OUTPUT / name).read_bytes() != text.encode("utf-8")]
            require(not stale, "Missing or stale generated artifacts: " + ", ".join(stale))
        else:
            OUTPUT.mkdir(parents=True, exist_ok=True)
            for name, text in artifacts.items():
                (OUTPUT / name).write_bytes(text.encode("utf-8"))
        print(f"{'Verified' if args.check else 'Generated'} 3 artifacts from 7 SHA-256-verified sources; 16 sessions, 4 arms.")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Benchmark artifact check failed: {exc}\n")


if __name__ == "__main__":
    main()

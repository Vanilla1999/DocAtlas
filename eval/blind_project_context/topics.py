"""Draw the blind topics mechanically; print headings and line ranges only.

A topic is a leaf Markdown section (ATX heading outside fenced code, no
sub-heading) of an L0 document with at least three non-empty body lines.
Sections that earlier DocAtlas question sets already cite are excluded, so the
new questions do not reuse topics that recent retrieval work was checked on:
line ranges at ``L0_COMMIT`` (acquisition pilot oracle, gold20) and verbatim
witness text from any revision (direct 15 questions, multilingual quality
spans). The draw uses a fixed published seed: at most two topics per document,
24 topics, then a second seeded shuffle splits them 12 dev / 12 holdout.
The output deliberately omits section bodies: questions are written from the
heading path alone and sealed before anyone reads the answer text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from pathlib import Path

import yaml

from corpus import CATALOG, L0_COMMIT, ROOT, git_blob

SEED_TEXT = "docatlas-blind-project-context-v1"
TOPICS = 24
PER_DOCUMENT = 2
MIN_BODY_LINES = 3
HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
PRIOR_LINE_SETS = ("eval/opencode_compat/acq_pilot/oracle.json",
                   "eval/opencode_compat/research_evidence/gold20.json")
PRIOR_TEXT_SETS = ("eval/direct_docatlas_questions_15/cases.json",
                   "eval/multilingual_retrieval_quality/corpus.json")


def squash(text: str) -> str:
    return " ".join(text.split())


def sections(path: str, text: str) -> list[dict]:
    lines = text.splitlines()
    headings, fence = [], None
    for number, line in enumerate(lines, start=1):
        marker = FENCE.match(line)
        if marker:
            if fence is None:
                fence = marker.group(1)
            elif marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                fence = None
            continue
        match = None if fence else HEADING.match(line)
        if match:
            headings.append((number, len(match.group(1)), match.group(2).strip()))
    found, stack = [], []
    for index, (number, level, title) in enumerate(headings):
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        following = headings[index + 1] if index + 1 < len(headings) else None
        if following is not None and following[1] > level:
            continue
        end = (following[0] - 1) if following else len(lines)
        while end > number and not lines[end - 1].strip():
            end -= 1
        body = [line for line in lines[number:end] if line.strip()]
        found.append({"path": path, "heading_path": [item[1] for item in stack],
                      "line_start": number, "line_end": end, "body_nonempty_lines": len(body),
                      "_text": squash("\n".join(lines[number - 1:end]))})
    return found


def prior_citations() -> tuple[list[tuple[str, int, int]], list[tuple[str, str]]]:
    spans, witnesses = [], []
    pilot = json.loads((ROOT / PRIOR_LINE_SETS[0]).read_text(encoding="utf-8"))
    for question in pilot["questions"]:
        for fact in question["facts"]:
            spans.append((fact["path"], int(fact["start"]), int(fact["end"])))
            witnesses.append((fact["path"], fact["quote"]))
    for item in json.loads((ROOT / PRIOR_LINE_SETS[1]).read_text(encoding="utf-8")).values():
        path, _, lines = item["source"].rpartition(":")
        start, _, end = lines.partition("-")
        spans.append((path, int(start), int(end or start)))
    direct = json.loads((ROOT / PRIOR_TEXT_SETS[0]).read_text(encoding="utf-8"))
    for case in direct["cases"]:
        for group in case["fact_groups"]:
            witnesses.extend((item["path"], item["text"]) for item in group["witnesses"])
    multilingual = json.loads((ROOT / PRIOR_TEXT_SETS[1]).read_text(encoding="utf-8"))
    for project in multilingual["projects"]:
        for span in project["documents"]:
            witnesses.extend((span["path"], line) for line in span["content"].splitlines()
                             if len(squash(line)) >= 24)
    return spans, [(path, squash(text)) for path, text in witnesses if squash(text)]


def draw() -> dict:
    catalog = yaml.safe_load(git_blob(L0_COMMIT, CATALOG))
    spans, witnesses = prior_citations()
    candidates, excluded, short = [], 0, 0
    for entry in catalog["documents"]:
        for section in sections(entry["path"], git_blob(L0_COMMIT, entry["path"]).decode("utf-8")):
            if section["body_nonempty_lines"] < MIN_BODY_LINES:
                short += 1
                continue
            cited = any(path == section["path"] and start <= section["line_end"] and end >= section["line_start"]
                        for path, start, end in spans)
            cited = cited or any(path == section["path"] and text in section["_text"] for path, text in witnesses)
            if cited:
                excluded += 1
                continue
            candidates.append({key: value for key, value in section.items() if key != "_text"})
    candidates.sort(key=lambda item: (item["path"], item["line_start"]))
    rng = random.Random(int(hashlib.sha256(SEED_TEXT.encode()).hexdigest(), 16))
    order = list(candidates)
    rng.shuffle(order)
    chosen, per_document = [], {}
    for section in order:
        if per_document.get(section["path"], 0) < PER_DOCUMENT:
            per_document[section["path"]] = per_document.get(section["path"], 0) + 1
            chosen.append(section)
        if len(chosen) == TOPICS:
            break
    split_order = list(chosen)
    rng.shuffle(split_order)
    holdout = {id(item) for item in split_order[TOPICS // 2:]}
    topics = []
    for index, section in enumerate(sorted(chosen, key=lambda item: (item["path"], item["line_start"])), start=1):
        topics.append({"topic_id": f"T{index:02d}", "split": "holdout" if id(section) in holdout else "dev",
                       "language": catalog["documentation_languages"].get(section["path"], ["en"])[0],
                       **section})
    return {"schema_version": 1, "l0_commit": L0_COMMIT, "seed_text": SEED_TEXT,
            "rules": {"topics": TOPICS, "per_document": PER_DOCUMENT, "min_body_nonempty_lines": MIN_BODY_LINES,
                      "prior_line_sets": list(PRIOR_LINE_SETS), "prior_text_sets": list(PRIOR_TEXT_SETS)},
            "counts": {"documents": len(catalog["documents"]), "eligible_sections": len(candidates),
                       "excluded_as_prior_cited": excluded, "excluded_short_body": short},
            "topics": topics}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()
    result = draw()
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        args.write.write_text(text, encoding="utf-8")
    print(text)

"""Check the seal and the gold, then record every verbatim fact occurrence.

* the sealed files still match FREEZE_MANIFEST.json (questions never change);
* every gold quote occurs inside its drawn section of the L0 document;
* every occurrence of every quote in the catalogued L0 and L2 documents is
  listed in witness-audit.json, so scoring can accept any verbatim copy.

``--check`` fails when the committed witness-audit.json is not current.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from corpus import HERE, build, documents

AUDIT = HERE / "witness-audit.json"


def load(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def verify_seal() -> dict:
    manifest = load("FREEZE_MANIFEST.json")
    changed = [name for name, digest in manifest["files"].items()
               if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != digest]
    if changed:
        raise RuntimeError(f"sealed files changed after freezing: {changed}")
    oracle = load("oracle.json")
    if oracle["sealed_questions_sha256"] != manifest["files"]["questions.json"]:
        raise RuntimeError("oracle is not bound to the sealed questions")
    return manifest


def occurrences(text: str, quote: str) -> list[tuple[int, int]]:
    found, start = [], text.find(quote)
    while start >= 0:
        first = text.count("\n", 0, start) + 1
        found.append((first, first + quote.count("\n")))
        start = text.find(quote, start + 1)
    return found


def audit() -> dict:
    verify_seal()
    topics = {topic["topic_id"]: topic for topic in load("topics.json")["topics"]}
    oracle = load("oracle.json")
    with TemporaryDirectory() as tmp:
        corpora = {name: documents(project) for name, project in build(Path(tmp)).items()}
    facts, errors = [], []
    for item in oracle["topics"]:
        topic = topics[item["topic_id"]]
        own = corpora["L0"][topic["path"]]
        for fact in item["facts"]:
            inside = [span for span in occurrences(own, fact["quote"])
                      if topic["line_start"] <= span[0] and span[1] <= topic["line_end"]]
            if not inside:
                errors.append(fact["fact_id"])
            facts.append({"fact_id": fact["fact_id"], "topic_id": item["topic_id"],
                          "drawn_section_occurrence": {"path": topic["path"], "line_start": inside[0][0],
                                                       "line_end": inside[0][1]} if inside else None,
                          "occurrences": {name: [{"path": path, "line_start": a, "line_end": b}
                                                 for path, text in sorted(docs.items())
                                                 for a, b in occurrences(text, fact["quote"])]
                                          for name, docs in corpora.items()}})
    if errors:
        raise RuntimeError(f"gold quotes not found inside their drawn sections: {errors}")
    return {"schema_version": 1, "oracle_sha256": hashlib.sha256((HERE / "oracle.json").read_bytes()).hexdigest(),
            "facts": facts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(audit(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if AUDIT.read_text(encoding="utf-8") != text:
            print("witness-audit.json is stale", file=sys.stderr)
            return 1
        return 0
    AUDIT.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Offline annotation preparation, independent Markdown parser, zero scoring.

Produces REVIEW DRAFT graph/extent/label files. This is not a gate or simulation.
No DocAtlas imports. The pinned raw-source inventory must receive parent review.
"""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import posixpath
import re
from urllib.parse import unquote, urlsplit
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / "step10-multidoc-gate"


def save(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    projects = json.loads((OLD / "projects.json").read_text())
    for project in projects:
        project["root"] = "../step10-multidoc-gate/" + project["root"]
        if project["split"] == "validation":
            project["split"] = "seen"
    projects.extend([
        {"id": "otel", "split": "holdout", "root": "sources/opentelemetry-specification", "query_scope": "project",
         "project_documents": ["specification/baggage/api.md", "specification/context/README.md",
                               "specification/context/api-propagators.md", "specification/document-status.md"],
         "module_documents": [{"path": "specification/context/env-carriers.md", "scope": "module", "module_path": "specification/context"}]},
        {"id": "embedded", "split": "holdout", "root": "sources/book", "query_scope": "project",
         "project_documents": ["src/start/interrupts.md", "src/start/exceptions.md", "src/start/panicking.md"],
         "module_documents": [{"path": "src/start/semihosting.md", "scope": "module", "module_path": "src/start"}]},
    ])
    md = MarkdownIt("commonmark", {"store_labels": True})
    inventories, graphs = {}, {}
    for project in projects:
        all_units, parsed = {}, {}
        names = project["project_documents"] + [d["path"] for d in project["module_documents"]]
        for path in names:
            raw_bytes = (ROOT / project["root"] / path).read_bytes()
            raw = raw_bytes.decode("utf-8")
            lines = raw.splitlines(keepends=True)
            offsets = [0]
            for line in lines:
                offsets.append(offsets[-1] + len(line))
            env = {}
            tokens = md.parse(raw, env)
            headings = [(t.map[0], int(t.tag[1:])) for t in tokens if t.type == "heading_open"]
            assert all(re.match(r"^#{1,6} ", lines[i]) for i, _ in headings), "setext needs separate review"
            if not headings or headings[0][0] != 0:
                headings.insert(0, (0, 0))
            units, slug_counts, anchors = [], {}, {}
            for n, (line, level) in enumerate(headings):
                stop = headings[n + 1][0] if n + 1 < len(headings) else len(lines)
                heading = lines[line][level:].strip() if level else "Introduction"
                key = path + "#" + heading
                if key in all_units:
                    key += " [line " + str(line + 1) + "]"
                a, b = offsets[line], offsets[stop]
                body = offsets[line + 1] if level else a
                unit = {"key": key, "path": path, "scope": "project" if path in project["project_documents"] else "module",
                        "heading_line": line + 1, "line_end": stop, "heading_level": level,
                        "char_start": a, "body_char_start": body, "char_end": b,
                        "own_text": raw[body:b], "source_sha256": sha(raw_bytes),
                        "whole_text_sha256": sha(raw[a:b].encode()), "reference_targets": [], "reference_gaps": [],
                        "reference_witnesses": []}
                units.append(unit)
                all_units[key] = unit
                if level:
                    slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
                    occurrence = slug_counts.get(slug, 0)
                    slug_counts[slug] = occurrence + 1
                    anchors[slug + (f"-{occurrence}" if occurrence else "")] = key
            for i, u in enumerate(units):
                end = next((j for j in range(i + 1, len(units)) if units[j]["heading_level"] <= u["heading_level"]), len(units))
                u["addressed_extent"] = [v["key"] for v in units[i:end]] if u["heading_level"] else [u["key"]]
                level, parents = u["heading_level"], []
                for v in reversed(units[:i]):
                    if v["heading_level"] < level:
                        parents.append(v["key"])
                        level = v["heading_level"]
                u["ancestors"] = parents
            parsed[path] = (raw, lines, offsets, tokens, env, units, anchors)

        for path, (raw, lines, offsets, tokens, env, units, anchors) in parsed.items():
            def owner(line):
                return next(u for u in units if u["heading_line"] - 1 <= line < u["line_end"])

            def gap(u, target, reason):
                g = {"target": target, "reason": reason}
                if g not in u["reference_gaps"]:
                    u["reference_gaps"].append(g)

            def link(u, target, line, definition=None, stop=None):
                stop = stop if stop is not None else line + 1
                u["reference_witnesses"].append({"target": target, "source_line": line + 1,
                                                "char_start": offsets[line], "char_end": offsets[stop],
                                                "raw_excerpt": raw[offsets[line]:offsets[stop]],
                                                "definition_label": definition})
                if definition and "`" in definition:
                    gap(u, "", "unsupported_definition_label")
                    return
                if definition:
                    ref = env["references"][definition]
                    u["reference_targets"].append(owner(ref["map"][0])["key"])
                url = urlsplit(target)
                if url.scheme or url.netloc or url.query:
                    gap(u, target, "target_not_in_checked_scope")
                    return
                dest = posixpath.normpath(posixpath.join(posixpath.dirname(path), unquote(url.path))) if url.path else path
                if not target or "\\" in url.path or (url.path and not dest.lower().endswith((".md", ".markdown"))):
                    gap(u, target, "unsupported_local_document_target")
                elif dest not in project["project_documents"]:
                    gap(u, target, "target_not_in_checked_scope")
                elif not url.fragment:
                    u["reference_targets"].extend(v["key"] for v in parsed[dest][5])
                elif unquote(url.fragment) not in parsed[dest][6]:
                    gap(u, target, "missing_or_ambiguous_anchor")
                else:
                    key = parsed[dest][6][unquote(url.fragment)]
                    u["reference_targets"].extend(all_units[key]["addressed_extent"])

            for token in tokens:
                if token.type != "inline" or not token.map:
                    continue
                u = owner(token.map[0])
                for child in token.children or []:
                    if child.type == "link_open":
                        link(u, child.attrGet("href"), token.map[0], child.meta.get("label"), token.map[1])
                    elif child.type == "image":
                        gap(u, child.attrGet("src"), "unsupported_asset_dependency")
            for label, ref in env.get("references", {}).items():
                line = ref["map"][0]
                link(owner(line), ref["href"], line, label, ref["map"][1])
            for u in units:
                u["reference_targets"] = sorted(set(u["reference_targets"]))
        inventories[project["id"]] = all_units
        graphs[project["id"]] = list(all_units.values())

    tasks = json.loads((OLD / "tasks.json").read_text())
    new_tasks = json.loads((ROOT / "holdout-tasks.json").read_text())
    for task in new_tasks:
        units = inventories[task["project"]]
        required = set(task["direct"])
        task["structural"] = sorted({p for k in required for p in units[k]["ancestors"]} - required)
        for key, quote in task["facts"]:
            assert key in required and quote in units[key]["own_text"], (task["id"], quote)
        task["optional_support"] = []
    tasks.extend(new_tasks)
    oldlabels = {r["task_id"]: {u["key"]: u for u in r["units"]}
                 for r in json.loads((OLD / "draft-labels.json").read_text())}
    labels, facts = [], []
    for task in tasks:
        units = inventories[task["project"]]
        annotated = []
        for key, u in units.items():
            if task["id"] in oldlabels:
                role = oldlabels[task["id"]][key]["role"]
            else:
                role = ("excluded" if u["scope"] != "project" else "direct" if key in task["direct"] else
                        "structural" if key in task["structural"] else "unlabelled")
            annotated.append({**u, "role": role, "hard_negative": key in task["hard_negatives"]})
        labels.append({"task_id": task["id"], "units": annotated})
        for key, quote in task["facts"]:
            u = units[key]
            start = u["body_char_start"] + u["own_text"].index(quote)
            facts.append({"task_id": task["id"], "key": key, "quote": quote, "char_start": start,
                          "char_end": start + len(quote), "source_sha256": u["source_sha256"]})
    save("projects.json", projects)
    save("tasks.json", tasks)
    save("draft-labels.json", labels)
    save("source-extent-graph.json", graphs)
    save("fact-spans.json", facts)
    save("annotation-receipt.json", {"status": "DRAFT_PARENT_REVIEW_REQUIRED", "independent_parser": "markdown-it-py",
         "version": importlib.metadata.version("markdown-it-py"), "source_projects": len(projects),
         "seen_questions": 16, "new_questions": 8, "holdout_source_files": 9,
         "new_fact_quotes": sum(len(t["facts"]) for t in new_tasks),
         "model_calls": 0, "closure_simulations": 0,
         "limitations": ["agent-selected questions/annotations, not blind external benchmark",
                         "reference graph draft requires raw-source review; no threshold evaluation",
                         "no new holdout true hard negatives claimed; excluded scope documents are adversarial witnesses"]})


if __name__ == "__main__":
    main()

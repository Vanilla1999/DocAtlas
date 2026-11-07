"""Offline authored-fixture inventory; no production imports, inference or freeze."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def inventory(path):
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    headers = [(i, m.group(2)) for i, line in enumerate(lines)
               if (m := re.fullmatch(r"(#{1,6}) (.+)\n?", line))]
    sections = {}
    for n, (start, heading) in enumerate(headers):
        end = headers[n + 1][0] if n + 1 < len(headers) else len(lines)
        body = "".join(lines[start + 1:end])
        assert heading not in sections and body.strip(), (path, heading)
        sections[heading] = {"heading_line": start + 1, "line_end": end,
                             "own_text": body, "source_sha256": digest(raw)}
    return sections


def main():
    projects = json.loads((ROOT / "projects.json").read_text())
    tasks = json.loads((ROOT / "tasks.json").read_text())
    assert len(projects) == 4 and len(tasks) == 16
    project_map, manifests = {}, {}
    for project in projects:
        directory = ROOT / project["root"]
        paths = project["project_documents"] + [d["path"] for d in project["module_documents"]]
        assert len(paths) == len(set(paths)) == 7
        assert set(paths) == {p.relative_to(directory).as_posix() for p in directory.rglob("*.md")}
        sections = {}
        for path in paths:
            source = directory / path
            manifests[source.relative_to(ROOT).as_posix()] = digest(source.read_bytes())
            for heading, section in inventory(source).items():
                sections[path + "#" + heading] = {**section, "path": path,
                    "scope": "project" if path in project["project_documents"] else "module"}
        project_map[project["id"]] = (project, sections)
        group = [t for t in tasks if t["project"] == project["id"]]
        assert len(group) == 4 and sum(bool(t.get("no_answer")) for t in group) == 1
    labels = []
    for task in tasks:
        project, sections = project_map[task["project"]]
        direct, structural, hard = (set(task[k]) for k in ("direct", "structural", "hard_negatives"))
        assert not direct & structural and not (direct | structural) & hard
        assert direct | structural | hard <= sections.keys()
        assert all(sections[k]["scope"] == "project" for k in direct | structural | hard)
        assert bool(task.get("no_answer")) == (not task["facts"])
        if task.get("no_answer"):
            assert not direct | structural
            assert sections[task["excluded_temptation"]]["scope"] == "module"
        for section, quote in task["facts"]:
            assert section in direct | structural and quote in sections[section]["own_text"], (task["id"], quote)
        if task.get("explicit_full_section"):
            assert task["explicit_full_section"] in direct
        labels.append({"task_id": task["id"], "split": project["split"], "scope": "project",
            "units": [{"key": key, **section,
                "role": ("excluded" if section["scope"] != "project" else
                         "direct" if key in direct else "structural" if key in structural else "negative"),
                "hard_negative": key in hard} for key, section in sections.items()]})
    for name in ("projects.json", "tasks.json", "DESIGN_RU.md", "STRUCTURAL_V2_DESIGN_RU.md", "audit_draft.py"):
        manifests[name] = digest((ROOT / name).read_bytes())
    manifest = {"status": "DRAFT_AWAITING_PARENT_REVIEW", "frozen_before_inference": False,
                "scorer_calls": 0, "public_prepares": 0,
                "provenance": "agent-authored synthetic; independent of T01, not external data",
                "files": manifests, "projects": 4, "documents": 28, "questions": 16,
                "fact_quotes": sum(len(t["facts"]) for t in tasks),
                "no_answer": sum(bool(t.get("no_answer")) for t in tasks)}
    (ROOT / "draft-labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=2) + "\n")
    manifest["files"]["draft-labels.json"] = digest((ROOT / "draft-labels.json").read_bytes())
    (ROOT / "draft-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in manifest.items() if k != "files"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

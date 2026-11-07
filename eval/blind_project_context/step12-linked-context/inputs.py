"""Frozen seen Meridian inputs and one source-authored structural guard.

Nothing here obtains expectations from the implementation under test. The guard
extends a copy of the existing public structural fixture, never its constants.
"""
from __future__ import annotations

import json
from pathlib import Path

from eval.blind_project_context.probe_minimal_structure import DOCUMENTS, QUESTION
from eval.heuristic_removal.receipts import sha

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "eval/blind_project_context"
DATA = BASE / "step10-reference-closure-v3"
POLICY = BASE / "step10-qwen-validation/provenance/original-policy.json"
CASE_IDS = ("V-M1", "V-M2", "V-M3", "V-M4")
COVERAGE = {
    "Meridian": {
        "direct_anchored_link": "V-M1 Transfer to Suspension",
        "ancestor_only_link": "NOT COVERED: the parent itself is a Qwen seed",
        "navigation_only_block": "NOT COVERED: overview Navigation is not selected",
        "linked_body_second_hop": "NOT COVERED", "missing_anchor": "NOT COVERED",
        "document_only_target": "NOT COVERED",
        "excluded_module": "V-M4 project scope; no cross-scope link in this corpus",
    },
    "guard": "Direct/ancestor/navigation/linked-body origins, missing anchor, document-only target, excluded module, exact single-decode HTML target, fail-closed backtick HTML attribute; no scorer or model-selection claim",
}


def read(path):
    return json.loads(path.read_text())


def frozen_inputs():
    project = next(p for p in read(DATA / "projects.json") if p["id"] == "meridian")
    source_root = (DATA / project["root"]).resolve()
    paths = project["project_documents"] + [r["path"] for r in project["module_documents"]]
    documents = {p: (source_root / p).read_bytes().decode("utf-8") for p in paths}
    policy = read(POLICY)
    graph = {u["key"]: u for u in read(DATA / "source-extent-graph.json")["meridian"]}
    tasks = {t["id"]: t for t in read(DATA / "tasks.json") if t["id"] in CASE_IDS}
    originals = {t["id"]: t for t in read(BASE / "step10-multidoc-gate/tasks.json") if t["id"] in CASE_IDS}
    files = [DATA / "projects.json", DATA / "tasks.json", DATA / "source-extent-graph.json",
             BASE / "step10-multidoc-gate/tasks.json", POLICY, *(source_root / p for p in paths)]
    cases = []
    for ident in CASE_IDS:
        task = tasks[ident]
        assert task["question"] == originals[ident]["question"]
        saved_path = BASE / "step10-qwen-validation/run-01/validation/meridian" / (ident + ".json")
        saved = read(saved_path)
        files.append(saved_path)
        assert saved["error"] is None and saved["receipt_status"] == "available"
        assert len(saved["observations"]) == 1
        observation = saved["observations"][0]
        assert observation["policy_sha256"] == sha(POLICY.read_bytes())
        assert observation["receipt"]["status"] == "complete"
        assert observation["receipt"]["contract_sha256"] == policy["contract_sha256"]
        facts = []
        for key, quote in task["facts"]:
            unit = graph[key]
            source = documents[unit["path"]]
            assert sha(source.encode()) == unit["source_sha256"]
            start = source.index(quote, unit["char_start"], unit["char_end"])
            facts.append(dict(path=unit["path"], start=start, end=start + len(quote), quote=quote))
        cases.append(dict(id=ident, question=task["question"], facts=facts,
                          no_answer=bool(task.get("no_answer")), scores=observation["scores"],
                          threshold=policy["threshold"], historical_packet=saved["packet"],
                          historical_receipt=observation["receipt"]))
    return documents, project["module_documents"], cases, files


def guard_inputs():
    documents = dict(DOCUMENTS)
    documents["docs/guide.md"] = documents["docs/guide.md"].replace(
        "Scope introduction.",
        "Scope introduction. The scope refers to the [ancestor condition](other.md#ancestor-only).",
    ).replace("| Item | Value |", (
        "Consult the [absent condition](other.md#absent), [whole document](other.md), "
        "and [restricted condition](modules/private.md#hidden).\n\n"
        "The rule also refers to its [scope introduction](#guide).\n\n"
        'Also retain the <a href="other.md#condition&amp;amp;gate">required condition</a>.\n\n'
        'Inspect the <a href="other.md#raw`target`">raw syntax reference</a>.\n\n'
        "- [Index entry](other.md#navigation-only)\n\n| Item | Value |"))
    documents["docs/other.md"] = documents["docs/other.md"].replace(
        "Remote condition [missing](private.md#hidden).",
        "Remote condition [missing](private.md#hidden). "
        "The remote condition also depends on [second step](#second-hop).",
    ) + (
        "\n## Ancestor only\n\nAncestor-only condition is not automatically fetched.\n"
        "\n## Navigation only\n\nNavigation-only content is not automatically fetched.\n"
        "\n## Second hop\n\nSecond-hop condition is not automatically fetched.\n"
        '\n## Correct entity condition\n\n<a id="condition&amp;amp;gate"></a>\n\n'
        "The single-decoded entity condition must be retained.\n"
        '\n## Wrong entity condition\n\n<a id="condition&amp;gate"></a>\n\n'
        "The double-decoded entity condition must not be substituted.\n"
        '\n## Raw syntax target\n\n<a id="raw`target`"></a>\n\n'
        "Raw HTML attribute content must not be fabricated.\n")
    documents["docs/modules/private.md"] = (
        "# Hidden\n\nRestricted condition must remain outside project scope.\n")
    required = {
        "docs/guide.md": ("Scope introduction.", "Keep this condition [limits](#limits) and [more][ref].",
                          "Limit condition [cycle](#selected).", "Footnote condition.\n    Continued footnote."),
        "docs/other.md": ("Other introduction.", "Remote condition [missing](private.md#hidden).",
                          "The single-decoded entity condition must be retained."),
    }
    facts = [dict(path=path, start=documents[path].index(quote),
                  end=documents[path].index(quote) + len(quote), quote=quote)
             for path, quotes in required.items() for quote in quotes]
    forbidden = [(path, quote) for path, quotes in {
        "docs/other.md": ("Ancestor-only condition is not automatically fetched.",
                          "Navigation-only content is not automatically fetched.",
                          "Second-hop condition is not automatically fetched.",
                          "The double-decoded entity condition must not be substituted.",
                          "Raw HTML attribute content must not be fabricated."),
        "docs/modules/private.md": ("Restricted condition must remain outside project scope.",),
    }.items() for quote in quotes]
    start = documents["docs/guide.md"].index("### Selected\n")
    end = documents["docs/guide.md"].index("#### Tail\n")
    case = dict(id="structural-guard", question=QUESTION, facts=facts, no_answer=False,
                component_seed=("docs/guide.md", start, end), forbidden=forbidden,
                literal_html_target="other.md#condition&amp;amp;gate",
                unsupported_html_target="other.md#raw`target`",
                pending=[("ancestor", "other.md#ancestor-only"),
                         ("selected_body", "other.md#absent"),
                         ("selected_body", "other.md"),
                         ("selected_body", "modules/private.md#hidden"),
                         ("selected_body", "other.md#navigation-only"),
                         ("selected_body", "other.md#raw`target`"),
                         ("linked_body", "#second-hop")])
    modules = [dict(path="docs/modules/private.md", scope="module", module_path="docs/modules")]
    return documents, modules, [case]

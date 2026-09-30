"""Frozen strong-planner retrieval probe. Plans are pre-authored; this file performs no LLM inference."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from .pilot_run import acquire, prepare, HERE
from .baseline_probe import run, write_report, environment
from .pilot_io import evidence_blocks, freeze_file_hashes, sha256

FILES = ["strong_pilot.protocol.json","strong_pilot.tasks.json","strong_pilot_run.py",
         "pilot_run.py","pilot_io.py","baseline_probe.py","source_profile.py","reference_core.py"]

def norm(text: str) -> str:
    return " ".join(text.casefold().split())

def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    out=args.output
    out.mkdir(parents=True,exist_ok=False)
    protocol=json.loads((HERE/"strong_pilot.protocol.json").read_text())
    tasks=json.loads((HERE/"strong_pilot.tasks.json").read_text())
    sources=acquire(protocol,out)
    scopes,oracles=prepare(protocol,tasks,sources,out)
    freeze={"status":"FROZEN_BEFORE_FIRST_HANDLER_CALL","created_at":datetime.now(timezone.utc).isoformat(),
            "files":freeze_file_hashes(HERE,FILES),"environment":environment(),
            "source_sha256":{k:v["sha256"] for k,v in sources.items()},
            "profiles":{k:v["hint"] for k,v in scopes.items()},
            "planner_identity":protocol["planner_identity"],"all_task_ids":[t["id"] for t in tasks],
            "product_activation":False}
    write_report(out/"freeze.json",freeze)
    print("FROZEN",sha256((out/"freeze.json").read_bytes()),flush=True)
    rows=[]
    for task in tasks:
        scope=scopes[task["scope"]]
        for cond in protocol["conditions"]:
            queries=[] if cond=="O" else [task["plans"][cond]]
            observed=run(scope["root"],scope["spec"],{"question":task["question"],"lookup_queries":queries})
            if observed["status"]!="EXECUTED":
                write_report(out/f'{task["id"]}-{cond}-error.json',observed)
                raise RuntimeError("handler/audit failed")
            blocks=evidence_blocks(observed["payload"])
            packet=norm("\n".join(b["text"] for b in blocks))
            complete=(not task["answerable"]) or all(norm(x) in packet for x in task["must_include"])
            rec={"task_id":task["id"],"condition":cond,"family":task["family"],
                 "query_language":task["query_language"],"question":task["question"],
                 "lookup_queries":queries,"source_language_hint":scope["hint"],
                 "answerable":task["answerable"],"complete_evidence":complete,
                 "evidence":blocks,"budget_tokens":observed["budget_tokens"],
                 "audit_errors":observed["audit_errors"],
                 "answer_supported":observed["payload"].get("answer_supported"),
                 "edit_ready":observed["payload"].get("edit_ready")}
            write_report(out/f'{task["id"]}-{cond}.json',rec)
            rows.append({k:rec[k] for k in ("task_id","condition","family","query_language","answerable","complete_evidence","budget_tokens","answer_supported","edit_ready")})
            print(json.dumps(rows[-1],ensure_ascii=False),flush=True)
    summary={}
    for cond in protocol["conditions"]:
        rr=[r for r in rows if r["condition"]==cond and r["answerable"]]
        summary[cond]={"complete":sum(bool(r["complete_evidence"]) for r in rr),"answerable":len(rr)}
    write_report(out/"summary.json",{"status":"EXECUTED_NOT_ANSWER_SCORED","summary":summary,"rows":rows,
                                     "planner_identity":protocol["planner_identity"],"product_activation":False})
    if freeze["files"] != freeze_file_hashes(HERE,FILES):
        raise RuntimeError("experiment files changed after freeze")
    return 0

if __name__=="__main__":
    raise SystemExit(main())

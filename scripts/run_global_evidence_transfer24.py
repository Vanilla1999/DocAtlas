#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, tempfile
from pathlib import Path
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.project_context_quality.capture_public_context import capture_public_call
from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--questions",type=Path,required=True)
    ap.add_argument("--source-plan",type=Path,required=True)
    ap.add_argument("--sources-root",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    questions=json.loads(a.questions.read_text())["cases"]
    plan=json.loads(a.source_plan.read_text())["projects"]
    os.environ["DOCATLAS_OFFLINE"]="1"
    os.environ["DOCATLAS_AUTO_VECTORS"]="0"
    rows=[]
    with tempfile.TemporaryDirectory(prefix="transfer24-") as raw:
        base=Path(raw); services={}
        try:
            for project,spec in plan.items():
                checkout=a.sources_root/project
                docs={rel:(checkout/rel).read_text(encoding="utf-8") for rel in spec["files"]}
                project_root=base/"corpus"/project
                write_project(project_root,docs)
                ctx=isolated_service(base/"state"/project)
                service,config=ctx.__enter__()
                index_project(service,config,project_root)
                services[project]=(ctx,service,project_root)
            for case in questions:
                _,service,root=services[case["project"]]
                cap=capture_public_call(service,{"project_path":str(root),"scope":"project","question":case["question"]})
                payload=cap["public_payload"]
                visible="\n".join(str(s.get("snippet") or "") for s in payload.get("sources") or [])
                safety=[]
                if docs_context_budget_tokens(payload)>800: safety.append("budget")
                if len(payload.get("sources") or [])>3: safety.append("source_cap")
                if payload.get("kind")=="docs_context" and any(payload.get(k) is not False for k in ("answer_supported","answer_available","edit_ready")):
                    safety.append("retrieval_flags")
                required=list(case.get("required_texts") or [])
                supported=(case["answerability"]=="within_budget" and bool(required) and all(text in visible for text in required))
                rows.append({"id":case["id"],"project":case["project"],"answerability":case["answerability"],"supported":supported,"required_texts":required,"safety_errors":safety,"payload":payload})
                print(case["id"],case["answerability"],supported,payload.get("status"),payload.get("estimated_tokens"),flush=True)
        finally:
            for ctx,_,_ in services.values(): ctx.__exit__(None,None,None)
    a.output.write_text(json.dumps({"rows":rows},ensure_ascii=False,indent=2)+"\n")
if __name__=="__main__":
    main()

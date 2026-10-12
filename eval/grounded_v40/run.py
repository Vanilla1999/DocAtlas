"""Run the pinned Grounded Docs CLI against DocAtlas's unchanged V40 documents.

This is a separate retrieval system with its own FTS index, local file parsing,
and context assembly. It does not evaluate generated answers.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
V40 = REPO / "eval" / "prepared_model_comparison40"
GROUND_VERSION = "3.2.1"

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def cli_call(cli, conf, *cmd, max_seconds=120):
    begin=time.monotonic()
    try:
        process=subprocess.run([str(cli), "--config", str(conf), *cmd],
            capture_output=True, text=True, timeout=max_seconds, check=False)
        return {"argv":["--config",str(conf),*cmd],"returncode":process.returncode,
            "seconds":round(time.monotonic()-begin,4),
            "stdout":process.stdout, "stderr":process.stderr[-12000:]}
    except Exception as exc:
        return {"argv":["--config",str(conf),*cmd],"error":type(exc).__name__+":"+str(exc),
            "seconds":round(time.monotonic()-begin,4)}

def run(args):
    output=args.output.resolve()
    if output.exists():raise ValueError("Output directory must be new")
    output.mkdir(parents=True)
    root=output/"docs"
    fams=read_json(V40/"source_plan.json")["families"]
    questions=read_json(V40/"questions.json")["cases"]
    manifests={}
    for f in fams:
        manifest={}
        for rel in f["paths"]:
            original=V40/"sources"/f["id"]/rel
            data=original.read_bytes()
            destination=root/f["id"]/rel
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(data)
            manifest[rel]=hashlib.sha256(data).hexdigest()
        manifests[f["id"]]=manifest
    cfg=output/"grounded-config.yaml"
    cfg.write_text(f"""app:
  storePath: "{(output/'grounded-store').as_posix()}"
  telemetryEnabled: false
  embeddingModel: null
scraper:
  maxPages: 80
  maxDepth: 12
  security:
    fileAccess:
      mode: allowedRoots
      allowedRoots:
        - "{root.as_posix()}"
      followSymlinks: false
      includeHidden: false
""",encoding="utf-8")
    write_json(output/"MANIFEST.json",{
      "version":GROUND_VERSION,"questions_sha256":hashlib.sha256((V40/"questions.json").read_bytes()).hexdigest(),
      "gold_sha256":hashlib.sha256((V40/"gold_spans.json").read_bytes()).hexdigest(),
      "source_sha256":manifests,"libraries":[f["id"] for f in fams],
      "embedding":"none; no provider keys configured","limits":list(args.limits),
      "policy":"No gold in CLI; no retries; no generator"})
    complete=[]
    for f in fams[:1] if args.smoke else fams:
        library="v40-"+f["id"]
        c=cli_call(args.cli,cfg,"scrape",library,(root/f["id"]).as_uri(),
                   "--max-pages","80","--max-depth","12",max_seconds=240)
        complete.append({"type":"scrape","family":f["id"],"receipt":c})
        write_json(output/"preparation"/(f["id"]+".json"),c)
        print("scrape",f["id"],c.get("returncode"),c.get("error"),
              c.get("stdout","")[:150],flush=True)
        if c.get("returncode") != 0:break
        for case in questions:
            if case["project_group"]!=f["id"]:continue
            for limit in args.limits:
                z=cli_call(args.cli,cfg,"search",library,case["question"],
                           "--limit",str(limit),"--output","json",max_seconds=90)
                write_json(output/"calls"/case["id"]/(str(limit)+".json"),z)
                complete.append({"type":"search","id":case["id"],"limit":limit,
                    "returncode":z.get("returncode"),"error":z.get("error"),
                    "seconds":z["seconds"],"stdout_bytes":len(z.get("stdout","").encode())})
                print("search",case["id"],limit,z.get("returncode"),z.get("error"),
                      z.get("stdout","")[:110],flush=True)
        if args.smoke: break
    write_json(output/"RUN_LOG.json",complete)
    if any(x.get("receipt",{}).get("returncode",0)!=0 for x in complete if x["type"]=="scrape"):
        return 2
    if any(x.get("returncode")!=0 for x in complete if x["type"]=="search"):
        return 3
    return 0

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--cli",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--smoke",action="store_true")
    parser.add_argument("--limits",type=int,nargs="+",default=[2,5])
    sys.exit(run(parser.parse_args()))

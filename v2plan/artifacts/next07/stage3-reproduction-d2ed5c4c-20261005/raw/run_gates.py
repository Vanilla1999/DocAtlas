"""Local evidence runner; no runtime instrumentation or source changes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

root, python, label = sys.argv[1:]
out = Path(__file__).parent / label
out.mkdir(exist_ok=True)
env = dict(os.environ, DOCATLAS_OFFLINE="1", PATH=str(Path(python).parent)+":"+os.environ["PATH"], RUNNER_TEMP=str(out))
def git(*args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()
def hashes():
    return {p: hashlib.sha256((Path(root)/p).read_bytes()).hexdigest() for p in git("ls-files").splitlines() if (Path(root)/p).is_file()}
before = hashes()
metadata = {"head":git("rev-parse","HEAD"), "parents":git("show","-s","--format=%P"), "tree":git("rev-parse","HEAD^{tree}"), "status_before":git("status","--porcelain"), "source_sha256":before, "python":python, "offline":"1"}
(out/"manifest.json").write_text(json.dumps(metadata, indent=2)+"\n")
subprocess.run([python,"-m","pip","freeze"],stdout=(out/"pip-freeze.txt").open("w"),stderr=subprocess.STDOUT)
subprocess.run([python,"-c","import sys,docmancer; print(sys.version); print(docmancer.__file__)"],cwd=root,stdout=(out/"runtime.txt").open("w"),stderr=subprocess.STDOUT)
commands = [
 ["-m","pytest","tests/","-m","advanced","-q"],
 ["scripts/run_recovery_contract_gate.py"],
 ["scripts/run_recovery_mutation_gate.py"],
 ["eval/project_context_quality_protocol.py"],
 ["eval/project_context_quality_protocol.py","--live","--report-only","--output",str(out/"legacy.json")],
 ["scripts/check_legacy_project_context_lineage.py",str(out/"legacy.json")],
 ["scripts/run_project_context_quality_v2_gate.py","--output",str(out/"v2.json")],
 ["scripts/run_question_surface_gate.py"],
 ["scripts/run_agent_developer_gate.py"],
 ["scripts/run_agent_developer_adversarial_gate.py"],
 ["scripts/run_critical_mutation_gate.py"],
 ["scripts/run_agent_developer_adversarial_mutation_gate.py"],
 ["scripts/docs_mcp_stdio_smoke.py"],
 ["scripts/installed_mcp_contract_self_test.py"],
]
ledger=[]
for i,args in enumerate(commands):
    start=time.time()
    with (out/f"gate-{i:02d}.log").open("w") as f:
        try:
            result=subprocess.run([python,*args],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=300)
            code=result.returncode
        except subprocess.TimeoutExpired:
            code="TIMEOUT"
    ledger.append({"command":[python,*args],"cwd":root,"sha":metadata["head"],"exit_code":code,"seconds":time.time()-start,"log":f"gate-{i:02d}.log","source_changed":hashes()!=before})
    (out/"ledger.json").write_text(json.dumps(ledger,indent=2)+"\n")
    print(label,i,code,flush=True)
(out/"postflight.json").write_text(json.dumps({"status":git("status","--porcelain"),"hashes_unchanged":hashes()==before},indent=2)+"\n")

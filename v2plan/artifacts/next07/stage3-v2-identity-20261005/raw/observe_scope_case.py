"""Trace one existing adversarial case without replacing any callable."""
import json
from pathlib import Path
import sys

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))
from scripts import run_agent_developer_adversarial_gate as gate

case = next(c for c in gate._load_cases()["cases"] if c["id"] == "module_scope_rejects_project_policy_detail")
observations = []


def trace(frame, event, arg):
    if event == "line" and frame.f_code.co_name == "_run_adversarial_case" and frame.f_lineno == 449:
        observations.append({"request":frame.f_locals["args"],"raw_response":frame.f_locals["payload"]})
    return trace


sys.settrace(trace)
try:
    result = gate._run_adversarial_case(case)
finally:
    sys.settrace(None)
print(json.dumps({"case":case,"observations":observations,"result":result},ensure_ascii=False,indent=2,default=str))
raise SystemExit(0 if result["passed"] else 1)

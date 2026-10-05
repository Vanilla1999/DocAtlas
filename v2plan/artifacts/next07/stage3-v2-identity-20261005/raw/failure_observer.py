"""Read-only failed-test frame capture; fixtures/results are never replaced."""
import hashlib
import json
import os
from pathlib import Path


def pytest_runtest_makereport(item, call):
    if call.when != "call" or call.excinfo is None:
        return
    names = {
        "question", "payload", "response", "result", "results", "chunks",
        "retrieval_plan", "contract", "requirements", "expected", "requests",
        "request_payload", "arguments", "rows", "case", "case_id", "report",
        "cases", "lookup_queries", "limit", "budget", "tokens", "projection",
        "sources", "actual", "queries", "fragments", "item", "text", "assertions",
    }
    frames = []
    for entry in call.excinfo.traceback:
        path = Path(str(entry.path)).resolve()
        frames.append({"path":str(path),"line":entry.lineno+1,"function":entry.name,
                       "source_sha256":hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
                       "locals":{k:repr(v) for k,v in entry.frame.f_locals.items() if k in names}})
    with Path(os.environ["FAILURE_OBSERVER_OUTPUT"]).open("a") as stream:
        stream.write(json.dumps({"node_id":item.nodeid,"fixtures":item.fixturenames,"frames":frames,"assertion":str(call.excinfo.value)},ensure_ascii=False)+"\n")

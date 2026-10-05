"""Read-only failure observation, no callable replacement or result modification."""
import hashlib
import json
import os
from pathlib import Path


def pytest_runtest_makereport(item, call):
    if call.excinfo is None or call.when != "call":
        return
    frames = []
    names = {"question", "payload", "response", "result", "model", "protocol", "expected", "project", "request_payload", "arguments"}
    for entry in call.excinfo.traceback:
        path = Path(str(entry.path)).resolve()
        frames.append({
            "file": str(path),
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
            "line": entry.lineno + 1,
            "function": entry.name,
            "observed_locals": {name: repr(value) for name, value in entry.frame.f_locals.items() if name in names},
        })
    with Path(os.environ["STAGE3_CAPTURE"]).open("a") as stream:
        stream.write(json.dumps({"node_id":item.nodeid,"fixtures":item.fixturenames,"frames":frames,"assertion":str(call.excinfo.value)},ensure_ascii=False)+"\n")

"""Observe existing projector returns, without altering inputs or outputs."""
import json
import os
from pathlib import Path
import sys

CURRENT = None
EVENTS = []


def profile(frame, event, arg):
    if event == "return" and "/docmancer/docs/" in str(frame.f_code.co_filename) and frame.f_code.co_name in {
        "query_project_docs", "get_project_docs", "project_context_pack",
        "_drop_placeholder_context_doc", "_drop_low_value_context_section",
        "_should_skip_low_trust_project_source",
    }:
        EVENTS.append({"node_id":CURRENT,"owner":frame.f_code.co_name,
                       "file":frame.f_code.co_filename,"line":frame.f_lineno,
                       "return":repr(arg),"locals":{k:repr(v) for k,v in frame.f_locals.items() if k in {"query","question","project_docs","item","content","title","heading_path","chunks","candidates","selected","source_taxonomy"}}})
    if event != "return" or not str(frame.f_code.co_filename).endswith("_docs_context_projection_core.py") or frame.f_code.co_name != "project_docs_context":
        return
    diagnostics = frame.f_locals.get("projection_diagnostics")
    EVENTS.append({"node_id":CURRENT,"max_tokens":frame.f_locals.get("max_tokens"),
                   "diagnostics":diagnostics,"prepared":frame.f_locals.get("prepared"),
                   "retrieval_input":frame.f_locals.get("retrieval"),
                   "initially_ranked":frame.f_locals.get("initially_ranked"),
                   "fallback_ids":frame.f_locals.get("fallback_ids"),
                   "output":arg})


def pytest_runtest_call(item):
    global CURRENT
    CURRENT = item.nodeid
    sys.setprofile(profile)


def pytest_runtest_teardown(item):
    sys.setprofile(None)
    with Path(os.environ["PROJECTION_OBSERVER_OUTPUT"]).open("a") as stream:
        for event in EVENTS:
            stream.write(json.dumps(event,ensure_ascii=False,default=str)+"\n")
    EVENTS.clear()

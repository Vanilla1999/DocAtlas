"""Passive installed-public-path diagnostics; no retrieval replacements or oracle input."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from receipts import sha, save
import run as runner


class BoundaryObserver:
    """Copy executed boundaries and budget trials, not the noisy recheck loop.

    All sources are recorded (no gold-dependent filter). Limits fail explicitly;
    observed objects are never mutated. sys.setprofile changes timing only.
    """

    def __init__(self, output):
        self.output = output
        self.active = None
        self.events = []
        self.errors = []
        self.calls = 0

    @staticmethod
    def chunk(value):
        if isinstance(value, dict):
            text = value.get("text") or value.get("content") or value.get("snippet") or ""
            metadata = value.get("metadata") or {}
            if isinstance(value.get("metadata_json"), str):
                metadata = json.loads(value["metadata_json"] or "{}")
            source = value.get("source") or value.get("path") or value.get("path_or_url")
            index = value.get("chunk_index")
            row_id = value.get("id")
        else:
            text, metadata, source, index = value.text, value.metadata or {}, value.source, value.chunk_index
            row_id = metadata.get("section_id")
        return dict(source=source, chunk_index=index, section_id=row_id, text=text,
                    text_sha256=sha(text.encode()),
                    metadata={key: metadata.get(key) for key in
                              ("char_start", "char_end", "line_start", "line_end", "ranking", "acquisition")})

    def emit(self, stage, **fields):
        if len(self.events) >= 4096:
            raise ValueError("observer event ceiling; incomplete diagnostic, never infer absence")
        self.events.append(dict(sequence=len(self.events) + 1, stage=stage, **fields))

    def profile(self, frame, event, result):
        name = frame.f_code.co_name
        module = frame.f_globals.get("__name__", "")
        if name == "call_docs_tool_payload" and module == "docmancer.mcp._docs_server_part01":
            if event == "call" and frame.f_locals.get("name") == "get_docs_context":
                self.calls += 1
                self.active = self.calls
                self.events, self.errors = [], []
            elif event == "return" and self.active is not None:
                save(self.output / f"call-{self.active}.json", dict(
                    request=frame.f_locals.get("args"), events=self.events, errors=self.errors,
                    event_count=len(self.events), omitted_events=0 if not self.errors else "UNKNOWN"))
                self.active = None
            return
        if self.active is None or not module.startswith("docmancer.") or event != "return":
            return
        try:
            local = frame.f_locals
            if name in ("_search_rows", "acquire_candidates", "select_experimental_candidates"):
                rows = result or []
                if len(rows) > 1024:
                    raise ValueError("observer source ceiling")
                self.emit(name + ".output", count=len(rows), rows=[self.chunk(row) for row in rows])
                if name == "select_experimental_candidates":
                    self.emit("selection.exclusions", rows=[dict(candidate=self.chunk(row), reason=reason,
                              original_ordinal=ordinal) for row, reason, ordinal in local.get("excluded", [])])
            elif name == "admit_original_literal_context" and frame.f_back.f_code.co_name != "recheck_source_valid_candidate":
                candidate = local.get("candidate") or {}
                self.emit("admission", candidate=self.chunk({**candidate, "content": local.get("evidence_text", "")}),
                          accepted=result is not None, reason=(result or {}).get("reason"))
            elif name in ("project_native_rank_context", "project_docs_context", "enforce_experimental_context_budget"):
                if not isinstance(result, tuple) or len(result) != 2:
                    raise ValueError("missing boundary tuple")
                payload, snapshot = result
                # Full final source representation, plus independently hashable binding coordinates.
                from docmancer.docs.application.projection_decision_trace import _flow_row
                self.emit(name + ".output", count=len(payload.get("sources") or []),
                          rows=[dict(public=row, binding=_flow_row(row, (snapshot.get(row.get("evidence_id")) or {}).get("source")))
                                for row in payload.get("sources") or []])
                if name == "enforce_experimental_context_budget":
                    self.emit("budget.ledger", ledger=local.get("ledger", {}),
                              all_omitted_evidence_ids=local.get("omitted", []))
            elif name == "experimental_context_cost":
                parent = frame.f_back
                if parent and parent.f_code.co_name == "enforce_experimental_context_budget":
                    p = parent.f_locals
                    option = p.get("option")
                    self.emit("budget.cost", cost=result, cap=p.get("cap"),
                              over_cap=result > p["cap"] if p.get("cap") is not None else None,
                              option=option, option_index=p.get("index"),
                              selected_ids=[row["evidence_id"] for row in p.get("selected", [])])
        except Exception as exc:
            self.errors.append(dict(function=name, error_type=type(exc).__name__, error=str(exc)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "worker", "output", "work"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    diagnostics = args.output.parent / "boundaries"
    if diagnostics.exists():
        raise ValueError("fresh diagnostic directory required")
    observer = BoundaryObserver(diagnostics)
    old = sys.getprofile()
    try:
        sys.setprofile(observer.profile)
        code = runner.run(args.manifest, args.output, args.work, args.worker)
    finally:
        sys.setprofile(old)
    save(diagnostics / "OBSERVER_STATUS.json", dict(calls=observer.calls, active=observer.active,
                                                   timing_comparable=False, product_replacements=0))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

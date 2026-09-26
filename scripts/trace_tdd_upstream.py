#!/usr/bin/env python3
"""Observe upstream pools during the unchanged projection diagnostic run."""
from __future__ import annotations
import json
from pathlib import Path
import sys
from pydantic import BaseModel
import trace_tdd_projection as projection


def main():
    output = Path(sys.argv[sys.argv.index('--output') + 1]).resolve()
    events = []
    def encode(value):
        return value.model_dump(mode='json') if isinstance(value, BaseModel) else projection.encode(value)
    def profile(frame, event, arg):
        if event != 'return':
            return
        filename = frame.f_code.co_filename
        name = frame.f_code.co_name
        if not (filename.endswith('/_project_docs_service_part03.py') and name == 'query_project_docs'
                or filename.endswith('/project_doc_ranking.py') and name == 'rerank_project_doc_chunks'):
            return
        values = frame.f_locals
        record = {'function': name, 'result': arg}
        for key in ('project_path', 'query', 'question', 'chunks', 'authoritative_chunks',
                    'supplemental_chunks_by_query', 'candidates', 'selected', 'effective_limit',
                    'budget', 'supplemental_budget', 'filters', 'scored'):
            if key in values:
                record[key] = values[key]
        # Freeze while the frame exists: later functions may mutate metadata.
        events.append(json.loads(json.dumps(record, default=encode, ensure_ascii=False)))
    previous = sys.getprofile()
    try:
        sys.setprofile(profile)
        projection.main()
    finally:
        sys.setprofile(previous)
    report = json.loads(output.read_text())
    report['upstream_observations'] = events
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('upstream observations:', len(events))


if __name__ == '__main__':
    main()

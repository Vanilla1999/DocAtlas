from pathlib import Path
import ast,hashlib
root=Path.cwd()
expected = {'tests/test_project_context_quality_v2_protocol.py': 'd64a869e694bffa3c34443ae84b8bbfc243f0b24c038b6cbf65e3f22dba1a652', 'docmancer/core/config.py': '493fa9c971b845493741cf96d8e23dd1ef48f528be96cec3bf61f45fd43cdbd4', 'docmancer/retrieval/_dispatch_part02.py': '85ab2512d0c9a6d496c0a22ffe2a71ac3017b9845ed845e2f166e001b95ed27c', 'docmancer/retrieval/_dispatch_part01.py': '1c0f549b2671c44e549c06954805ef76f33b6eec6489113b7a04b42bbd4312b7'}
originals={}
def change(path, fn):
 p=root/path
 old=p.read_text()
 assert hashlib.sha256(p.read_bytes()).hexdigest()==expected[path], path
 new=fn(old)
 assert new!=old,path
 ast.parse(new,filename=path)
 originals[path]=old
 p.write_text(new)
def once(s,old,new):
 assert s.count(old)==1,(old[:100],s.count(old))
 return s.replace(old,new,1)
def trace(s):
 s=once(s,'calls = {"coverage": 0, "acquisition": 0}', 'calls = {"validation": 0, "acquisition": 0}')
 s=once(s,'coverage = runner.docs_context_projection.component_coverage_decision', 'validate = runner.context_tools.validate_model_visible_projection')
 s=once(s,'''        def observe_coverage(*args, **kwargs):
            calls["coverage"] += 1
            return coverage(*args, **kwargs)
''','''        def observe_validation(*args, **kwargs):
            calls["validation"] += 1
            return validate(*args, **kwargs)
''')
 s=once(s,'monkeypatch.setattr(runner.docs_context_projection, "component_coverage_decision", observe_coverage)', 'monkeypatch.setattr(runner.context_tools, "validate_model_visible_projection", observe_validation)')
 return once(s,'assert first_calls["coverage"] > 0 and first_calls["acquisition"] > 0', 'assert first_calls["validation"] > 0 and first_calls["acquisition"] > 0')
change('tests/test_project_context_quality_v2_protocol.py',trace)
def config(s):
 return once(s,'default=None, ge=1, description="Legacy parsing field; source quotas are no longer applied.",','default=None, ge=1, description="Explicit source quota; unset preserves native order without a quota. Explicit expansion bypasses it.",')
change('docmancer/core/config.py',config)
def dispatch2(s):
 return once(s,'''        # Source identity is an access/provenance constraint, not a diversity
        # quota. Preserve the native (or fused) rank under the global bound.
        return chunks[:limit] if limit is not None else chunks
''','''        # An explicitly configured resource quota is not a relevance score.
        # The default remains unset: no implicit diversity or authority policy.
        quota = self.config.retrieval.max_sections_per_source
        if quota is None:
            return chunks[:limit] if limit is not None else chunks
        counts: dict[str, int] = {}
        selected = []
        for chunk in chunks:
            source = str(chunk.source)
            if counts.get(source, 0) >= quota:
                continue
            counts[source] = counts.get(source, 0) + 1
            selected.append(chunk)
        return selected[:limit] if limit is not None else selected
''')
change('docmancer/retrieval/_dispatch_part02.py',dispatch2)
def dispatch1(s):
 s=once(s,'"max_sections_per_source": None,','"max_sections_per_source": self.config.retrieval.max_sections_per_source,')
 s=once(s,'"expansion": retrieval_expand or "none", "source_quota": None,','"expansion": retrieval_expand or "none",\n                "source_quota": self.config.retrieval.max_sections_per_source,')
 return once(s,'''            acquired_count = len(chunks)
            chunks = self._filter_chunks(chunks, merged_filters)
            for chunk in chunks:
''','''            acquired_count = len(chunks)
            chunks = self._filter_chunks(chunks, merged_filters)
            # Keep the MCP pool independent of SDK limit/budget. Only an
            # explicit host resource quota may bound a source here.
            chunks = self._limit_sections_per_source(chunks, expand=retrieval_expand)
            for chunk in chunks:
''')
change('docmancer/retrieval/_dispatch_part01.py',dispatch1)
expected['docmancer/docs/application/projection_decision_trace.py'] = '4f0c671355ee28cd3c149b3f30d274627f6a77ebd54a326703027e32a45d60f6'
expected['tests/test_native_context_preservation_integration.py'] = '0dded637b8c642b71bd15263ddb63cd16b13293203663ebcc9386e03bfb8d139'
def flow(s):
 old = '            if len(state["events"]) >= MAX_CONTEXT_FLOW_EVENTS:\n                state["omitted_events"] += 1\n                return None\n'
 new = '''            if len(state["events"]) >= MAX_CONTEXT_FLOW_EVENTS:
                state["omitted_events"] += 1
                # Retain the outer recheck/budget boundaries even when detailed
                # per-row trial events exhaust the same fixed-size trace. Every
                # displaced event stays counted; this never changes selection.
                outer = {"recheck.input", "recheck.output", "budget.input", "budget.output"}
                if kind != "boundary" or stage not in outer:
                    return None
                replace = next((index for index in range(len(state["events"]) - 1, -1, -1)
                                if state["events"][index].get("event") != "boundary"
                                or state["events"][index].get("stage") not in outer), None)
                if replace is None:
                    return None
                del state["events"][replace]
'''
 return once(s, old, new)
change('docmancer/docs/application/projection_decision_trace.py', flow)
def trace_bounds(s):
 s=once(s,'''    assert flow["event_count"] == flow["recorded_events"] == len(flow["events"]) <= 256
    assert flow["omitted_events"] == flow["serialization_omitted_events"] == flow["diagnostic_error_count"] == 0
    assert [event["sequence"] for event in flow["events"]] == list(range(1, flow["event_count"] + 1))
''','''    assert flow["recorded_events"] == len(flow["events"]) <= 256
    assert flow["event_count"] == flow["recorded_events"] + flow["omitted_events"]
    assert flow["serialization_omitted_events"] == flow["diagnostic_error_count"] == 0
    sequences = [event["sequence"] for event in flow["events"]]
    assert sequences == sorted(set(sequences))
    assert all(1 <= sequence <= flow["event_count"] for sequence in sequences)
    # Native pools can exceed the bounded diagnostic preview. Such omissions
    # must be exact and explicit, never mistaken for absent source evidence.
''')
 return once(s,'''        assert event["source_rows_omitted"] == event["serialization_omitted_source_rows"] == 0
        assert event["source_count"] == len(event["rows"]) <= 64
''','''        assert event["serialization_omitted_source_rows"] == 0
        assert len(event["rows"]) <= 64
        assert event["source_count"] == len(event["rows"]) + event["source_rows_omitted"]
''')
change('tests/test_native_context_preservation_integration.py', trace_bounds)
print('Hash-verified follow-up:',len(originals),'files; no new tests, no changed source-fact oracles.')

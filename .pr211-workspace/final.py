from pathlib import Path
import ast, hashlib, json
root = Path.cwd()
expected = {
 'tests/test_heuristic_removal_public_integration.py': '5d588075de4f97a929b3f0985b9404ffd9fc927a2d814cca66400448f455c705',
 'tests/test_project_context_quality_v2_protocol.py': 'c7e0da3418badb6281bee3704944e06c4a9759e837902c46babdead552e81c0f',
}
def once(text, old, new):
 assert text.count(old) == 1, (old[:100], text.count(old))
 return text.replace(old,new,1)
for name, digest in expected.items():
 p = root / name
 assert hashlib.sha256(p.read_bytes()).hexdigest() == digest, name
 s = p.read_text()
 if name.endswith('test_project_context_quality_v2_protocol.py'):
  s = once(s, '''        trace = on["diagnostics"]["projection_observation"]["returned_core_diagnostics"]["decision_trace"]
        assert trace["events"]["recorded_count"] > 0
''', '''        # The removed heuristic projector no longer emits decision_trace.
        # Observe the source-native recheck and terminal-budget events instead.
        trace = on["diagnostics"]["projection_observation"]["returned_core_diagnostics"]["context_flow"]
        assert trace["observation"] == "recorded"
        assert 0 < trace["recorded_events"] == len(trace["events"]) <= 256
        assert trace["event_count"] == trace["recorded_events"] + trace["omitted_events"]
        assert trace["serialization_omitted_events"] == trace["diagnostic_error_count"] == 0
        boundaries = {event["stage"] for event in trace["events"] if event["event"] == "boundary"}
        assert {"recheck.input", "recheck.output", "budget.input", "budget.output"} <= boundaries
''')
 else:
  s = once(s, '''    config.retrieval.default_mode = "hybrid"
    config.retrieval.max_sections_per_source = 1
''', '''    config.retrieval.default_mode = "hybrid"
    # Native-order completeness uses the ordinary default, not an explicit
    # one-window cap. The capped arm below independently checks that contract.
    assert config.retrieval.max_sections_per_source is None
''')
  s = once(s, '''        evidence.append({"mode": result.mode_used, "sources": [chunk.source for chunk in result.chunks],
                         "texts": [chunk.text for chunk in result.chunks], "counts": result.candidate_counts})
''', '''        # Reuse the real indexed vector/lexical backends for an explicit cap,
        # then bypass that cap only through an explicit page expansion request.
        config.retrieval.max_sections_per_source = 1
        try:
            capped = dispatcher_for_agent(agent, mode=mode).run(
                "observatory", mode=mode, limit=10, budget=4000, expand="none",
                filters={"forbidden_sources": ["secret.md"]}, allow_degraded=mode == "hybrid",
            )
            expanded = dispatcher_for_agent(agent, mode=mode).run(
                "observatory", mode=mode, limit=10, budget=4000, expand="page",
                filters={"forbidden_sources": ["secret.md"]}, allow_degraded=mode == "hybrid",
            )
        finally:
            config.retrieval.max_sections_per_source = None
        assert len(capped.chunks) == 1, capped
        assert capped.chunks[0].text in {chunk.text for chunk in result.chunks}
        for packet in (capped, expanded):
            assert packet.mode_used == expected_mode
            assert packet.failures == result.failures
            assert packet.chunks
            assert all(chunk.source == "observatory.md" and chunk.text in text
                       and "HIDDEN_97" not in chunk.text for chunk in packet.chunks)
        for fact in ("Observatory aperture is 73 mm.", "Observatory shutter waits 19 seconds.",
                     "Observatory archive retains 41 nights."):
            assert any(fact in chunk.text for chunk in expanded.chunks), expanded
        evidence.append({"mode": result.mode_used, "sources": [chunk.source for chunk in result.chunks],
                         "texts": [chunk.text for chunk in result.chunks], "counts": result.candidate_counts,
                         "explicit_cap_texts": [chunk.text for chunk in capped.chunks],
                         "explicit_page_texts": [chunk.text for chunk in expanded.chunks]})
''')
 assert s != p.read_text()
 ast.parse(s, filename=name)
 p.write_text(s)
print(json.dumps({n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in expected}, indent=2))

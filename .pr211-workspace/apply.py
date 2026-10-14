from pathlib import Path
import ast, hashlib, json
root=Path.cwd()
manifest=json.loads((root/'.pr211-workspace/manifest.json').read_text())
for name, digest in manifest['original_sha256'].items():
 assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest, ('base mismatch', name)
originals={}
def change(name, fn):
 p=root/name;old=p.read_text();new=fn(old)
 assert old!=new,name
 originals[name]=old
 p.write_text(new)
def replace_once(s, old, new):
 assert s.count(old)==1,(old[:100],s.count(old))
 return s.replace(old,new,1)

def finalizer(s):
 s=replace_once(s, '''The ordinary default has no new cap.  Experimental limits apply to the complete
JSON text returned by Docs MCP, using its existing offline codec and UTF-8 proxy.''', '''The source-native default applies its explicit cap to the complete JSON text
returned by Docs MCP, using the offline codec and UTF-8 proxy.''')
 return replace_once(s, '''    payload.update(context_unassessed=True, admission_contract="source_only_heuristic_removal_v1")
''', '''    veto = payload.get("delivery_decision")
    if not payload.get("sources") and isinstance(veto, dict) and veto.get("deliverable") is False:
        # An operational denial contains no candidate context to assess. Keep
        # its source/consent cause and confirmation fields ahead of optional
        # admission annotations, including under a small final DTO budget.
        payload.pop("context_unassessed", None)
        payload.pop("admission_contract", None)
        _refresh_estimate(payload)
        return
    payload.update(context_unassessed=True, admission_contract="source_only_heuristic_removal_v1")
''')
change('docmancer/docs/application/experimental_context_finalization.py',finalizer)

def native_test(s):
 s=replace_once(s, '''        model_forwards = sum(receipt["selection"]["model_forwards"]
                             for record in records.values() for receipt in record["receipts"])
        operations.update(model_forwards=model_forwards, optional_model_modules_before=imported_before,
                          optional_model_modules_after=imported_after)
''','''        model_work = [receipt["selection"]["model_work"]
                      for record in records.values() for receipt in record["receipts"]]
        # These are observational receipts, not measured model-forward counts.
        operations.update(selection_model_work=model_work, optional_model_modules_before=imported_before,
                          optional_model_modules_after=imported_after)
''')
 s=replace_once(s, '''            assert selection["mode"] == "budget" and selection["model_forwards"] == 0
''','''            assert selection["mode"] == "native_acquisition_rank"
            assert selection["model_work"] == "none"
''')
 return replace_once(s, '''        assert imported_before == imported_after and model_forwards == 0
''','''        assert imported_before == imported_after and model_work == ["none", "none"]
''')
change('tests/test_native_context_preservation_integration.py',native_test)

def modes_test(s):
 s=replace_once(s,'''        assert len(observed) == 1 and observed[0]["mode"] == "budget"
        assert observed[0]["model_forwards"] == 0
''','''        assert len(observed) == 1 and observed[0]["mode"] == "native_acquisition_rank"
        assert observed[0]["model_work"] == "none"
''')
 return replace_once(s,'''        record_property("model_forwards", 0)
''','''        record_property("selection_model_work", observed[0]["model_work"])
''')
change('tests/test_experimental_selection_modes_integration.py',modes_test)

def observation(s):
 s=replace_once(s,'from docmancer.docs.application import docs_context_projection\n','from docmancer.docs.application import experimental_context_finalization\n')
 s=replace_once(s,'''    select = docs_context_projection.context_selection_decision
''','''    # Observe the actual source-native consumer, not aliases of retired
    # projectors. The observer forwards operands/results without replacing
    # retrieval, selection or validation. Native reads issue no component proof.
    select = experimental_context_finalization.context_selection_decision
''')
 start=s.index('    coverage = docs_context_projection.component_coverage_decision\n')
 end=s.index('    def capture_delivery(',start)
 s=s[:start]+s[end:]
 s=replace_once(s,'''        patch.object(docs_context_projection, "context_selection_decision", capture_selection),
''','''        patch.object(experimental_context_finalization, "context_selection_decision", capture_selection),
''')
 return replace_once(s,'''        patch.object(docs_context_projection, "component_coverage_decision", capture_coverage),
''','')
change('scripts/run_project_docs_self_host_gate.py',observation)

def smoke(s):
 s=replace_once(s,'''    assert answer.get("status") == "ok", answer
    assert answer.get("kind") in {"docs_answer", "docs_context"}, answer
    if answer["kind"] == "docs_context":
''','''    assert answer.get("kind") in {"docs_answer", "docs_context"}, answer
    if answer["kind"] == "docs_context":
        # A bounded retrieval-only packet may omit other candidates. The
        # required fact must still be delivered in source text below; status
        # alone is neither a completeness oracle nor answer authority.
        assert answer.get("status") in {"ok", "truncated"}, answer
''')
 s=replace_once(s,'''    else:
        assert answer.get("support_status") == "supported", answer
''','''    else:
        assert answer.get("status") == "ok", answer
        assert answer.get("support_status") == "supported", answer
''')
 return replace_once(s,'''    assert required_fragment in json.dumps(answer), answer
    assert answer.get("sources"), answer
''','''    assert answer.get("sources"), answer
    assert any(required_fragment in source.get("snippet", "") for source in answer["sources"]), answer
''')
change('scripts/docs_mcp_stdio_smoke.py',smoke)

def cache(s):
 s=replace_once(s,'import ipaddress\n','import gzip\nimport hashlib\nimport ipaddress\n')
 insertion='''@pytest.fixture(scope="session", autouse=True)
def isolated_tokenizer_cache(tmp_path_factory):
    """Provide tiktoken's pinned vocabulary without DNS or a developer cache.

    This is environment preparation for real integration scenarios, not a
    replacement encoder or a product result. Child processes inherit the same
    isolated cache; the original host setting is restored after the session.
    """
    cache = tmp_path_factory.mktemp("docatlas-tokenizer-cache")
    vocabulary = Path(__file__).resolve().parents[1] / "docmancer/docs/data/o200k_base.tiktoken.gz"
    data = gzip.decompress(vocabulary.read_bytes())
    expected = "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError("pinned integration tokenizer vocabulary hash mismatch")
    url = "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken"
    (cache / hashlib.sha1(url.encode()).hexdigest()).write_bytes(data)
    previous = os.environ.get("TIKTOKEN_CACHE_DIR")
    os.environ["TIKTOKEN_CACHE_DIR"] = str(cache)
    try:
        yield cache
    finally:
        if previous is None:
            os.environ.pop("TIKTOKEN_CACHE_DIR", None)
        else:
            os.environ["TIKTOKEN_CACHE_DIR"] = previous


'''
 return replace_once(s,'def pytest_configure(config):\n',insertion+'def pytest_configure(config):\n')
change('tests/conftest.py',cache)
change('.github/workflows/ci.yml',lambda s:s.replace('pip install -e ".[dev]"','pip install -e ".[dev,embeddings-openai]"'))

def evidence(s):
 old='''      - name: Prepare tokenizer cache
        run: echo "TIKTOKEN_CACHE_DIR=$RUNNER_TEMP/source-native-tokenizer" >> "$GITHUB_ENV"
'''
 new='''      - name: Prepare isolated integration evidence paths
        run: |
          echo "TIKTOKEN_CACHE_DIR=$RUNNER_TEMP/source-native-tokenizer" >> "$GITHUB_ENV"
          echo "PYTEST_DOCATLAS_ARTIFACT_DIR=$RUNNER_TEMP/source-native-results/scenarios" >> "$GITHUB_ENV"
'''
 assert s.count(old)==2
 s=s.replace(old,new,1)
 return replace_once(s,'''            tests/test_native_context_preservation_integration.py \\
''','''            tests/test_native_context_preservation_integration.py \\
            tests/test_experimental_selection_modes_integration.py \\
''')
change('.github/workflows/source-native-integration.yml',evidence)

for name, digest in manifest['candidate_sha256'].items():
 assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest, ('candidate mismatch', name)
 if name.endswith('.py'): ast.parse((root/name).read_text(),filename=name)
assert set(originals)==set(manifest['original_sha256'])==set(manifest['candidate_sha256'])
print('Applied and hash-verified', len(originals), 'files. No unit tests or oracle changes.')

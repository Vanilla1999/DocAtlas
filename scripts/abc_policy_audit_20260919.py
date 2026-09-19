#!/usr/bin/env python3
"""One harness correctness correction, not a relevance treatment.
Reuse the immutable same-call candidate captures from the completed ABC run.
No changed questions, candidate generation, model, rank/packing parameters.
Restore later production source-taxonomy risks before experimental selection.
"""
from pathlib import Path
import os
previous = Path(os.environ['ABC_PREVIOUS'])
source = (previous / 'runner.py').read_text(encoding='utf-8')
start = source.index('cfg=DocmancerConfig()')
end = source.index('def allowed(')
load = '''
previous = Path(os.environ['ABC_PREVIOUS'])
files=json.loads((previous/'source_files.json').read_text())
native=json.loads((previous/'native.json').read_text())
allrows=json.loads((previous/'index_rows.json').read_text())
binding_rejections=[]
from docmancer.docs.domain.project_doc_ranking import project_source_taxonomy
from docmancer.docs.domain.lifecycle_policy import lifecycle_intent as runtime_lifecycle_intent
policy_added=[]
for rows in [allrows,*[case['pool'] for case in native]]:
    for x in rows:
        taxonomy=project_source_taxonomy(x['path'],doc_scope=x.get('doc_scope'),module_path=x.get('module_path'))
        flags=set(x.get('risk_flags') or ()) | set(taxonomy.get('risk_flags') or ())
        if flags != set(x.get('risk_flags') or ()):
            policy_added.append({'path':x['path'],'flags':sorted(flags)})
        x['risk_flags']=sorted(flags)
        # Indexed project_file is adapted to project_doc at the project-context boundary.
        assert x.get('source_class') in ('project_file','project_doc')
        x['source_class']='project_doc'
        raw=(ROOT/x['path']).read_text(encoding='utf-8')
        assert digest(raw)==x['source_file_sha256']
        assert raw[x['char_start']:x['char_end']]==x['content']
dump('policy_correction.json',{'basis':'existing project_source_taxonomy risk flags and runtime lifecycle intent',
    'added':list({r['path']:r for r in policy_added}.values()),
    'frozen_previous_artifact':10579161761,
    'ranking_changed':False,'model_changed':False,'questions_changed':False,
    'metadata_scope':'Not a proof of all source-policy/continuation behavior; this corrects one detected missing adaptation.'})
dump('native.json',native); dump('index_rows.json',allrows); dump('source_files.json',files)
'''
source = source[:start] + load + source[end:]
old = "lifecycle_intent='history' if 'history' in q.casefold() or 'historical' in q.casefold() else 'current'"
assert old in source
source = source.replace(old, 'lifecycle_intent=runtime_lifecycle_intent(q)')
old = "rev=HfApi().model_info(name).sha"
assert old in source
source = source.replace(old, "rev='233902d25c440f23af6f7d6e94d2946bac0bee0a'")
marker = "validation_errors=["
assert marker in source
source = source.replace(marker, '''
research=next(x for x in allrows if 'research_artifact' in x.get('risk_flags',[]))
assert not allowed(research,'documentation',{})
controls.append({'mutation':'source_taxonomy_research_not_just_explicit_flag','rejected':True})
'''+marker, 1)
# Retain exact executed program in artifact, including the correction itself.
(Path(os.environ['ABC_OUT'])).mkdir(parents=True,exist_ok=True)
(Path(os.environ['ABC_OUT'])/'executed_program.py').write_text(source,encoding='utf-8')
exec(compile(source, str(Path(__file__).resolve()), 'exec'))

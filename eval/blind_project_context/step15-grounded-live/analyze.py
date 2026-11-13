"""Offline mechanical scope, source bytes, line delivery and usage audit; no semantic grade."""
import collections, hashlib, json, pathlib, re
HERE=pathlib.Path(__file__).resolve().parent
OLD=HERE.parent/'step14-host-language-live'
LIVE=HERE/'attempt-02/live-02'
def load(p):return json.loads(p.read_text())
def save(p,v):
    with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
sources=load(HERE/'sources.json');urls={s['url']:s for s in sources}
aliases={s['url'].removesuffix('.md'):s for s in sources}|urls
source_text={s['path']:(HERE/'source-bytes'/s['path']).read_text() for s in sources}
for s in sources:
    assert sha(HERE/'source-bytes'/s['path'])==s['sha256']==sha(OLD/'frozen-corpus'/s['path'])
common=load(OLD/'attempt-02/A/V-M1/config.json')['agents']['measure']['system'].split('\n\nBound documentation project:')[0]
tasks=load(OLD/'tasks.json'); metrics=[]; audits=[]
for task in tasks:
    case=LIVE/'D'/task['id'];m=load(case/'accounting.json');receipt=load(case/'runtime/receipt.json')
    events=rows(case/'capture/events.jsonl');stdio=rows(case/'stdio-events.jsonl')
    requests=[e for e in events if e['type']=='http.request'];models=[]
    for request in requests:
        b=request['data'];b=json.loads(b) if isinstance(b,str) else b
        models.append(dict(hook=request['model'],wire_model=b.get('model'),reasoning=b.get('reasoning')))
    first=load(case/'capture/first-provider-request.json');b=first['body'];b=json.loads(b) if isinstance(b,str) else b
    serialized=json.dumps(b,ensure_ascii=False)
    visible_tools=[t.get('name') for t in b.get('tools',[])]
    # JSON serialization escapes newlines; compare encoded paragraph content.
    common_present=json.dumps(common,ensure_ascii=False)[1:-1] in serialized
    responses={e['message']['id']:e['message'] for e in stdio if e['direction']=='response' and 'id' in e['message']}
    calls=[];delivered=[]
    for e in stdio:
        msg=e['message']
        if e['direction']!='request' or msg.get('method')!='tools/call':continue
        name=msg['params']['name'];args=msg['params'].get('arguments',{})
        valid=(name=='search_docs' and args.get('library')=='meridian-step15-e62fa9e3' and args.get('version')=='1.0.0') or (name=='fetch_url' and args.get('url') in urls and args.get('followRedirects') is False)
        assert valid
        response=responses[msg['id']]['result'];assert not response.get('isError')
        text='\n'.join(p['text'] for p in response.get('content',[]) if p.get('type')=='text')
        calls.append(dict(id=msg['id'],tool=name,arguments=args,scope_valid=valid,response_bytes=len(text.encode()),no_results=text.startswith('No results found')))
        entries=[]
        if name=='fetch_url':entries=[(args['url'],text)]
        else:
            matches=list(re.finditer(r'Result \d+: (\S+)\n+',text))
            for i,match in enumerate(matches):
                body=text[match.end():matches[i+1].start() if i+1<len(matches) else len(text)]
                body=re.sub(r'\n-{10,}\s*$','',body).strip('\n')
                entries.append((match.group(1),body))
        for url,body in entries:
            assert url in aliases,url
            source=aliases[url];lines=source_text[source['path']].splitlines()
            mapping=[dict(text=line,source_lines=[i+1 for i,s in enumerate(lines) if s==line]) for line in body.splitlines() if line.strip()]
            delivered.append(dict(request_id=msg['id'],url=url,path=source['path'],source_sha256=source['sha256'],delivered_sha256=hashlib.sha256(body.encode()).hexdigest(),
                all_nonblank_lines_exact=all(m['source_lines'] for m in mapping),line_mapping=mapping))
    answer_urls=re.findall(r'https?://[^\s)\]>]+',m['answer'])
    audit=dict(task=task['id'],models=models,all_model_requests_terra_low=all(x['wire_model']=='gpt-6.1-terra' and x['reasoning'].get('effort')=='low' and x['hook']['variant']=='low' for x in models),
       original_question_unchanged=m['original_question_in_first_request'],common_prompt_present=common_present,visible_tools=visible_tools,
       only_grounded_tools_visible=set(visible_tools)<={'grounded_search_docs','grounded_fetch_url'},calls=calls,delivered=delivered,
       answer_urls=answer_urls,all_answer_urls_allowlisted=all(u.split('#')[0] in aliases for u in answer_urls),
       index_unchanged=load(case/'index-after.json')==load(HERE/'attempt-02/index-inspection.json'),
       semantic_grade=None,line_mapping_boundary='Checks delivered English source lines only, not whether the answer covers required facts; original blank lines may be omitted.')
    assert audit['all_model_requests_terra_low'] and audit['original_question_unchanged'] and audit['common_prompt_present'] and audit['only_grounded_tools_visible']
    assert audit['index_unchanged'] and all(d['all_nonblank_lines_exact'] for d in delivered)
    audits.append(audit)
    metrics.append(dict(arm='D',task=task['id'],usage=m['usage'],provider_requests=m['provider_requests'],seconds=receipt['seconds'],model_tool_calls=m['model_tool_calls'],actual_mcp_calls=m['actual_mcp_calls'],
       answer=m['answer'],answer_source=str((case/'answer.md').relative_to(HERE)),quality=None,source_facts_found=None,source_facts_delivered=None,measurement_gap=None))
historic=load(OLD/'results.json')
totals={}
for arm in 'ABCD':
    ss=[m for m in (metrics if arm=='D' else historic['sessions']) if m['arm']==arm]
    def total(values):return sum(values) if all(isinstance(v,(int,float)) for v in values) else None
    totals[arm]=dict(sessions=len(ss),provider_requests=total([s['provider_requests'] for s in ss]),seconds=total([s.get('seconds') for s in ss]),
      usage={k:total([s['usage'].get(k) for s in ss]) for k in ('input','output','cached','uncached','cache_write','reasoning')},
      actual_mcp_calls=dict(sum((collections.Counter(s.get('actual_mcp_calls',{})) for s in ss),collections.Counter())),
      model_tool_calls=dict(sum((collections.Counter(s.get('model_tool_calls',{})) for s in ss),collections.Counter())),
      boundary='new sequential D' if arm=='D' else 'historical step14; preserve its measurement gaps')
save(HERE/'scope-source-model-audit.json',audits)
save(HERE/'preliminary-results.json',dict(status='4_COMPLETED_SEMANTIC_REVIEW_PENDING',sessions=metrics,totals=totals,historical_results_sha256=sha(OLD/'results.json'),historical_measurement_gaps=[dict(arm=s['arm'],task=s['task'],gap=s['measurement_gap']) for s in historic['sessions'] if s.get('measurement_gap')],
   no_simultaneous_randomization=True,model_retries=0,lexical_mode=True,preparation_calls_excluded=True,orchestration_agent_usage_included=False))
print(json.dumps(totals,indent=2))

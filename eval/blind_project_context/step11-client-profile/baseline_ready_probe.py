"""One ready historical inventory request through real OpenCode; no tools/models."""
import argparse
from copy import deepcopy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prior', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--opencode', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.absolute()
    output.mkdir(exist_ok=False)
    prior = json.loads((args.prior/'baseline/opencode.json').read_text())
    question = json.loads((args.prior/'plan.json').read_text())['question']
    save(output/'plan.json', {'provider_requests':1,'tool_calls':0,'model_calls':0,
        'label':'warm/ready historical inventory; no historical trajectory claim',
        'prior_config_sha256':hashlib.sha256((args.prior/'baseline/opencode.json').read_bytes()).hexdigest(),
        'changes':'isolated location/provider endpoint/observer readiness only; agent system, permissions and native schemas unchanged'})
    requests=[]
    errors=[]
    class Provider(BaseHTTPRequestHandler):
        def log_message(self,*_): pass
        def do_POST(self):
            raw=self.rfile.read(int(self.headers['Content-Length']))
            body=json.loads(raw); requests.append(body)
            (output/f'provider-request-{len(requests)}.json').write_bytes(raw)
            system='\n'.join(str(m.get('content','')) for m in body['messages'] if m['role']=='system')
            if len(requests)!=1: errors.append('unexpected provider retry')
            if 'tools.docatlas.get_docs_context' not in system or 'tools.docatlas.docs_status' not in system:
                errors.append('ready Code Mode catalog missing')
            if [m['content'] for m in body['messages'] if m['role']=='user'][-1] != question:
                errors.append('question changed')
            chunks=[{'id':'inventory','object':'chat.completion.chunk','created':0,'model':'capture',
                'choices':[{'index':0,'delta':{'role':'assistant','content':'Client inventory recorded.'},'finish_reason':None}]},
                {'id':'inventory','object':'chat.completion.chunk','created':0,'model':'capture',
                'choices':[{'index':0,'delta':{},'finish_reason':'stop'}]}]
            data=(''.join('data: '+json.dumps(x)+'\n\n' for x in chunks)+'data: [DONE]\n\n').encode()
            self.send_response(200); self.send_header('Content-Type','text/event-stream')
            self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    provider=ThreadingHTTPServer(('127.0.0.1',0),Provider)
    threading.Thread(target=provider.serve_forever,daemon=True).start()
    observer=output/'observer'; observer.mkdir()
    (observer/'index.js').write_text('import {writeFileSync} from "node:fs";\n'
      'export default {id:"ready-baseline-inventory",async setup(ctx){\n'
      ' await ctx.session.hook("title",event=>{event.result="Documentation";});\n'
      ' await ctx.tool.hook("execute.before",()=>{throw new Error("inventory forbids tool execution");});\n'
      ' await ctx.session.hook("prompt",async event=>{\n'
      '  const started=performance.now();let checks=0;\n'
      '  while(true){const tools=await ctx.tool.list();checks++;\n'
      '   if(["docatlas_get_docs_context","docatlas_docs_status"].every(id=>tools.some(t=>t.id===id))){\n'
      '    writeFileSync(new URL("../readiness.json",import.meta.url),JSON.stringify({checks,elapsed_ms:Math.round(performance.now()-started),deadline_ms:10000,tool_ids:tools.map(t=>t.id)},null,2));return;\n'
      '   }\n'
      '   const left=10000-(performance.now()-started);if(left<=0)throw new Error("baseline_mcp_not_ready");\n'
      '   await new Promise(resolve=>setTimeout(resolve,Math.min(25,left)));\n'
      '  }\n'
      ' });\n}};\n')
    config=deepcopy(prior)
    config['plugins']=[str(observer)]
    config['providers']['local-check']['settings']['baseURL']=f'http://127.0.0.1:{provider.server_port}/v1'
    assert config['agents']==prior['agents'] and config['mcp']==prior['mcp']
    save(output/'opencode.json',config)
    env={key:os.environ[key] for key in ('PATH','LANG','LC_ALL','SSL_CERT_FILE','SSL_CERT_DIR') if key in os.environ}
    for variable,folder in [('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('XDG_STATE_HOME','state'),('XDG_CACHE_HOME','cache')]:
        (output/folder).mkdir();env[variable]=str(output/folder)
    save(output/'config/opencode/opencode.json',{'update':'disable'})
    command=[str(args.opencode),'run','--standalone','--format','json','--agent','docs',
        '--model','local-check/capture','--title','Documentation']
    try:
        result=subprocess.run(command,input=question,text=True,capture_output=True,env=env,cwd=output,timeout=40)
        (output/'client.stdout').write_text(result.stdout)
        (output/'client.stderr').write_text(result.stderr)
        assert result.returncode==0 and len(requests)==1 and not errors, (result.returncode,errors)
        events=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        assert not any(event.get('type')=='tool_use' for event in events)
        from docmancer.docs.application.projection_tokenizer import projection_token_count
        count=lambda s:projection_token_count(s.encode())
        body=requests[0]
        measured={'first_system_tokens':sum(count(str(m.get('content',''))) for m in body['messages'] if m['role']=='system'),
            'first_tools_tokens':count(json.dumps(body.get('tools',[]),ensure_ascii=False,separators=(',',':'))),
            'tool_names':[t['function']['name'] for t in body.get('tools',[])],
            'system_permissions_mcp_unchanged':True,'model_calls':0,'provider_requests':1,'tool_calls':0,
            'passed':True,'boundary':'Ready inventory only, local o200k components; not billing or answer quality.'}
        save(output/'result.json',measured)
        print(json.dumps(measured,indent=2))
    finally:
        provider.shutdown()
        save(output/'runtime-counts.json',{'provider_requests':len(requests),'errors':errors,'model_calls':0})

if __name__=='__main__': main()

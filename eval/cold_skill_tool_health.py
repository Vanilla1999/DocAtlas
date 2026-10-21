"""Independent tool-generation health control: can this Qwen emit any MCP tool call?"""
from __future__ import annotations
import argparse, asyncio, hashlib, json, re
from pathlib import Path

async def main():
    p=argparse.ArgumentParser()
    for x in ('worker','model-python','tools','out'):p.add_argument('--'+x,required=True,type=Path)
    a=p.parse_args()
    for x in ('worker','tools','out'):setattr(a,x,getattr(a,x).resolve())
    # Keep virtualenv/bin/python symbolic path, not its system interpreter target.
    a.model_python=a.model_python.absolute()
    a.out.mkdir(parents=True,exist_ok=True)
    tools=json.loads(a.tools.read_text())
    assert {t['function']['name'] for t in tools}=={'docs_status','get_docs_context','prepare_docs'}
    worker=await asyncio.create_subprocess_exec(str(a.model_python),str(a.worker),'--identity',str(a.out/'MODEL.json'),
                     stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:
        first=await asyncio.wait_for(worker.stdout.readline(),timeout=900)
        ready=json.loads(first)
        assert ready.get('ready'),ready
        prompts=[
            ("status",[
              {"role":"system","content":"You are an assistant with three MCP tools. This is a tool-use test. You MUST call the specified tool. Do not respond with prose. Call a tool using the chat-template tool format."},
              {"role":"user","content":"Call docs_status with arguments {\"action\":\"project\",\"project_path\":\"/repo\",\"include_language\":true} NOW. Return a tool call, not an explanation."}]),
            ("docs",[
              {"role":"system","content":"You are an assistant with three MCP tools. You MUST call the specified tool. Do not respond with prose. Call a tool using the chat-template tool format."},
              {"role":"user","content":"Call get_docs_context with arguments {\"question\":\"What port does MeridianGate listen on?\",\"project_path\":\"/repo\",\"scope\":\"project\"} NOW."}]),
        ]
        records=[]
        for label,messages in prompts:
            obj={'id':label,'messages':messages,'tools':tools,'max_new_tokens':320}
            worker.stdin.write((json.dumps(obj,ensure_ascii=False)+'\n').encode());await worker.stdin.drain()
            line=await asyncio.wait_for(worker.stdout.readline(),timeout=600)
            reply=json.loads(line)
            raw=reply.get('raw','')
            blocks=re.findall(r'<tool_call>\s*(.*?)\s*</tool_call>',raw,re.DOTALL)
            parsed=[]
            for block in blocks:
                try:parsed.append(json.loads(block))
                except Exception as e:parsed.append({'error':str(e),'raw':block})
            records.append({'probe':label,'messages':messages,'model':reply,
                            'tool_calls':parsed,'valid_tool':any(v.get('name') in {'docs_status','get_docs_context'} for v in parsed)})
            print(json.dumps({'probe':label,'valid_tool':records[-1]['valid_tool'],
                              'raw_excerpt':raw[:500]},ensure_ascii=False),flush=True)
        (a.out/'SUMMARY.json').write_text(json.dumps({'results':records,'tools_sha256':hashlib.sha256(a.tools.read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
    finally:
        if worker.stdin:worker.stdin.close()
        try:await asyncio.wait_for(worker.wait(),timeout=10)
        except TimeoutError:worker.kill();await worker.wait()
        if worker.stderr:
            (a.out/'model.stderr').write_bytes(await worker.stderr.read())
if __name__=='__main__':asyncio.run(main())

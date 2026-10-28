"""Run the measured library, evaluator and at most one local model together."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

p=argparse.ArgumentParser()
p.add_argument('--group',required=True)
a=p.parse_args()
out=Path('/evidence');out.mkdir(parents=True,exist_ok=True)
server=None
started=time.monotonic()
try:
    if a.group!='baseline':
        flags=['/runtime/llama-server','-m','/llm/model.gguf','--host','127.0.0.1','--port','8099',
               '--alias','docatlas-light','--ctx-size','2048','--parallel','1','--threads','2',
               '--threads-batch','2','--batch-size','128','--ubatch-size','64',
               '--cache-ram','0','--no-context-shift']
        if a.group=='qwen-rerank':
            flags+=['--reranking','--pooling','rank']
        else:
            flags+=['--jinja','--chat-template-kwargs','{"enable_thinking":false}']
        log=(out/'server.log').open('w')
        server=subprocess.Popen(flags,stdout=log,stderr=subprocess.STDOUT)
        for _ in range(120):
            if server.poll() is not None:
                raise RuntimeError('model server exited before readiness')
            try:
                with urllib.request.urlopen('http://127.0.0.1:8099/health',timeout=1) as r:
                    if r.status==200:break
            except Exception:time.sleep(1)
        else:raise RuntimeError('model server readiness deadline')
    (out/'STARTUP.json').write_text(json.dumps({'group':a.group,'seconds':time.monotonic()-started,
                                              'server_pid':server.pid if server else None},indent=2))
    result=subprocess.run([sys.executable,'-I','/repo/eval/lightweight_evidence/run.py',
                           '--repo','/repo','--out','/evidence/run','--group',a.group])
    raise SystemExit(result.returncode)
finally:
    memory={}
    for name in ('memory.max','memory.swap.max','memory.current','memory.peak','memory.events'):
        path=Path('/sys/fs/cgroup')/name
        if path.exists():memory[name]=path.read_text().strip()
    if server is not None:
        path=Path('/proc')/str(server.pid)/'status'
        if path.exists():memory['server_proc_status']=path.read_text()
        server.terminate()
        try:server.wait(timeout=10)
        except subprocess.TimeoutExpired:server.kill();server.wait()
    (out/'MEMORY.json').write_text(json.dumps(memory,indent=2)+'\n')

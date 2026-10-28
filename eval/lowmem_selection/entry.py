"""One cgroup contains the model, MCP service, indexing and evaluation driver."""
import json,os,subprocess,sys,time,urllib.request
from pathlib import Path
out=Path('/evidence');out.mkdir(exist_ok=True)
def memory():
 root=Path('/sys/fs/cgroup')
 return {name:(root/name).read_text().strip() for name in
         ('memory.max','memory.peak','memory.swap.max','memory.events')}
def save(name,obj):
 (out/name).write_text(json.dumps(obj,indent=2)+'\n')
start=time.monotonic();server=None;log=None;rc=1
try:
 mem=memory();assert mem['memory.max']=='1500000000' and mem['memory.swap.max']=='0',mem
 save('CGROUP_START.json',mem)
 policy=os.environ['POLICY'];suite=os.environ['SUITE']
 if policy.startswith('facet-tiny-'):
  log=(out/'llama.log').open('w')
  # Anonymous weight buffers are charged to this cgroup. Do not borrow
  # prewarmed mmap pages charged to the host that downloaded the artifact.
  server=subprocess.Popen(['/runtime/llama-server','-m','/tiny/model.gguf','--no-mmap','--host','127.0.0.1',
   '--port','8099','--alias','docatlas-tiny','--ctx-size','2048','--parallel','1',
   '--threads','2','--threads-batch','2','--batch-size','64','--ubatch-size','64',
   '--jinja','--chat-template-kwargs','{"enable_thinking":false}','--no-context-shift'],stdout=log,stderr=log)
  ready=False
  for _ in range(120):
   if server.poll() is not None:raise RuntimeError('local model failed to load')
   try:
    with urllib.request.urlopen('http://127.0.0.1:8099/health',timeout=1) as response:
     ready=response.status==200
   except OSError:pass
   if ready:break
   time.sleep(1)
  if not ready:raise RuntimeError('model startup timeout')
 save('STARTUP.json',{'seconds':time.monotonic()-start,'model_started':server is not None,
                      'model_memory_mapping':False})
 rc=subprocess.run(['/opt/venv/bin/python','-I','-u','/repo/eval/lowmem_selection/run.py',
   '--repo','/repo','--work','/tmp/lowmem-work','--out','/evidence/run',
   '--policy',policy,'--suite',suite]).returncode
finally:
 if server is not None:
  if server.poll() is None:server.terminate()
  try:server.wait(timeout=10)
  except subprocess.TimeoutExpired:server.kill();server.wait()
 if log:log.close()
 mem=memory();save('CGROUP_FINAL.json',{**mem,'driver_exit':rc,'wall_seconds':time.monotonic()-start})
 events=dict(line.split() for line in mem['memory.events'].splitlines())
 if int(events.get('oom_kill','0')) or int(events.get('oom','0')):rc=137
 if int(mem['memory.peak'])>1_500_000_000:rc=137
sys.exit(rc)

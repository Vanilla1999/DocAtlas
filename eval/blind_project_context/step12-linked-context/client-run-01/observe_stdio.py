import json,signal,subprocess,sys,threading
from pathlib import Path
log=Path(sys.argv[1]); child=subprocess.Popen(sys.argv[2:],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=sys.stderr)
def incoming():
 try:
  for line in sys.stdin.buffer:
   try:
    value=json.loads(line)
    if value.get("method") in ("tools/call","resources/read"):
     with log.open("a") as f: f.write(json.dumps(value)+"\n")
   except (ValueError,AttributeError): pass
   child.stdin.write(line); child.stdin.flush()
 finally: child.stdin.close()
signal.signal(signal.SIGTERM,lambda *_: child.terminate())
threading.Thread(target=incoming,daemon=True).start()
try:
 for line in child.stdout: sys.stdout.buffer.write(line); sys.stdout.buffer.flush()
finally:
 child.terminate(); child.wait(timeout=5)

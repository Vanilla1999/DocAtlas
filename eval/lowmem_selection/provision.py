"""Explicit pre-runtime download of official checksum-pinned Qwen 0.6B."""
import hashlib,json,sys,urllib.request
from pathlib import Path
URL='https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/1eaf4d9657fe65ad10a51eab76a8db5b363bddaa/Qwen3-0.6B-Q8_0.gguf'
SHA='9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031'
p=Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True)
h=hashlib.sha256();size=0
try:
 with urllib.request.urlopen(URL,timeout=180) as response,p.open('xb') as output:
  if not response.geturl().startswith('https://'):raise ValueError('insecure redirect')
  while block:=response.read(4*1024*1024):
   size+=len(block)
   if size>1_000_000_000:raise ValueError('unexpected model size')
   h.update(block);output.write(block)
 if h.hexdigest()!=SHA:raise ValueError('model checksum mismatch')
except BaseException:
 p.unlink(missing_ok=True);raise
print(json.dumps({'model':'Qwen3-0.6B-Q8_0','url':URL,'sha256':SHA,'bytes':size,'verified':True}))

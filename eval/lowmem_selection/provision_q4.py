"""Explicit resource variant: third-party Q4 quant, immutable revision/hash."""
import hashlib,json,sys,urllib.request
from pathlib import Path
URL='https://huggingface.co/bartowski/Qwen_Qwen3-0.6B-GGUF/resolve/d8dd54f51753264b7b04f2e00cb64712dca05c44/Qwen_Qwen3-0.6B-Q4_K_M.gguf'
SHA='9acfc1e001311f34b4252001b626f2e466d592a42065f66571bff3790d4e1b14'
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
print(json.dumps({'model':'bartowski-Qwen3-0.6B-Q4_K_M','url':URL,'sha256':SHA,'bytes':size,'verified':True}))

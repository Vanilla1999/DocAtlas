"""Full-document, question-blind contextualization using official Q8 weights."""
import argparse,json,time,resource,hashlib
from pathlib import Path
from llama_cpp import Llama,__version__
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(exist_ok=False)
model_path=Path('/tmp/docatlas-context-gguf/qwen2.5-0.5b-instruct-q8_0.gguf')
model=Llama(model_path=str(model_path),n_ctx=16384,n_threads=3,n_threads_batch=3,n_batch=512,seed=0,verbose=False)
system='Write a concise retrieval context for an excerpt from a technical document. Use only the document supplied. Identify the library, the subject of the excerpt and its relationship to the surrounding document. Return one paragraph of 50 to 80 words. Do not answer a user question. Do not invent missing information.'
docs=json.loads((a.input/'documents.json').read_text());chunks=json.loads((a.input/'chunks.json').read_text());rows=[];started=time.perf_counter()
for doc in docs:
 prefix='<|im_start|>system\n'+system+'<|im_end|>\n<|im_start|>user\nLibrary: '+doc['library']+'\nDocument:\n'+doc['text']+'\nExcerpt:\n'
 for c in [c for c in chunks if c['document']==doc['key']]:
  prompt=prefix+c['text']+'\nReturn only the context paragraph.<|im_end|>\n<|im_start|>assistant\n';ids=model.tokenize(prompt.encode(),add_bos=False,special=True);assert len(ids)+128<16384
  t=time.perf_counter();result=model(ids,max_tokens=128,temperature=0.,repeat_penalty=1.,seed=0,stop=['<|im_end|>','<|endoftext|>']);elapsed=time.perf_counter()-t
  rows.append({'key':c['key'],'context':result['choices'][0]['text'],'generated_tokens':result['usage']['completion_tokens'],'capped':result['choices'][0]['finish_reason']=='length','seconds':elapsed,'prompt_tokens':len(ids)})
  (a.output/'contexts.json').write_text(json.dumps(rows,ensure_ascii=False)+'\n');print(len(rows),'/',len(chunks),'seconds',round(elapsed,2),flush=True)
(a.output/'environment.json').write_text(json.dumps({'model':'Qwen/Qwen2.5-0.5B-Instruct-GGUF','revision':Path('/tmp/docatlas-context-gguf/revision.txt').read_text(),'file_sha256':hashlib.sha256(model_path.read_bytes()).hexdigest(),'runtime':'llama-cpp-python','runtime_version':__version__,'quantization':'Q8_0','system':system,'max_new_tokens':128,'temperature':0.,'repeat_penalty':1.,'threads':3,'question_access':False,'total_seconds':time.perf_counter()-started,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},indent=2)+'\n')

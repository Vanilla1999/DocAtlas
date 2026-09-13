"""Same multilingual encoder: isolated, late-pooled, or contextualized chunks."""
import argparse,json,os,sys,time,resource
from pathlib import Path
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--contexts',type=Path);p.add_argument('--base',type=Path);p.add_argument('--stream-contexts',action='store_true');a=p.parse_args();a.output.mkdir(exist_ok=False)
import torch,numpy as np
from transformers import AutoTokenizer
sys.path.insert(0,'/tmp')
from docatlas_jina_impl.configuration_xlm_roberta import XLMRobertaFlashConfig
from docatlas_jina_impl.modeling_lora import XLMRobertaLoRA,LoRAParametrization
from docatlas_jina_impl.mha import SelfAttention
torch.set_num_threads(2);torch.manual_seed(0)
# Algebraically equivalent CPU SDPA avoids materializing an 8192^2 attention matrix.
old=SelfAttention.forward
def sdpa(self,qkv,causal=None,key_padding_mask=None):
 q,k,v=[t.transpose(1,2) for t in qkv.unbind(dim=2)];causal=self.causal if causal is None else causal
 assert not causal
 mask=None if key_padding_mask is None else torch.where(key_padding_mask[:,None,None,:],0.,-10000.).to(q.dtype)
 return torch.nn.functional.scaled_dot_product_attention(q,k,v,attn_mask=mask,dropout_p=0.,scale=self.softmax_scale).transpose(1,2)
probe=SelfAttention().eval();qkv=torch.randn(2,17,3,4,8);mask=torch.ones(2,17,dtype=torch.bool);mask[1,-3:]=False
error=float((old(probe,qkv,key_padding_mask=mask)-sdpa(probe,qkv,key_padding_mask=mask)).abs().max());assert error<1e-5;SelfAttention.forward=sdpa
config=XLMRobertaFlashConfig.from_pretrained('/tmp/docatlas-jina-v3');config.use_flash_attn=False;config._name_or_path='/tmp/docatlas-jina-v3'
model=XLMRobertaLoRA.from_pretrained('/tmp/docatlas-jina-v3',config=config,local_files_only=True,torch_dtype=torch.float32).eval();tok=AutoTokenizer.from_pretrained('/tmp/docatlas-jina-v3',local_files_only=True)
docs=json.loads((a.input/'documents.json').read_text());chunks=json.loads((a.input/'chunks.json').read_text());questions=json.loads((a.input/'questions.json').read_text());started=time.perf_counter();timings={};windows=[]
lora_original=LoRAParametrization.lora_forward
def cached_lora(self,X,current_task):
 assert not self.training
 key=int(current_task)
 if getattr(self,'_fixed_task',None)!=key:
  self._fixed_weight=lora_original(self,X,current_task);self._fixed_task=key
 return self._fixed_weight
lora_checked=False;lora_error=None
def hidden(text,task):
 global lora_checked,lora_error
 instruction=model._task_instructions[task]
 enc=tok(instruction+text,return_tensors='pt',return_offsets_mapping=True,truncation=False);offsets=[[max(0,s-len(instruction)),max(0,e-len(instruction))] for s,e in enc.pop('offset_mapping')[0].tolist()];assert enc['input_ids'].shape[1]<=8192,('too_long',enc['input_ids'].shape)
 adapter=torch.full((1,),model._adaptation_map[task],dtype=torch.int32)
 with torch.inference_mode():
  if not lora_checked:
   reference=model(**enc,adapter_mask=adapter).last_hidden_state
   LoRAParametrization.lora_forward=cached_lora
   actual=model(**enc,adapter_mask=adapter).last_hidden_state
   lora_error=float((reference-actual).abs().max());assert lora_error<1e-6;lora_checked=True
  h=model(**enc,adapter_mask=adapter).last_hidden_state[0]
 return h,offsets

def vector(h,indices):
 v=h[indices].float().mean(0);return torch.nn.functional.normalize(v,dim=0).cpu().numpy()
arrays={}
if a.contexts:
 contexts={};wait_seconds=0.;base=np.load(a.base);arrays['queries']=base['queries'];v=[];t=time.perf_counter()
 for i,c in enumerate(chunks):
  waiting=time.perf_counter()
  while c['key'] not in contexts:
   try:contexts={r['key']:r['context'] for r in json.loads(a.contexts.read_text())}
   except (FileNotFoundError,json.JSONDecodeError):
    if not a.stream_contexts:raise
   if c['key'] not in contexts:
    if not a.stream_contexts:raise ValueError('missing context: '+c['key'])
    time.sleep(1)
  wait_seconds+=time.perf_counter()-waiting
  h,offs=hidden(contexts[c['key']]+'\n\n'+c['text'],'retrieval.passage');v.append(vector(h,[j for j,(s,e) in enumerate(offs) if e>s]));print('context',i+1,'/',len(chunks),flush=True)
 arrays['context']=np.stack(v);timings['context_index_seconds']=time.perf_counter()-t-wait_seconds;timings['context_wait_seconds']=wait_seconds
else:
 v=[];t=time.perf_counter()
 for i,q in enumerate(questions):
  h,offs=hidden(q['question'],'retrieval.query');v.append(vector(h,list(range(len(offs)))));print('query',i+1,flush=True)
 arrays['queries']=np.stack(v);timings['queries_seconds']=time.perf_counter()-t
 v=[];t=time.perf_counter()
 for i,c in enumerate(chunks):
  h,offs=hidden(c['text'],'retrieval.passage');v.append(vector(h,[j for j,(s,e) in enumerate(offs) if e>s]));print('plain',i+1,'/',len(chunks),flush=True)
 arrays['plain']=np.stack(v);timings['plain_index_seconds']=time.perf_counter()-t
 vectors={};t=time.perf_counter()
 for doc in docs:
  h,offs=hidden(doc['text'],'retrieval.passage');windows.append({'document':doc['key'],'tokens':len(offs),'windows':1})
  for c in [c for c in chunks if c['document']==doc['key']]:
   idx=[j for j,(s,e) in enumerate(offs) if e>s and s<c['char_end'] and e>c['char_start']];assert idx;vectors[c['key']]=vector(h,idx)
  print('late',doc['library'],doc['path'],len(offs),flush=True)
 arrays['late']=np.stack([vectors[c['key']] for c in chunks]);timings['late_index_seconds']=time.perf_counter()-t
np.savez_compressed(a.output/'vectors.npz',**arrays)
rows=[]
for i,q in enumerate(questions):
 indices=[j for j,c in enumerate(chunks) if c['library']==q['library']];lanes={}
 for name,vectors in arrays.items():
  if name=='queries':continue
  scores=vectors[indices]@arrays['queries'][i];order=np.argsort(-scores,kind='stable');lanes[name]=[{'key':chunks[indices[j]]['key'],'score':float(scores[j])} for j in order]
 rows.append({'key':q['key'],'lanes':lanes})
(a.output/'rankings.json').write_text(json.dumps(rows)+'\n');(a.output/'environment.json').write_text(json.dumps({'model':'jinaai/jina-embeddings-v3','revision':'ab036b023d30b4d1138c4c3bfa9f0c445ab455d6','code_revision':'bd55a5ec8e6c0fb1d6c26efb4b6a4a74ce8a88d3','dtype':'float32','threads':2,'passage_pooling':'mean source/context tokens; exclude instruction and special tokens','query_pooling':'mean all tokens','task_instructions':model._task_instructions,'lora_cache_equivalence_max_error':lora_error,'sdpa_equivalence_max_error':error,'windows':windows,'timings':timings,'total_seconds':time.perf_counter()-started,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},indent=2)+'\n')

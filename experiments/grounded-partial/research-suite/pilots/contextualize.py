"""Question-blind preprocessing; bounded batches and reuse immutable document KV prefixes."""
import argparse,json,time,os,resource
from pathlib import Path
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(exist_ok=True)
import torch
from transformers import AutoTokenizer,AutoModelForCausalLM
from transformers.cache_utils import DynamicCache
torch.set_num_threads(3);torch.manual_seed(0)
tok=AutoTokenizer.from_pretrained('/tmp/docatlas-context-small',local_files_only=True,padding_side='left')
model=AutoModelForCausalLM.from_pretrained('/tmp/docatlas-context-small',local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').eval()
docs=json.loads((a.input/'documents.json').read_text());chunks=json.loads((a.input/'chunks.json').read_text());rows=json.loads((a.output/'contexts.json').read_text()) if (a.output/'contexts.json').exists() else [];done={r['key'] for r in rows};resumed_count=len(rows);started=time.perf_counter()
system='Write a concise retrieval context for an excerpt from a technical document. Use only the document supplied. Identify the library, the subject of the excerpt and its relationship to the surrounding document. Return one paragraph of 50 to 80 words. Do not answer a user question. Do not invent missing information.'
stop=set(model.generation_config.eos_token_id if isinstance(model.generation_config.eos_token_id,list) else [model.generation_config.eos_token_id])
with torch.inference_mode():
 for doc in docs:
  children=[c for c in chunks if c['document']==doc['key'] and c['key'] not in done]
  if not children:continue
  prefix='<|im_start|>system\n'+system+'<|im_end|>\n<|im_start|>user\nLibrary: '+doc['library']+'\nDocument:\n'+doc['text']+'\nExcerpt:\n'
  prefix_ids=tok(prefix,return_tensors='pt',add_special_tokens=False)['input_ids'];base=model(prefix_ids,use_cache=True,logits_to_keep=1).past_key_values.to_legacy_cache();plen=prefix_ids.shape[1]
  for at in range(0,len(children),1):
   batch=children[at:at+1];bs=len(batch);before=time.perf_counter()
   tails=[c['text']+'\nReturn only the context paragraph.<|im_end|>\n<|im_start|>assistant\n' for c in batch]
   encoded=tok(tails,padding=True,return_tensors='pt',add_special_tokens=False)
   cache=DynamicCache.from_legacy_cache(tuple(tuple(x.repeat(bs,1,1,1) for x in layer) for layer in base))
   mask=torch.cat([torch.ones(bs,plen,dtype=torch.long),encoded['attention_mask']],dim=1)
   pos=(mask.cumsum(-1)-1).clamp(min=0)[:,-encoded['input_ids'].shape[1]:]
   out=model(encoded['input_ids'],attention_mask=mask,position_ids=pos,past_key_values=cache,use_cache=True,logits_to_keep=1)
   generated=[[] for _ in batch];finished=[False]*bs
   for step in range(128):
    tokens=out.logits[:,-1].argmax(-1)
    for i,t in enumerate(tokens.tolist()):
     if not finished[i]:
      if t in stop:finished[i]=True
      else:generated[i].append(t)
    if all(finished):break
    mask=torch.cat([mask,torch.ones(bs,1,dtype=torch.long)],dim=1);pos=(mask.sum(-1)-1).unsqueeze(-1)
    out=model(tokens[:,None],attention_mask=mask,position_ids=pos,past_key_values=out.past_key_values,use_cache=True,logits_to_keep=1)
   elapsed=time.perf_counter()-before
   for c,g in zip(batch,generated):rows.append({'key':c['key'],'context':tok.decode(g,skip_special_tokens=True),'generated_tokens':len(g),'capped':len(g)==128,'batch_size':bs,'batch_seconds':elapsed,'document_tokens':plen})
   (a.output/'contexts.json').write_text(json.dumps(rows,ensure_ascii=False)+'\n');print(len(rows),'/',len(chunks),'batch_seconds',round(elapsed,2),flush=True)
   del out,cache
(a.output/'environment.json').write_text(json.dumps({'model':'Qwen/Qwen2.5-0.5B-Instruct','revision':'7ae557604adf67be50417f59c2c2f167def9a775','system':system,'max_new_tokens':128,'dtype':'bfloat16','threads':3,'batch':1,'resumed_rows':resumed_count,'question_access':False,'total_seconds':time.perf_counter()-started,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},indent=2)+'\n')

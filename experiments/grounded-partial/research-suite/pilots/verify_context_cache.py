"""Check cached, left-padded batch logits against ordinary full prompts."""
import os,json
from pathlib import Path
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from transformers.cache_utils import DynamicCache
torch.set_num_threads(1)
tok=AutoTokenizer.from_pretrained('/tmp/docatlas-context-small',local_files_only=True,padding_side='left')
m=AutoModelForCausalLM.from_pretrained('/tmp/docatlas-context-small',local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').eval()
prefix='<|im_start|>system\nSummarize the excerpt using the document.<|im_end|>\n<|im_start|>user\nDocument: The HTTPX library uses environment variables by default. Set trust_env=False to ignore them.\nExcerpt:\n'
tails=['Set trust_env=False to ignore them.','The HTTPX library uses environment variables by default.']
tails=[t+'\nReturn only context.<|im_end|>\n<|im_start|>assistant\n' for t in tails]
with torch.inference_mode():
 ids=tok(prefix,return_tensors='pt',add_special_tokens=False)['input_ids'];base=m(ids,use_cache=True,logits_to_keep=1).past_key_values.to_legacy_cache();plen=ids.shape[1]
 e=tok(tails,padding=True,return_tensors='pt',add_special_tokens=False);mask=torch.cat([torch.ones(2,plen,dtype=torch.long),e['attention_mask']],dim=1);pos=(mask.cumsum(-1)-1).clamp(min=0)[:,-e['input_ids'].shape[1]:]
 cache=DynamicCache.from_legacy_cache(tuple(tuple(x.repeat(2,1,1,1) for x in layer) for layer in base));cached=m(e['input_ids'],attention_mask=mask,position_ids=pos,past_key_values=cache,logits_to_keep=1).logits[:,-1].float()
 rows=[]
 for i,t in enumerate(tails):
  full=tok(prefix+t,return_tensors='pt',add_special_tokens=False);ordinary=m(**full,logits_to_keep=1).logits[0,-1].float();a=int(cached[i].argmax());b=int(ordinary.argmax());rows.append({'same_top_token':a==b,'max_logit_difference':float((cached[i]-ordinary).abs().max()),'cached_top':a,'ordinary_top':b});assert a==b
print(json.dumps({'dtype':'bfloat16','left_padding':True,'rows':rows}))

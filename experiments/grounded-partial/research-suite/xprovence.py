"""Execute upstream XProvence; preserve original sentence coordinates for evidence."""
import argparse,json,os,time,sys,resource
from pathlib import Path
from unittest.mock import patch
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(exist_ok=False)
import torch
torch.set_num_threads(2);torch.manual_seed(0)
sys.path.insert(0,'/tmp/docatlas-xprovence')
import modeling_xprovence_hf as upstream
config=upstream.XProvenceConfig(**json.loads(Path('/tmp/docatlas-xprovence/config.json').read_text()))
config._name_or_path='/tmp/docatlas-xprovence'
model=upstream.XProvence.from_pretrained('/tmp/docatlas-xprovence',config=config,local_files_only=True,torch_dtype=torch.float32).eval()
module=sys.modules[model.__class__.__module__];rounding=module.sentence_rounding
rows=[];started=time.perf_counter()
for row in [json.loads(line) for line in a.input.read_text().splitlines()]:
 masks=[]
 def capture(predictions,chunks,**kwargs):
  selected=rounding(predictions,chunks,**kwargs);masks.append([bool(selected[start:end].all()) for start,end in chunks]);return selected
 texts=[c['text'] for c in row['candidates']];before=time.perf_counter()
 with patch.object(module,'sentence_rounding',capture):
  result=model.process([row['question']],[texts],title=None,threshold=0.3,always_select_title=False,reorder=False,batch_size=4)
 assert len(masks)==len(texts),'unexpected multi-window input; add explicit window mapping'
 candidates=[]
 for c,mask,decoded,score in zip(row['candidates'],masks,result['pruned_context'][0],result['reranking_score'][0]):
  sents=[s for s in module.nlp(c['text']).sents if model.tokenizer.encode(s.text.strip(),add_special_tokens=False)]
  assert len(sents)==len(mask)
  spans=[]
  for s,keep in zip(sents,mask):
   if keep:
    left=s.start_char+len(s.text)-len(s.text.lstrip());right=s.end_char-(len(s.text)-len(s.text.rstrip()))
    spans.append({'start':left,'end':right,'text':c['text'][left:right]})
  candidates.append({'key':c['key'],'score':float(score),'spans':spans,'upstream_decoded':decoded,'input_chars':len(c['text']),'retained_chars':sum(s['end']-s['start'] for s in spans)})
 rows.append({'key':row['key'],'candidates':candidates,'seconds':time.perf_counter()-before});(a.output/'rows.json').write_text(json.dumps(rows,ensure_ascii=False)+'\n');print(len(rows),'/80',flush=True)
(a.output/'environment.json').write_text(json.dumps({'model':'naver/xprovence-reranker-bgem3-v2','revision':'f2798d357213c40164bdd79557d6d2e43ca7d8d2','threshold':0.3,'title':None,'always_select_title':False,'total_seconds':time.perf_counter()-started,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},indent=2)+'\n')

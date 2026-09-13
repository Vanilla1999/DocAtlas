"""Gold-blind local scoring: this process has no evaluation imports or case IDs."""
import argparse, hashlib, json, os, time, resource
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--model',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert not a.output.exists();a.output.mkdir(parents=True)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.manual_seed(0);torch.use_deterministic_algorithms(True)
    started=time.perf_counter();tokenizer=AutoTokenizer.from_pretrained(a.model,local_files_only=True)
    model=AutoModelForSequenceClassification.from_pretrained(a.model,local_files_only=True,torch_dtype=torch.float32).eval()
    load_seconds=time.perf_counter()-started; outputs=[]; total_pairs=0;total_tokens=0
    inputs=[json.loads(line) for line in a.input.read_text().splitlines()]
    for row in inputs:
        assert set(row)=={'key','question','candidates'}
        for c in row['candidates']: assert set(c)=={'key','header','text'}
        query_start=time.perf_counter();candidates=[]
        for offset in range(0,len(row['candidates']),4):
            batch=row['candidates'][offset:offset+4]
            passages=[c['header']+'\n'+c['text'] for c in batch]
            enc=tokenizer([row['question']]*len(batch),passages,padding=True,truncation='only_second',max_length=1024,return_offsets_mapping=True,return_tensors='pt')
            offsets=enc.pop('offset_mapping');seqs=[enc.sequence_ids(i) for i in range(len(batch))]
            with torch.inference_mode(): scores=model(**enc).logits.view(-1).tolist()
            for i,(c,score) in enumerate(zip(batch,scores)):
                end=max((int(off[1]) for off,seq in zip(offsets[i],seqs[i]) if seq==1),default=0)
                seen_body=c['text'][:max(0,end-len(c['header'])-1)]
                tokens=int(enc['attention_mask'][i].sum());total_tokens+=tokens;total_pairs+=1
                candidates.append({'key':c['key'],'score':score,'seen_text':seen_body,'truncated':bool(c['text'][len(seen_body):].strip()),'pair_tokens':tokens})
            print(row['key'][:10],offset+len(batch),'/',len(row['candidates']),flush=True)
        outputs.append({'key':row['key'],'candidates':candidates,'seconds':time.perf_counter()-query_start})
        (a.output/'scores.json').write_text(json.dumps(outputs,ensure_ascii=False)+'\n')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in a.model.iterdir() if p.is_file()}
    env={'model':'BAAI/bge-reranker-v2-m3','revision':'953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e','model_sha256':hashes,'input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'torch':torch.__version__,'device':'cpu','dtype':'float32','threads':4,'batch_size':4,'max_length':1024,'seed':0,'load_seconds':load_seconds,'first_query_seconds':outputs[0]['seconds'],'total_seconds':time.perf_counter()-started,'pairs':total_pairs,'input_tokens':total_tokens,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'generator_tested':False}
    (a.output/'environment.json').write_text(json.dumps(env,indent=2)+'\n')
if __name__=='__main__':main()

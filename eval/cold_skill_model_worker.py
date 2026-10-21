"""Separate pinned public offline Qwen worker, no project/gold access."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

MODEL = 'Qwen/Qwen2.5-1.5B-Instruct'
REV = '989aa7980e4cf806f80c7fef2b1adb7bc71aa306'

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(4*1024*1024), b''):
            h.update(part)
    return h.hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--identity', required=True, type=Path)
    args = parser.parse_args()
    import torch
    import transformers
    from huggingface_hub import snapshot_download
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    path = Path(snapshot_download(MODEL,revision=REV,token=False,
                                  allow_patterns=['*.json','*.safetensors','merges.txt','vocab.json']))
    tok = AutoTokenizer.from_pretrained(path,trust_remote_code=False,local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(path, trust_remote_code=False,
              local_files_only=True, torch_dtype=torch.float32, attn_implementation='eager').eval()
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    ident = {'model':MODEL,'revision':REV,'torch':torch.__version__,
             'transformers':transformers.__version__, 'quantization':None,
             'cpu_threads':2,'seed':0,'do_sample':False,
             'assets':{p.name:{'sha256':digest(p),'bytes':p.stat().st_size}
                       for p in sorted(path.iterdir()) if p.is_file()}}
    args.identity.parent.mkdir(parents=True,exist_ok=True)
    args.identity.write_text(json.dumps(ident,indent=2)+'\n')
    print(json.dumps({'ready':True,'model':MODEL,'revision':REV}),flush=True)
    for line in sys.stdin:
        payload=None
        try:
            payload=json.loads(line)
            assert set(payload)=={'id','messages','tools','max_new_tokens'}
            messages=payload['messages']
            tools=payload['tools']
            budget=payload['max_new_tokens']
            assert budget in (192,256,320)
            tokens=tok.apply_chat_template(messages,tools=tools,
                                           tokenize=True,return_tensors='pt',
                                           add_generation_prompt=True)
            inp=int(tokens.shape[-1])
            if inp>15500:
                raise ValueError(f'LLM input budget exceeded ({inp}), no truncation')
            start=time.perf_counter()
            with torch.inference_mode():
                out=model.generate(tokens,do_sample=False,max_new_tokens=budget,
                                   pad_token_id=tok.eos_token_id)
            generated=out[0,inp:]
            raw=tok.decode(generated,skip_special_tokens=False)
            friendly=tok.decode(generated,skip_special_tokens=True)
            ret={'id':payload['id'],'text':friendly,'raw':raw,'input_tokens':inp,
                 'output_tokens':len(generated),
                 'hit_limit':len(generated)==budget and int(generated[-1])!=tok.eos_token_id,
                 'elapsed_s':round(time.perf_counter()-start,2)}
        except Exception as exc:
            ret={'id':payload.get('id') if isinstance(payload,dict) else None,
                 'error':type(exc).__name__,'message':str(exc)}
        print(json.dumps(ret,ensure_ascii=False),flush=True)

if __name__=='__main__':
    main()

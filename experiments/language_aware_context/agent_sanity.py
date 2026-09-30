"""Disjoint model health control; no pilot tasks, facts or retrieval results read."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import time


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    import torch
    import transformers
    from transformers import AutoModelForCausalLM,AutoTokenizer
    from huggingface_hub import snapshot_download
    from experiments.language_aware_context.pilot_io import (
        ANSWER_SYSTEM, PLANNER_SYSTEM, answering_messages, planning_messages, parse_plan,
    )
    args.output.mkdir(parents=True,exist_ok=False)
    revision='989aa7980e4cf806f80c7fef2b1adb7bc71aa306'
    local=snapshot_download('Qwen/Qwen2.5-1.5B-Instruct',revision=revision,token=False,
        allow_patterns=['*.json','*.safetensors','merges.txt','vocab.json'])
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    torch.manual_seed(0);torch.use_deterministic_algorithms(True)
    tok=AutoTokenizer.from_pretrained(local,local_files_only=True,trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(local,local_files_only=True,
        trust_remote_code=False,torch_dtype=torch.float32,attn_implementation='eager').eval()
    plan,literals=planning_messages('When should I call `open()` if the file is missing?',None)
    cases=[('echo',[{'role':'user','content':'Reply with exactly the single word READY.'}]),
           ('evidence',answering_messages('What colour is the kettle?',[
               {'id':'S1','text':'The kettle is green.'}])),('planner',plan)]
    results=[]
    for mode in ('fp32','dynamic_int8'):
        if mode=='dynamic_int8':
            model=torch.ao.quantization.quantize_dynamic(model,{torch.nn.Linear},dtype=torch.qint8)
        for name,messages in cases:
            inputs=tok.apply_chat_template(messages,add_generation_prompt=True,
                tokenize=True,return_dict=True,return_tensors='pt')
            before=inputs['input_ids'].shape[-1]
            start=time.perf_counter()
            with torch.inference_mode():
                generated=model.generate(**inputs,do_sample=False,max_new_tokens=96,
                    pad_token_id=tok.eos_token_id)
            text=tok.decode(generated[0,before:],skip_special_tokens=True)
            if name=='echo':ok=text.strip()=='READY'
            elif name=='evidence':ok=bool(re.search(r'\bgreen\b',text,re.I)) and '[S1]' in text
            else:
                try:ok=bool(parse_plan(text,literals,'When should I call `open()` if the file is missing?'))
                except (ValueError,TypeError,KeyError,IndexError):ok=False
            results.append({'mode':mode,'case':name,'passed':ok,'text':text,
                'input_ids_sha256':hashlib.sha256(inputs['input_ids'].numpy().tobytes()).hexdigest(),
                'input_tokens':before,'output_tokens':generated.shape[-1]-before,
                'seconds':time.perf_counter()-start})
            print(json.dumps(results[-1]),flush=True)
    report={'revision':revision,'torch':torch.__version__,'transformers':transformers.__version__,
        'quantized_engine':torch.backends.quantized.engine,'cases':results,
        'pilot_inputs_read':False,'use_as_retrieval_quality_result':False}
    (args.output/'health.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0


if __name__=='__main__':raise SystemExit(main())

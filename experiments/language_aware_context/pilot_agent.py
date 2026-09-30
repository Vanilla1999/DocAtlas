"""Genuine isolated CPU language-model worker. JSONL input/output; no task/gold access.

Run in a separate explicitly versioned environment. Never imported by production.
Download public pinned model without tokens, then inference uses local files only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--identity', type=Path, required=True)
    args = parser.parse_args()
    import torch
    import transformers
    from huggingface_hub import snapshot_download
    from transformers import AutoModelForCausalLM, AutoTokenizer
    revision = '989aa7980e4cf806f80c7fef2b1adb7bc71aa306'
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    local = snapshot_download('Qwen/Qwen2.5-1.5B-Instruct', revision=revision, token=False,
        allow_patterns=['*.json', '*.safetensors', 'merges.txt', 'vocab.json'])
    files = {}
    for path in sorted(Path(local).glob('*')):
        if path.is_file():
            h = hashlib.sha256()
            with path.open('rb') as f:
                for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
                    h.update(chunk)
            files[path.name] = {'sha256': h.hexdigest(), 'size': path.stat().st_size}
    tokenizer = AutoTokenizer.from_pretrained(local, local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(local, local_files_only=True,
        trust_remote_code=False, torch_dtype=torch.float32, attn_implementation='eager').eval()
    model = torch.ao.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)
    identity = {'model': 'Qwen/Qwen2.5-1.5B-Instruct', 'revision': revision,
        'torch': torch.__version__, 'transformers': transformers.__version__,
        'files': files, 'device': 'cpu', 'threads': 2, 'seed': 0, 'do_sample': False,
        'quantization': 'torch dynamic Linear qint8', 'dtype_before_quantization': 'float32'}
    args.identity.parent.mkdir(parents=True, exist_ok=True)
    args.identity.write_text(json.dumps(identity, indent=2) + '\n')
    print(json.dumps({'ready': True, 'identity': identity}), flush=True)
    for line in sys.stdin:
        obj = None
        try:
            obj = json.loads(line)
            if set(obj) != {'id', 'messages', 'max_new_tokens'}:
                raise ValueError('invalid worker fields')
            maximum = obj['max_new_tokens']
            if maximum not in (96, 144):
                raise ValueError('unexpected generation budget')
            inputs = tokenizer.apply_chat_template(obj['messages'], add_generation_prompt=True,
                tokenize=True, return_dict=True, return_tensors='pt')
            n = inputs['input_ids'].shape[-1]
            if n > 6000:
                raise ValueError('input budget exceeded; no silent truncation')
            started = time.perf_counter()
            with torch.inference_mode():
                result = model.generate(**inputs, do_sample=False, max_new_tokens=maximum,
                    pad_token_id=tokenizer.eos_token_id)
            output = result[0, n:]
            print(json.dumps({'id': obj['id'], 'text': tokenizer.decode(output, skip_special_tokens=True),
                'input_tokens': n, 'output_tokens': len(output),
                'hit_length_limit': len(output) == maximum and int(output[-1]) != tokenizer.eos_token_id,
                'seconds': time.perf_counter() - started}, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps({'id': obj.get('id') if isinstance(obj, dict) else None,
                'error': type(exc).__name__, 'message': str(exc)}), flush=True)
            return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

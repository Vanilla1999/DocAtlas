"""Two published official-card pairs only; not the evidence recipe or gate."""
import argparse
import hashlib
import json
from pathlib import Path
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--assets", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    provenance = json.loads((Path(__file__).parent / "assets-provenance.json").read_text())
    for name, details in provenance["files"].items():
        with (args.assets / name).open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == details["sha256"], name
    import torch
    import transformers
    from transformers import AutoTokenizer, AutoModelForCausalLM
    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(args.assets, local_files_only=True, trust_remote_code=False, padding_side="left")
    model = AutoModelForCausalLM.from_pretrained(args.assets, local_files_only=True, trust_remote_code=False,
                dtype=torch.bfloat16, attn_implementation="sdpa").to("cuda:0").eval()
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - started
    torch.cuda.reset_peak_memory_stats()
    prefix = '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
    suffix = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
    instruction = 'Given a web search query, retrieve relevant passages that answer the query'
    queries = ['What is the capital of China?', 'Explain gravity']
    documents = ['The capital of China is Beijing.',
                 'Gravity is a force that attracts two bodies towards each other. It gives weight to physical objects and is responsible for the movement of planets around the sun.']
    assert tokenizer.encode('no', add_special_tokens=False) == [2152]
    assert tokenizer.encode('yes', add_special_tokens=False) == [9693]
    records = []
    for query, document in zip(queries, documents, strict=True):
        body = f'<Instruct>: {instruction}\n<Query>: {query}\n<Document>: {document}'
        ids = (tokenizer.encode(prefix, add_special_tokens=False, truncation=False)
               + tokenizer.encode(body, add_special_tokens=True, truncation=False)
               + tokenizer.encode(suffix, add_special_tokens=False, truncation=False))
        tensor = torch.tensor([ids], device='cuda:0')
        tick = time.perf_counter()
        with torch.inference_mode():
            logits = model(input_ids=tensor, attention_mask=torch.ones_like(tensor),
                           use_cache=False, logits_to_keep=1).logits[0, -1, [2152, 9693]].float()
            probability = torch.softmax(logits, dim=0)[1]
            assert torch.isfinite(logits).all().item() and torch.isfinite(probability).item()
        torch.cuda.synchronize()
        records.append({'query': query, 'document': document, 'input_tokens': len(ids),
                        'input_ids_sha256': hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest(),
                        'logits_no_yes': logits.tolist(), 'p_yes': probability.item(),
                        'forward_seconds': time.perf_counter() - tick})
    receipt = {'status': 'PASS', 'boundary': 'official pinned model-card 2pairs, not evidence recipe/gate/public DocAtlas',
               'model_revision': provenance['revision'], 'assets_hashes_verified': True,
               'torch': torch.__version__, 'transformers': transformers.__version__, 'cuda': torch.version.cuda,
               'gpu': torch.cuda.get_device_name(), 'dtype': 'bfloat16', 'attention': 'sdpa',
               'pairs': 2, 'model_forwards': 2, 'score_cache_hits': 0, 'batch_size': 1,
               'model_input_tokens': sum(r['input_tokens'] for r in records), 'model_loads': 1,
               'load_seconds': load_seconds, 'forward_seconds': sum(r['forward_seconds'] for r in records),
               'total_seconds_after_asset_checks': time.perf_counter() - started,
               'peak_vram_allocated_bytes': torch.cuda.max_memory_allocated(),
               'peak_vram_reserved_bytes': torch.cuda.max_memory_reserved(), 'records': records,
               'gate_calls': 0, 'terra_calls': 0, 'context_32k_verified': False}
    (args.out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()

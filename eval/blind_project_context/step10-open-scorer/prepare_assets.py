"""Explicit official pinned Qwen preparation, no model inference or gate reads."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import urllib.request

MODEL = "Qwen/Qwen3-Reranker-0.6B"
REVISION = "e61197ed45024b0ed8a2d74b80b4d909f1255473"
FILES = ("README.md", "config.json", "generation_config.json", "tokenizer.json",
         "tokenizer_config.json", "merges.txt", "vocab.json", "chat_template.jinja", "model.safetensors")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    with urllib.request.urlopen(f"https://huggingface.co/api/models/{MODEL}/tree/{REVISION}", timeout=60) as response:
        tree = json.load(response)
    entries = {item["path"]: item for item in tree}
    manifest = {"model": MODEL, "revision": REVISION, "official_origin": "https://huggingface.co/" + MODEL,
                "gate_inference_calls": 0, "model_inference_calls": 0, "files": {}}
    for name in FILES:
        entry = entries[name]
        sha256 = hashlib.sha256()
        git_blob = hashlib.sha1(f"blob {entry['size']}\0".encode())
        url = f"https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}"
        temporary = args.out / (name + ".partial")
        size = 0
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open("xb") as stream:
            while block := response.read(1024 * 1024):
                stream.write(block)
                size += len(block)
                sha256.update(block)
                git_blob.update(block)
        assert size == entry["size"], name
        if "lfs" in entry:
            assert sha256.hexdigest() == entry["lfs"]["oid"], name
        else:
            assert git_blob.hexdigest() == entry["oid"], name
        temporary.rename(args.out / name)
        manifest["files"][name] = {"sha256": sha256.hexdigest(), "bytes": size, "url": url,
                                  "remote_lfs_sha256": entry.get("lfs", {}).get("oid"),
                                  "remote_git_blob_sha1": entry["oid"]}
        print("verified", name, size, flush=True)
    import torch
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.out, local_files_only=True, trust_remote_code=False)
    label_ids = {label: tokenizer.encode(label, add_special_tokens=False) for label in ("yes", "no")}
    assert all(len(ids) == 1 for ids in label_ids.values())
    assert torch.cuda.is_available()
    matrix = torch.ones((16, 16), device="cuda", dtype=torch.bfloat16)
    assert torch.all(matrix @ matrix == 16).item()
    torch.cuda.synchronize()
    manifest["runtime"] = {"packages": {dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()},
                           "torch": torch.__version__, "cuda": torch.version.cuda,
                           "gpu": torch.cuda.get_device_name(), "capability": torch.cuda.get_device_capability(),
                           "compiled_arches": torch.cuda.get_arch_list(), "bf16_matmul": "PASS",
                           "label_ids": label_ids, "tokenizer_model_max_length": tokenizer.model_max_length}
    (args.out / "provenance.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "prepared", "model": MODEL, "revision": REVISION,
                      "label_ids": label_ids, "model_inference_calls": 0}, indent=2))


if __name__ == "__main__":
    main()

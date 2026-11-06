"""Read-only local/cache and authenticated metadata checks; never emits secrets."""
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import urllib.request
import urllib.error

from huggingface_hub import get_token, constants

BASE = "google/gemma-2b-it"
REVISION = "96988410cbdaeb8d5093d1ebdc5a8fb563e02bad"
ADAPTER = "doubleyyh/exit-gemma-2b"
ADAPTER_REVISION = "e286ce9096178a4aefb743d0919705250fdf1b23"


def main():
    token = get_token()
    headers = {"Authorization": "Bearer " + token} if token else {}
    request = urllib.request.Request(
        f"https://huggingface.co/{BASE}/resolve/{REVISION}/config.json", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            config = json.load(response)
            access = {"status": response.status, "accessible": True,
                      "max_position_embeddings": config.get("max_position_embeddings")}
    except urllib.error.HTTPError as exc:
        access = {"status": exc.code, "accessible": False}
    except Exception as exc:
        access = {"accessible": None, "error_type": type(exc).__name__}
    roots = {Path(constants.HF_HUB_CACHE), Path.home() / ".cache/huggingface/hub"}
    roots.update(Path("/tmp/opencode").glob("**/models--google--gemma-2b-it"))
    roots.update(Path("/tmp/opencode").glob("**/models--doubleyyh--exit-gemma-2b"))
    cached = []
    for root in sorted(roots):
        for model, revision in ((BASE, REVISION), (ADAPTER, ADAPTER_REVISION)):
            folder = "models--" + model.replace("/", "--")
            repository = root if root.name == folder else root / folder
            snapshot = repository / "snapshots" / revision
            if snapshot.exists():
                cached.append({"model": model, "snapshot": str(snapshot),
                               "files": [p.name for p in snapshot.iterdir() if p.is_file()]})
    nonstandard = []
    for name in ("config.json", "adapter_config.json"):
        for path in Path("/tmp/opencode").rglob(name):
            try:
                data = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and (data.get("model_type") == "gemma" or
                                           data.get("base_model_name_or_path") == BASE):
                nonstandard.append({"config_path": str(path),
                                    "weight_files": [p.name for p in path.parent.glob("*.safetensors")]})
    packages = {}
    for name in ("torch", "transformers", "peft", "accelerate", "huggingface-hub"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                          "--format=csv,noheader"], capture_output=True, text=True)
    print(json.dumps({"credential_available": bool(token), "base_metadata_access": access,
                      "base": BASE, "base_revision": REVISION,
                      "adapter": ADAPTER, "adapter_revision": ADAPTER_REVISION,
                      "searched_hf_cache_roots": [str(p) for p in sorted(roots)],
                      "pinned_snapshots": cached, "packages": packages,
                      "matching_local_configs_under_tmp_opencode": nonstandard,
                      "gpu": gpu.stdout.strip(), "downloads": 0, "inference_calls": 0,
                      "limitation": "No license acceptance; HF layouts in configured/default cache and /tmp/opencode plus Gemma config metadata under /tmp/opencode checked; not a whole-disk proof."}, indent=2))


if __name__ == "__main__":
    main()

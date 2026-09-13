"""Explicit online preparation; inference scripts run with network denied."""
from pathlib import Path
import shutil
from huggingface_hub import snapshot_download,hf_hub_download
models=[('naver/xprovence-reranker-bgem3-v2','f2798d357213c40164bdd79557d6d2e43ca7d8d2','/tmp/docatlas-xprovence'),('jinaai/jina-embeddings-v3','ab036b023d30b4d1138c4c3bfa9f0c445ab455d6','/tmp/docatlas-jina-v3')]
for repo,rev,path in models:
 snapshot_download(repo,revision=rev,local_dir=path,allow_patterns=['*.json','*.safetensors','*.py','*.model','merges.txt','LICENSE*','README.md'])
code='/tmp/docatlas-jina-code'
snapshot_download('jinaai/xlm-roberta-flash-implementation',revision='bd55a5ec8e6c0fb1d6c26efb4b6a4a74ce8a88d3',local_dir=code,allow_patterns=['*.py','LICENSE*'])
p=Path('/tmp/docatlas_jina_impl');p.mkdir(exist_ok=True);(p/'__init__.py').touch()
for f in Path(code).glob('*.py'):shutil.copyfile(f,p/f.name)

rev='9217f5db79a29953eb74d5343926648285ec7e67'
hf_hub_download('Qwen/Qwen2.5-0.5B-Instruct-GGUF','qwen2.5-0.5b-instruct-q8_0.gguf',revision=rev,local_dir='/tmp/docatlas-context-gguf')
Path('/tmp/docatlas-context-gguf/revision.txt').write_text(rev)

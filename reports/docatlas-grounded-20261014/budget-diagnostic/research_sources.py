"""Fetch primary text/config/license artifacts only; never model weights."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

SOURCES = {
    'setr-paper': 'https://arxiv.org/html/2507.06838v2',
    'setr-readme': 'https://raw.githubusercontent.com/LGAI-Research/SetR/main/README.md',
    'setr-license': 'https://raw.githubusercontent.com/LGAI-Research/SetR/main/License.md',
    'setr-train': 'https://raw.githubusercontent.com/LGAI-Research/SetR/main/train_llama_3.1_8B_inst_gcp.sh',
    'paraset-paper': 'https://arxiv.org/html/2607.05712v1',
    'provence-paper': 'https://arxiv.org/html/2501.16214v1',
    'provence-card': 'https://huggingface.co/naver/provence-reranker-debertav3-v1/raw/main/README.md',
    'provence-config': 'https://huggingface.co/naver/provence-reranker-debertav3-v1/raw/main/config.json',
    'provence-license': 'https://huggingface.co/naver/provence-reranker-debertav3-v1/raw/main/Provence%20LICENSE.txt',
    'xprovence-paper': 'https://arxiv.org/html/2601.18886v1',
    'xprovence-card': 'https://huggingface.co/naver/xprovence-reranker-bgem3-v2/raw/main/README.md',
    'xprovence-config': 'https://huggingface.co/naver/xprovence-reranker-bgem3-v2/raw/main/config.json',
    'late-paper': 'https://arxiv.org/html/2409.04701v3',
    'late-readme': 'https://raw.githubusercontent.com/jina-ai/late-chunking/main/README.md',
    'late-license': 'https://raw.githubusercontent.com/jina-ai/late-chunking/main/LICENSE',
    'jina-card': 'https://huggingface.co/jinaai/jina-embeddings-v2-base-en/raw/main/README.md',
    'longrefiner-paper': 'https://arxiv.org/html/2505.10413v1',
    'longrefiner-readme': 'https://raw.githubusercontent.com/ignorejjj/LongRefiner/main/README.md',
    'longrefiner-license': 'https://raw.githubusercontent.com/ignorejjj/LongRefiner/main/LICENSE',
    'longrefiner-card': 'https://huggingface.co/ignorejjj/LongRefiner/raw/main/README.md',
}


def main():
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=False)

    def fetch(item):
        name, url = item
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                raw = response.read()
                resolved = response.url
            (output / (name + '.txt')).write_bytes(raw)
            return dict(name=name, url=url, resolved=resolved, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        except Exception as exc:
            return dict(name=name, url=url, error=str(exc))

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(fetch, SOURCES.items()))
    (output / 'SOURCES.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()

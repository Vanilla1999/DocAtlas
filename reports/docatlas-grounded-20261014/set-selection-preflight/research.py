"""Read-only artifact discovery; downloads metadata/papers, never model weights."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

URLS = {
    'setr-repo': 'https://api.github.com/repos/LGAI-Research/SetR',
    'setr-tree': 'https://api.github.com/repos/LGAI-Research/SetR/git/trees/main?recursive=1',
    'setr-releases': 'https://api.github.com/repos/LGAI-Research/SetR/releases',
    'setr-issues': 'https://api.github.com/repos/LGAI-Research/SetR/issues?state=all&per_page=100',
    'setr-paper': 'https://arxiv.org/html/2507.06838v2',
    'paraset-paper': 'https://arxiv.org/html/2607.05712v1',
    'paraset-abstract': 'https://arxiv.org/abs/2607.05712',
    'hf-paraset': 'https://huggingface.co/api/models?search=ParaSet&limit=100',
    'hf-setce': 'https://huggingface.co/api/models?search=SetCE&limit=100',
    'hf-setr': 'https://huggingface.co/api/models?search=SetR&limit=100',
    'github-paraset': 'https://api.github.com/search/repositories?q=ParaSet',
    'github-setce': 'https://api.github.com/search/repositories?q=SetCE',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)

    def fetch(item):
        name, url = item
        record = dict(url=url, accessed_at=datetime.now(timezone.utc).isoformat())
        try:
            with urlopen(Request(url, headers={'User-Agent': 'DocAtlas-artifact-preflight'}), timeout=90) as response:
                body = response.read()
                record.update(status=response.status, final_url=response.url)
        except HTTPError as exc:
            body = exc.read()
            record.update(status=exc.code, error=str(exc))
        except Exception as exc:
            body = str(exc).encode()
            record.update(status=None, error=str(exc))
        (args.output / (name + '.txt')).write_bytes(body)
        record.update(file=name + '.txt', bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        return name, record

    with ThreadPoolExecutor(max_workers=4) as executor:
        records = dict(executor.map(fetch, URLS.items()))
    if records['setr-tree']['status'] == 200:
        revision = json.loads((args.output / 'setr-tree.txt').read_text())['sha']
        pinned = {name: f'https://raw.githubusercontent.com/LGAI-Research/SetR/{revision}/{path}'
                  for name, path in [('setr-readme', 'README.md'), ('setr-license', 'License.md'),
                                     ('setr-train', 'train_llama_3.1_8B_inst_gcp.sh')]}
        records.update(dict(map(fetch, pinned.items())))
    (args.output / 'SOURCES.json').write_text(json.dumps(records, indent=2) + '\n')
    print(json.dumps(records, indent=2))


if __name__ == '__main__':
    main()

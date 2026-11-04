"""Explicit pre-run provisioning of checksum-pinned public GGUF weights."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--model', required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
manifest = json.loads(Path(__file__).with_name('models.json').read_text())
entry = manifest['models'][a.model]
url = f"https://huggingface.co/{entry['repository']}/resolve/{entry['revision']}/{entry['filename']}"
a.output.parent.mkdir(parents=True, exist_ok=True)
checksum, size = hashlib.sha256(), 0
with urllib.request.urlopen(url, timeout=180) as response, a.output.open('xb') as output:
    if not response.geturl().startswith('https://'):
        raise RuntimeError('insecure model redirect')
    while block := response.read(4 * 1024 * 1024):
        size += len(block)
        if size > 4_000_000_000:
            raise RuntimeError('unexpected model size')
        checksum.update(block)
        output.write(block)
if checksum.hexdigest() != entry['sha256']:
    a.output.unlink(missing_ok=True)
    raise RuntimeError('model checksum mismatch')
print(json.dumps({**entry, 'bytes': size, 'verified': True}))

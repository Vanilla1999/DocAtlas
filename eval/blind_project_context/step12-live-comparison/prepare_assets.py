"""Restore exact previously frozen assets; no inference or product changes."""
import hashlib
import json
from pathlib import Path
import urllib.request

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'step10-open-scorer/assets-provenance.json'
OUT = Path('/tmp/opencode/step12-qwen-assets')

if __name__ == '__main__':
    manifest = json.loads(SOURCE.read_text())
    OUT.mkdir(exist_ok=False)
    for name, entry in manifest['files'].items():
        target = OUT / name
        with urllib.request.urlopen(entry['url'], timeout=120) as response, target.open('xb') as stream:
            while block := response.read(1024 * 1024):
                stream.write(block)
        with target.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        assert digest == entry['sha256'], name
        assert target.stat().st_size == entry['bytes'], name
        print('verified', name, target.stat().st_size, flush=True)
    (OUT / 'provenance.json').write_text(SOURCE.read_text())
    print('All frozen assets restored; no inference.', flush=True)

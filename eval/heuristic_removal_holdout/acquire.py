"""Bounded original-source acquisition only; never calls DocAtlas or evaluates outputs."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent
SOURCES = [
    ("click", "pallets/click", "8.1.8", "docs/options.rst"),
    ("requests", "psf/requests", "v2.32.3", "docs/user/quickstart.rst"),
    ("pytest", "pytest-dev/pytest", "8.3.5", "doc/en/how-to/skipping.rst"),
    ("tox", "tox-dev/tox", "4.24.1", "docs/config.rst"),
]
PAPERS = {
    "beir": "https://arxiv.org/pdf/2104.08663v4",
    "sufficient-context": "https://arxiv.org/pdf/2411.06037v3",
    "setr": "https://arxiv.org/pdf/2507.06838v2",
    "raptor": "https://arxiv.org/pdf/2401.18059v1",
    "lost-middle": "https://aclanthology.org/2024.tacl-1.9.pdf",
    "anthropic": "https://www.anthropic.com/engineering/contextual-retrieval",
    "sqlite-fts5": "https://www.sqlite.org/fts5.html",
}


def fetch(url, destination):
    request = urllib.request.Request(url, headers={"User-Agent": "independent-source-audit/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = response.read(12_000_001)
            if len(data) > 12_000_000:
                raise ValueError("12 MB source ceiling exceeded")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            return {"url": url, "path": str(destination.relative_to(ROOT)),
                    "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                    "status": response.status, "final_url": response.url}
    except Exception as exc:
        return {"url": url, "error": str(exc)}


def main():
    records = []
    for family, repo, ref, path in SOURCES:
        url = f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"
        record = fetch(url, ROOT / "corpus" / family / path)
        record.update(family=family, repository=repo, revision=ref, upstream_path=path)
        records.append(record)
    for name, url in PAPERS.items():
        ext = "html" if name in {"anthropic", "sqlite-fts5"} else "pdf"
        records.append(dict(fetch(url, ROOT / "research" / f"{name}.{ext}"), paper=name))
    (ROOT / "acquisition.json").write_text(json.dumps(records, indent=2) + "\n")


if __name__ == "__main__":
    main()

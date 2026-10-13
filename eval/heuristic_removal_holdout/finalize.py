"""Data-only manifest freeze. Do not rerun after outputs; no product dependencies."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    acquired = json.loads((ROOT / "acquisition.json").read_text())
    sources = []
    for item in acquired:
        if "family" not in item:
            continue
        family = item["family"]
        sources.append(dict(item, project_group=family, project_root=f"corpus/{family}"))
    (ROOT / "source-manifest.json").write_text(json.dumps(dict(
        schema_version=1, dataset_id="NEW20-20261013", sources=sources), indent=2) + "\n")
    cases = json.loads((ROOT / "sealed/questions.json").read_text())["cases"]
    witnesses = json.loads((ROOT / "sealed/witness-audit.json").read_text())["witnesses"]
    if Counter(x["answerability"] for x in cases) != Counter(positive=8, partial=6, negative=6):
        raise ValueError("wrong frozen distribution")
    if not all(x["exact"] for x in witnesses):
        raise ValueError("raw byte witness audit failed")
    entries = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.name == "FREEZE_MANIFEST.json" or "__pycache__" in path.parts:
            continue
        raw = path.read_bytes()
        entries.append(dict(path=str(path.relative_to(ROOT)), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                            sealed="sealed" in path.relative_to(ROOT).parts))
    manifest = dict(schema_version=1, dataset_id="NEW20-20261013",
                    frozen_at_utc=datetime.now(timezone.utc).isoformat(), state="SEALED_PRE_OUTPUT",
                    boundary="D data-only acquisition/pinning; zero product/test/benchmark/model calls",
                    distribution=dict(Counter(x["answerability"] for x in cases)),
                    families=sorted({x["project_group"] for x in cases}), cases=len(cases),
                    witness_occurrences=len(witnesses), files=entries)
    (ROOT / "FREEZE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()

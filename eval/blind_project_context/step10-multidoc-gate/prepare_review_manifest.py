"""Write unapproved review artifacts only. No model loading or gate execution."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys

from docmancer.docs.application import context_evidence_scoring as scorer

ROOT = Path(__file__).resolve().parent
TREE = ROOT.parents[2]


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def main():
    assets = Path("/tmp/opencode/step10-qwen-reranker-06b-assets")
    scorer.verify_assets(str(assets))
    smoke = Path("/tmp/opencode/step10-qwen-model-card-smoke-01/receipt.json")
    (ROOT / "model-card-smoke-receipt.json").write_bytes(smoke.read_bytes())
    save(ROOT / "runtime-post-install.json", {
        "python": sys.version, "executable": sys.executable, "platform": platform.platform(),
        "packages": dict(sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())),
        "install_command": "uv pip install --offline --link-mode hardlink --python /tmp/opencode/step10-qwen-gpu-py312/bin/python -e .",
        "assets": str(assets), "all_nine_asset_hashes_reverified": True,
        "asset_provenance_sha256": hashlib.sha256((assets / "provenance.json").read_bytes()).hexdigest(),
        "gate_calls": 0, "new_model_calls_this_command": 0,
    })
    save(ROOT / "recipe-freeze-ready.json", {
        "status": "DRAFT_AWAITING_PARENT_REVIEW", "default_enabled": False,
        "contract": scorer.CONTRACT, "contract_sha256": scorer.CONTRACT_SHA256,
        "policy_schema": 3, "calibration_recipe": scorer.CALIBRATION_RECIPE,
        "threshold": None, "calibration_sha256": None,
        "selection": "score >= threshold; equal scores admitted together; no rounding",
        "fit": "largest observed finite breakpoint preserving required final obligations under closure",
        "empty_boundary": "nextafter(max_score,+inf); separately recorded, never fitted",
        "full_contract": "FREEZE_READY_CONTRACT_RU.md",
    })
    # Hash the entire production Python/data tree because this shared checkout
    # contains pre-existing uncommitted implementation dependencies.
    paths = set((TREE / "docmancer").rglob("*.py"))
    paths.update(p for p in (TREE / "docmancer/docs/data").rglob("*") if p.is_file())
    paths.update({TREE / "pyproject.toml", TREE / "eval/evidence_quality_v2/runtime.py"})
    paths.update(p for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                 and p.name != "freeze-ready-manifest.json")
    paths.update(p for p in (ROOT.parent / "step10-open-scorer").rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts)
    paths.update(p for p in (ROOT.parent / "step10-qwen-public-preflight").rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts)
    save(ROOT / "freeze-ready-manifest.json", {
        "status": "DRAFT_AWAITING_PARENT_REVIEW", "frozen_before_inference": False,
        "contract_sha256": scorer.CONTRACT_SHA256, "gate_calls": 0,
        "approved_model_card_smoke_forwards": 2, "threshold": None,
        "authorized_public_diagnostic_forwards": 16,
        "authorized_public_diagnostic_input_tokens": 6608,
        "asset_sha256": scorer.ASSETS,
        "files": {p.relative_to(TREE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)},
        "excluded": ["manifest itself", "parent review/checkpoint documents", "pycache", "external runtime binaries"],
    })
    print("Review manifest written; status DRAFT_AWAITING_PARENT_REVIEW; no inference")


if __name__ == "__main__":
    main()

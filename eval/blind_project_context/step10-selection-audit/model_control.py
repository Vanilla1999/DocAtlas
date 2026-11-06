"""Independent model-card encoding control for the failed public T01 source.

Diagnostic only: no production selectors/helpers, threshold fitting, new labels,
or model downloads. The public-call replay is the end-to-end failure evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    observation = json.loads((args.audit / "original-v3/observations.json").read_text())[0]
    state = json.loads((args.audit / "original-v3/input.json").read_text())
    root = Path("/tmp/opencode/step8-corpora2/L0-0/project")
    raw = (root / "CONTRIBUTING.md").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == state["state"]["files"]["project/CONTRIBUTING.md"]
    lines = raw.decode().splitlines(keepends=True)
    # Independently read the fixed source lines; no product parser or scorer.
    body = "".join(lines[59:63])
    context = "".join(lines[:6]) + lines[58]
    headings = lines[0] + lines[58]
    translation = json.loads((args.audit.parent / "step10-agent-evaluation/renewed-audit.json").read_text())["question"]["search_question"]
    queries = {"original": state["request"]["question"], "translation": translation}
    expected_assets = observation["receipt"]["model"]["assets_sha256"]
    actual_assets = {name: hashlib.sha256((args.model / name).read_bytes()).hexdigest()
                     for name in expected_assets}
    assert actual_assets == expected_assets

    import torch
    import transformers
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch.set_num_threads(8)
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True, trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model, local_files_only=True, trust_remote_code=False,
        use_safetensors=True, dtype=torch.float32, attn_implementation="sdpa").eval()
    inputs, records = [], []
    for lane, query in queries.items():
        for name, intro in (("contextual", context), ("headings", headings), ("body", "")):
            # Official model-card route: tokenizer(query, passage).
            pair = tokenizer(query, intro + body, truncation=False)
            assert len(pair["input_ids"]) <= tokenizer.model_max_length
            # Independently compare the public scorer's split-token construction.
            qids = tokenizer(query, add_special_tokens=False)["input_ids"]
            cids = tokenizer(intro, add_special_tokens=False)["input_ids"]
            bids = tokenizer(body, add_special_tokens=False)["input_ids"]
            split = tokenizer.prepare_for_model(qids, pair_ids=cids + bids, add_special_tokens=True)
            records.append({"lane": lane, "variant": name, "question": query,
                            "passage": intro + body, "tokens": len(pair["input_ids"]),
                            "split_encoding_equal": dict(pair) == dict(split)})
            inputs.append(pair)
    query = "How many people live in Berlin?"
    for passage in (
        "Berlin has a population of 3,520,031 registered inhabitants in an area of 891.82 square kilometers.",
        "New York City is famous for the Metropolitan Museum of Art.",
    ):
        pair = tokenizer(query, passage, truncation=False)
        inputs.append(pair)
        records.append({"lane": "model_card_control", "question": query, "passage": passage,
                        "tokens": len(pair["input_ids"])})
    tick = time.perf_counter()
    with torch.inference_mode():
        values = model(**tokenizer.pad(inputs, padding=True, return_tensors="pt")).logits[:, 0].float().tolist()
    for row, score in zip(records, values, strict=True):
        row["score"] = score
    witness = next(r for r in observation["scores"] if r["path"] == "CONTRIBUTING.md" and r["line_start"] == 59)
    result = {"boundary": "independent_direct_HuggingFace_model_card_control_not_public_acceptance",
              "model_pairs": len(inputs), "inference_seconds": time.perf_counter() - tick,
              "torch": torch.__version__, "transformers": transformers.__version__,
              "assets_sha256": actual_assets, "records": records,
              "public_contextual_score": witness["contextual_score"],
              "public_own_body_score": witness["own_body_score"],
              "original_contextual_delta": records[0]["score"] - witness["contextual_score"],
              "original_headings_delta": records[1]["score"] - witness["own_body_score"]}
    (args.out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
